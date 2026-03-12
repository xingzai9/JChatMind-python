"""
LongTermMemoryService - 长期记忆服务

设计：
  WorkingMemory (Markdown)
       ↓
  Reflection Prompt (LLM)
       ↓
  Knowledge Extraction  →  importance score (LLM, 1-10)
       ↓
  importance >= 7  →  存入 SemanticMemory / EpisodicMemory

检索：
  SemanticMemory  → pgvector cosine similarity (semantic search)
  EpisodicMemory  → time-aware retrieval：decay_score * cosine_sim

遗忘：
  decay_score = importance * exp(-days_since_created / tau)
  tau = 30 天（可配置）
  定期清理 decay_score < threshold 的记忆
"""
import json
import math
import logging
from datetime import datetime, timezone
from typing import Optional, List, Dict, Any
import numpy as np
from sqlalchemy.orm import Session
from sqlalchemy import select, update, func

from app.models.memory import SemanticMemory, EpisodicMemory
from app.services.rag_service import RagService
from app.core.config import settings

logger = logging.getLogger(__name__)

IMPORTANCE_THRESHOLD = settings.lt_memory_importance_threshold
DECAY_TAU_DAYS = settings.lt_memory_decay_tau_days
DECAY_PRUNE_THRESHOLD = settings.lt_memory_decay_prune_threshold

_REFLECTION_PROMPT = """\
你是一个专业的知识提炼助手。请从下面的「会话工作记忆」中提取值得长期保留的知识。

【工作记忆】
{working_memory}

**提取规则**
1. 只提取「长期有价值」的知识，忽略临时/一次性信息
2. 每条记忆需评估重要性（importance_score: 1-10）：
   - 9-10: 核心用户信息（姓名、职业）、不可逆决策
   - 7-8: 用户强偏好、关键技能掌握、重要事实
   - 5-6: 一般偏好、普通事件（不存入）
   - 1-4: 临时上下文（不存入）
3. 只输出 importance_score >= 7 的条目

**输出 JSON 格式（严格）**
{{
  "semantic_memories": [
    {{
      "memory_type": "preference|personal_info|knowledge|skill",
      "topic": "简洁主题（≤20字）",
      "content": "具体内容（≤80字）",
      "importance_score": 8
    }}
  ],
  "episodic_memories": [
    {{
      "event_summary": "事件摘要（≤50字）",
      "event_detail": "详细描述（可选，≤150字）",
      "importance_score": 7,
      "event_time": "ISO8601 时间（若未知则填当前时间）"
    }}
  ]
}}

注意：
- semantic_memories：偏好、个人信息、知识、技能 → 稳定、可被多次引用
- episodic_memories：完成的任务、关键事件 → 有时间戳、一次性
- 没有内容的数组填 []
- 严格 JSON，不要 markdown 代码块包裹

直接输出 JSON："""


