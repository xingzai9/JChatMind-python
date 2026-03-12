"""
WorkingMemoryService - 工作记忆服务

核心设计：
  - 消息数达到 threshold（默认6）后触发后台线程更新
  - LLM 生成/增量更新 Markdown 工作记忆文档
  - 文档超长（>2000字）时自动压缩合并
  - 内容结构：已完成工作 / 获取的信息 / 已做决策 / 下一步计划 / 遇到的问题
"""
import threading
import logging
from datetime import datetime
from typing import Optional, List
from sqlalchemy.orm import Session

from app.models.memory import WorkingMemory
from app.models.agent import ChatMessage
from app.core.config import settings

logger = logging.getLogger(__name__)

WORKING_MEMORY_THRESHOLD = settings.working_memory_threshold
MAX_WORKING_MEMORY_CHARS = settings.working_memory_max_chars


_UPDATE_PROMPT = """\
你是一个专业的任务进展整理助手。根据最新对话，更新下面的「工作记忆」文档。

【已有工作记忆】
{existing}

【最新对话内容（最近 {n} 条）】
{conversation}

**更新规则**
1. 只追加/修改真实发生的内容，不捏造
2. 保持各节标题不变（## 已完成工作 / ## 获取的信息 / ## 已做决策 / ## 下一步计划 / ## ⚠️ 遇到的问题）
3. 每个条目用「- 」开头，简洁精炼（≤40字/条）
4. 已完成的「下一步计划」移入「已完成工作」
5. 总文档长度控制在 800 字以内
6. 只输出 Markdown 文档，不要额外说明

直接输出更新后的 Markdown："""

_INIT_PROMPT = """\
你是一个专业的任务进展整理助手。请根据以下对话，生成结构化「工作记忆」文档。

【对话内容】
{conversation}

**生成规则**
1. 只记录真实发生的内容，不捏造
2. 每个条目用「- 」开头，简洁精炼（≤40字/条）
3. 没有内容的节写「- 暂无」
4. 总文档长度控制在 800 字以内
5. 只输出 Markdown，不要额外说明

按照以下格式输出：

## 已完成工作
- 

## 获取的信息
- 

## 已做决策
- 

## 下一步计划
- 

## ⚠️ 遇到的问题
- """

_COMPRESS_PROMPT = """\
以下工作记忆文档过长，请在保留关键信息的前提下压缩至 800 字以内。
合并同类条目，删除已过时内容，保持 5 个节标题不变。只输出压缩后的 Markdown：

{content}"""