class LongTermMemoryService:

    def __init__(self, llm_client, db: Session):
        """
        Args:
            llm_client: LangChain LLM（共用，无 tools）
            db: SQLAlchemy Session
        """
        self.llm = llm_client
        self.db = db
        self._rag = RagService(db)

    # ──────────────────────────────────────────────
    # Reflection & Extraction
    # ──────────────────────────────────────────────

    def reflect_and_extract(
        self,
        working_memory_md: str,
        agent_id,
        user_id: str,
        source_session_id: Optional[str] = None
    ) -> Dict[str, int]:
        """
        Reflection：从工作记忆中提取长期记忆。
        Returns: {"semantic": n, "episodic": m} 存入条数统计
        """
        if not working_memory_md or not working_memory_md.strip():
            return {"semantic": 0, "episodic": 0}

        raw = self._call_llm_json(_REFLECTION_PROMPT.format(working_memory=working_memory_md))
        if not raw:
            return {"semantic": 0, "episodic": 0}

        semantic_count = self._store_semantic(
            raw.get("semantic_memories", []),
            agent_id, user_id, source_session_id
        )
        episodic_count = self._store_episodic(
            raw.get("episodic_memories", []),
            agent_id, user_id, source_session_id
        )

        self.db.commit()
        logger.info(
            "Reflection 完成: semantic=%d, episodic=%d (agent=%s, user=%s)",
            semantic_count, episodic_count, agent_id, user_id
        )
        return {"semantic": semantic_count, "episodic": episodic_count}

    # ──────────────────────────────────────────────
    # Retrieval
    # ──────────────────────────────────────────────

    def semantic_search(
        self,
        query: str,
        agent_id,
        user_id: str,
        top_k: int = 5
    ) -> List[SemanticMemory]:
        """
        语义检索：pgvector cosine similarity
        同时更新 access_count 和 last_accessed_at
        """
        try:
            q_emb = self._rag.embed(query)
        except Exception as e:
            logger.warning("语义记忆检索: embedding 失败 %s", e)
            return []

        stmt = (
            select(SemanticMemory)
            .where(
                SemanticMemory.agent_id == agent_id,
                SemanticMemory.user_id == user_id,
            )
            .order_by(SemanticMemory.embedding.cosine_distance(q_emb))
            .limit(top_k)
        )
        results = self.db.execute(stmt).scalars().all()

        for r in results:
            r.access_count = (r.access_count or 0) + 1
            r.last_accessed_at = datetime.utcnow()
        if results:
            self.db.commit()

        return results

    def episodic_retrieval(
        self,
        query: str,
        agent_id,
        user_id: str,
        top_k: int = 5,
        time_weight: float = 0.4
    ) -> List[EpisodicMemory]:
        """
        时间感知检索：先刷新 decay_score，再综合向量相似度 + decay 排序
        time_weight: decay 分数的权重（0~1），剩余权重给向量相似度
        """
        self._refresh_decay_scores(agent_id, user_id)

        try:
            q_emb = self._rag.embed(query)
        except Exception as e:
            logger.warning("情节记忆检索: embedding 失败 %s", e)
            return []

        # DB 层按 decay_score 降序粗召回 top_k*4，减少 Python 内存占用
        pre_k = max(top_k * 4, 20)
        records = (
            self.db.query(EpisodicMemory)
            .filter(
                EpisodicMemory.agent_id == agent_id,
                EpisodicMemory.user_id == user_id,
            )
            .order_by(EpisodicMemory.decay_score.desc())
            .limit(pre_k)
            .all()
        )

        if not records:
            return []

        q_arr = np.array(q_emb, dtype=np.float32)
        q_norm = np.linalg.norm(q_arr) + 1e-9
        scored = []
        for r in records:
            emb_arr = np.array(r.embedding, dtype=np.float32)
            cosine_sim = float(np.dot(q_arr, emb_arr) / (q_norm * (np.linalg.norm(emb_arr) + 1e-9)))
            decay_norm = min(float(r.decay_score) / 10.0, 1.0)
            combined = (1 - time_weight) * cosine_sim + time_weight * decay_norm
            scored.append((combined, r))

        scored.sort(key=lambda x: x[0], reverse=True)
        top_results = [r for _, r in scored[:top_k]]

        # 更新访问统计
        now = datetime.utcnow()
        for r in top_results:
            r.access_count = (r.access_count or 0) + 1
            r.last_accessed_at = now
        if top_results:
            try:
                self.db.commit()
            except Exception:
                self.db.rollback()

        return top_results

    # ──────────────────────────────────────────────
    # Context building (inject into system prompt)
    # ──────────────────────────────────────────────

    def _has_any_memory(self, agent_id, user_id: str) -> bool:
        """快速预检：该 agent+user 是否存在任何长期记忆（避免无记录时做无谓 embedding）"""
        try:
            sem_count = (
                self.db.query(SemanticMemory.id)
                .filter(SemanticMemory.agent_id == agent_id, SemanticMemory.user_id == user_id)
                .limit(1)
                .count()
            )
            if sem_count > 0:
                return True
            epi_count = (
                self.db.query(EpisodicMemory.id)
                .filter(EpisodicMemory.agent_id == agent_id, EpisodicMemory.user_id == user_id)
                .limit(1)
                .count()
            )
            return epi_count > 0
        except Exception:
            return False

    def build_memory_context(
        self,
        query: str,
        agent_id,
        user_id: str,
        semantic_top_k: int = settings.lt_memory_semantic_top_k,
        episodic_top_k: int = settings.lt_memory_episodic_top_k
    ) -> str:
        """
        构建注入 system_prompt 的记忆上下文 Markdown 片段。
        无记忆时跳过 embedding，直接返回空字符串。
        """
        # 快速预检：无记忆则跳过 embedding 调用（避免白白等待 Ollama）
        if not self._has_any_memory(agent_id, user_id):
            return ""

        lines = []

        sem = self.semantic_search(query, agent_id, user_id, top_k=semantic_top_k)
        if sem:
            lines.append("### 📚 用户相关知识（语义记忆）")
            for s in sem:
                lines.append(f"- [{s.memory_type}] **{s.topic}**：{s.content}")

        epi = self.episodic_retrieval(query, agent_id, user_id, top_k=episodic_top_k)
        if epi:
            lines.append("\n### 📅 历史事件（情节记忆）")
            for e in epi:
                ts = e.event_time.strftime("%Y-%m-%d") if e.event_time else "未知时间"
                lines.append(f"- `{ts}` {e.event_summary}")

        if not lines:
            return ""

        return "\n## 🧠 长期记忆\n" + "\n".join(lines)

    # ──────────────────────────────────────────────
    # Maintenance
    # ──────────────────────────────────────────────

    def prune_decayed(self, agent_id, user_id: str) -> int:
        """清理衰减分数过低的情节记忆，返回删除条数。"""
        self._refresh_decay_scores(agent_id, user_id)
        victims = (
            self.db.query(EpisodicMemory)
            .filter(
                EpisodicMemory.agent_id == agent_id,
                EpisodicMemory.user_id == user_id,
                EpisodicMemory.decay_score < DECAY_PRUNE_THRESHOLD
            )
            .all()
        )
        for v in victims:
            self.db.delete(v)
        if victims:
            self.db.commit()
        logger.info("清理衰减记忆 %d 条 (agent=%s, user=%s)", len(victims), agent_id, user_id)
        return len(victims)

    # ──────────────────────────────────────────────
    # Private helpers
    # ──────────────────────────────────────────────

    _SIM_DEDUP_THRESHOLD = 0.92  # cosine 相似度 >= 此値则视为重复记忆

    def _find_duplicate_semantic(
        self,
        emb: List[float],
        agent_id,
        user_id: str,
    ) -> Optional[SemanticMemory]:
        """cosine 相似度检测：若已有记忆与待入记忆非常相似，返回现有记忆。"""
        stmt = (
            select(SemanticMemory)
            .where(
                SemanticMemory.agent_id == agent_id,
                SemanticMemory.user_id == user_id,
            )
            .order_by(SemanticMemory.embedding.cosine_distance(emb))
            .limit(1)
        )
        candidate = self.db.execute(stmt).scalars().first()
        if candidate is None:
            return None
        # 手动计算 cosine 相似度
        a = np.array(emb, dtype=np.float32)
        b = np.array(candidate.embedding, dtype=np.float32)
        sim = float(np.dot(a, b) / (np.linalg.norm(a) * np.linalg.norm(b) + 1e-9))
        return candidate if sim >= self._SIM_DEDUP_THRESHOLD else None

    def _store_semantic(
        self,
        items: List[dict],
        agent_id,
        user_id: str,
        source_session_id: Optional[str]
    ) -> int:
        count = 0
        for item in items:
            score = float(item.get("importance_score", 0))
            if score < IMPORTANCE_THRESHOLD:
                continue
            content = item.get("content", "").strip()
            if not content:
                continue
            try:
                emb = self._rag.embed(content)
            except Exception as e:
                logger.warning("SemanticMemory embedding 失败: %s", e)
                continue

            # 相似度去重：若已有高相似记忆，则更新而非新建
            dup = self._find_duplicate_semantic(emb, agent_id, user_id)
            if dup is not None:
                if score > (dup.importance_score or 0):
                    dup.content = content
                    dup.importance_score = score
                    dup.topic = item.get("topic", dup.topic)[:255]
                logger.debug("语义记忆去重更新: topic=%s", dup.topic)
                count += 1
                continue

            mem = SemanticMemory(
                agent_id=agent_id,
                user_id=user_id,
                memory_type=item.get("memory_type", "knowledge"),
                topic=item.get("topic", "")[:255],
                content=content,
                embedding=emb,
                importance_score=score,
                source_session_id=str(source_session_id) if source_session_id else None,
            )
            self.db.add(mem)
            count += 1
        return count

    def _store_episodic(
        self,
        items: List[dict],
        agent_id,
        user_id: str,
        source_session_id: Optional[str]
    ) -> int:
        count = 0
        for item in items:
            score = float(item.get("importance_score", 0))
            if score < IMPORTANCE_THRESHOLD:
                continue
            summary = item.get("event_summary", "").strip()
            if not summary:
                continue
            try:
                emb = self._rag.embed(summary)
            except Exception as e:
                logger.warning("EpisodicMemory embedding 失败: %s", e)
                continue

            event_time = datetime.utcnow()
            raw_ts = item.get("event_time")
            if raw_ts:
                try:
                    event_time = datetime.fromisoformat(raw_ts.replace("Z", "+00:00"))
                    if event_time.tzinfo is not None:
                        event_time = event_time.replace(tzinfo=None)
                except Exception:
                    pass

            mem = EpisodicMemory(
                agent_id=agent_id,
                user_id=user_id,
                event_summary=summary,
                event_detail=item.get("event_detail", ""),
                embedding=emb,
                importance_score=score,
                decay_score=score,  # 初始 decay_score = importance
                event_time=event_time,
                source_session_id=str(source_session_id) if source_session_id else None,
            )
            self.db.add(mem)
            count += 1
        return count

    def _refresh_decay_scores(self, agent_id, user_id: str):
        """SQL UPDATE 批量刷新衣减分数，避免把所有记录拉到 Python 内存。"""
        self.db.execute(
            update(EpisodicMemory)
            .where(
                EpisodicMemory.agent_id == agent_id,
                EpisodicMemory.user_id == user_id,
            )
            .values(
                decay_score=EpisodicMemory.importance_score
                * func.exp(
                    -func.extract(
                        "epoch",
                        func.now() - EpisodicMemory.created_at,
                    )
                    / 86400.0
                    / DECAY_TAU_DAYS
                )
            )
        )

    def _call_llm_json(self, prompt: str) -> Optional[Dict]:
        from langchain_core.messages import HumanMessage
        try:
            resp = self.llm.invoke([HumanMessage(content=prompt)])
            raw = (resp.content or "").strip()
            # 去除可能的 markdown 代码块
            if raw.startswith("```"):
                raw = raw.split("```")[1]
                if raw.startswith("json"):
                    raw = raw[4:]
            return json.loads(raw.strip())
        except json.JSONDecodeError as e:
            logger.warning("LongTermMemory Reflection JSON 解析失败: %s", e)
            return None
        except Exception as e:
            logger.error("LongTermMemory LLM 调用失败: %s", e, exc_info=True)
            return None