class WorkingMemoryService:
    # 类级锁：防止同一 session 并发触发多次更新
    _session_locks: dict = {}
    _session_locks_meta = threading.Lock()

    def __init__(self, llm_client, db: Session):
        """
        Args:
            llm_client: LangChain LLM client（与 Agent 共用）
            db: SQLAlchemy Session
        """
        self.llm = llm_client
        self.db = db

    @classmethod
    def _get_lock(cls, session_id) -> threading.Lock:
        key = str(session_id)
        with cls._session_locks_meta:
            if key not in cls._session_locks:
                cls._session_locks[key] = threading.Lock()
            return cls._session_locks[key]

    # ──────────────────────────────────────────────
    # Public API
    # ──────────────────────────────────────────────

    def should_update(self, session_id, current_msg_count: int) -> bool:
        """判断是否需要更新工作记忆（消息数达到阈值）"""
        wm = self._get_working_memory(session_id)
        if wm is None:
            return current_msg_count >= WORKING_MEMORY_THRESHOLD
        processed = wm.message_count
        return (current_msg_count - processed) >= WORKING_MEMORY_THRESHOLD

    def trigger_update_async(
        self,
        session_id,
        agent_id,
        user_id: Optional[str],
        messages: List[dict],
        on_done=None
    ):
        """
        后台线程异步更新工作记忆。
        - 使用独立 DB session，不复用请求线程的 session
        - per-session 锁：同一 session 同时只有一个线程执行更新
        """
        from app.core.database import SyncSessionLocal
        lock = self._get_lock(session_id)
        llm = self.llm

        def _run():
            if not lock.acquire(blocking=False):
                logger.info("[ MEM  ] session=%s 已在更新中，跳过重复触发", str(session_id)[:8])
                return
            new_db = SyncSessionLocal()
            try:
                svc = WorkingMemoryService(llm, new_db)
                wm = svc.update(session_id, agent_id, user_id, messages)
                if on_done:
                    on_done(wm)
            except Exception as e:
                logger.error("[ MEM  ] 工作记忆后台更新失败: %s", e, exc_info=True)
            finally:
                new_db.close()
                lock.release()

        t = threading.Thread(target=_run, daemon=True)
        t.start()
        return t

    def update(
        self,
        session_id,
        agent_id,
        user_id: Optional[str],
        messages: List[dict]
    ) -> WorkingMemory:
        """
        同步更新工作记忆。
        messages: [{"role": "user"/"assistant", "content": "..."}]
        """
        existing_wm = self._get_working_memory(session_id)
        conversation_text = self._format_messages(messages)

        if existing_wm is None:
            md_content = self._call_llm(_INIT_PROMPT.format(conversation=conversation_text))
            wm = WorkingMemory(
                session_id=session_id,
                agent_id=agent_id,
                user_id=user_id,
                content=md_content,
                message_count=len(messages),
                version=1
            )
            self.db.add(wm)
        else:
            existing_md = existing_wm.content
            new_md = self._call_llm(_UPDATE_PROMPT.format(
                existing=existing_md,
                n=len(messages) - existing_wm.message_count,
                conversation=conversation_text
            ))
            if len(new_md) > MAX_WORKING_MEMORY_CHARS:
                new_md = self._compress(new_md)
            existing_wm.content = new_md
            existing_wm.message_count = len(messages)
            existing_wm.version += 1
            existing_wm.updated_at = datetime.utcnow()
            wm = existing_wm

        self.db.commit()
        logger.info("工作记忆更新完成: session=%s, v=%s", session_id, wm.version)
        return wm

    def get_content(self, session_id) -> Optional[str]:
        """获取当前工作记忆的 Markdown 内容，不存在返回 None"""
        wm = self._get_working_memory(session_id)
        return wm.content if wm else None

    # ──────────────────────────────────────────────
    # Private helpers
    # ──────────────────────────────────────────────

    def _get_working_memory(self, session_id) -> Optional[WorkingMemory]:
        return (
            self.db.query(WorkingMemory)
            .filter(WorkingMemory.session_id == session_id)
            .order_by(WorkingMemory.version.desc())
            .first()
        )

    def _format_messages(self, messages: List[dict]) -> str:
        """
        按角色区别截断：
          - user: 保留 300 字（问题通常是关键信息）
          - assistant: 保留 150 字（回答往往较达，只取开头摘要）
        """
        USER_LIMIT = 300
        ASST_LIMIT = 150
        lines = []
        for m in messages:
            role = m.get("role", "?")
            content = (m.get("content") or "").strip()
            if not content:
                continue
            if role == "user":
                text = content[:USER_LIMIT] + ("…" if len(content) > USER_LIMIT else "")
                lines.append(f"[用户] {text}")
            elif role == "assistant":
                text = content[:ASST_LIMIT] + ("…" if len(content) > ASST_LIMIT else "")
                lines.append(f"[助手] {text}")
        return "\n".join(lines)

    def _call_llm(self, prompt: str) -> str:
        from langchain_core.messages import HumanMessage
        try:
            resp = self.llm.invoke([HumanMessage(content=prompt)])
            return (resp.content or "").strip()
        except Exception as e:
            logger.error("WorkingMemory LLM 调用失败: %s", e)
            return "## 工作记忆生成失败\n- " + str(e)

    def _compress(self, content: str) -> str:
        logger.info("工作记忆超长（%d 字），触发压缩", len(content))
        return self._call_llm(_COMPRESS_PROMPT.format(content=content))
