"""
JChatMind Agent - 基于 LangChain 的智能体实现
简化版本：使用 LLM + 工具，暂不使用复杂的 Agent 框架
"""
from typing import List, Optional, Dict, Any, Iterator, Callable
from uuid import UUID as PyUUID
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain_core.messages import AIMessage, SystemMessage, ToolMessage
from langchain_community.chat_message_histories import ChatMessageHistory
from sqlalchemy.orm import Session
import logging
import json
import time
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed

from app.models.agent import Agent, ChatSession, ChatMessage
from app.models import KnowledgeBase
from app.services.llm_client import LLMClientFactory
from app.agents.tools.knowledge_tool import KnowledgeTool
from app.agents.tools.file_processor_tool import FileProcessorTool
from app.agents.tools.skills_tool import SkillsTool
from app.agents.tools.email_tool import EmailTool
from app.agents.tools.python_executor_tool import PythonExecutorTool
from app.services.memory.working_memory_service import WorkingMemoryService
from app.services.memory.long_term_memory_service import LongTermMemoryService

logger = logging.getLogger(__name__)


class JChatMindAgent:
    """
    JChatMind Agent 类
    
    功能：
    - Think-Execute 多轮循环
    - 短期记忆（滑动窗口）
    - 工具调用（Tool Calls）
    - 消息持久化
    """

    MAX_STEPS: int = 20
    
    def __init__(
        self,
        agent_config: Agent,
        session: ChatSession,
        db: Session,
        user_id: Optional[str] = None
    ):
        """
        初始化 Agent

        Args:
            agent_config: Agent 配置对象
            session: 聊天会话对象
            db: 数据库会话
            user_id: 用户标识（用于长期记忆跨会话共享）
        """
        self.agent_config = agent_config
        self.session = session
        self.db = db
        self.user_id = user_id or session.user_id or "anonymous"

        # 创建 LLM 客户端
        self.llm = LLMClientFactory.create_client(
            model_type=agent_config.model_type,
            model_name=agent_config.model_name,
            temperature=agent_config.temperature,
            max_tokens=agent_config.max_tokens
        )

        # 创建工具列表
        self.tools = self._create_tools()
        self._llm_with_tools = None  # 延迟初始化

        # 创建短期记忆（使用 ChatMessageHistory）
        self.message_history = ChatMessageHistory()

        # 记忆服务（复用主 LLM，避免重复创建）
        self.working_memory_svc = WorkingMemoryService(self.llm, db)
        self.long_term_memory_svc = LongTermMemoryService(self.llm, db)

        # 加载历史消息
        self._load_history()

        # 保留 prompt 属性兼容旧测试
        self.prompt = self._create_prompt()

        tool_names = [t.name for t in self.tools]
        logger.info("[ INIT ] agent=%r  session=%s  user=%s  工具=%s",
                    agent_config.name, str(session.id)[:8], self.user_id, tool_names)
    
    def _create_tools(self) -> List:
        """
        创建工具列表
        
        工具使用优先级：
        1. FileProcessorTool - 处理对话中上传的文件
        2. SkillsTool - 学习如何处理特定任务
        3. EmailTool - 发送邮件
        4. KnowledgeTool - 查询知识库获取相关信息
        """
        tools = []

        configured_tools = set(self.agent_config.tools or [])
        # 兼容旧 Agent：未显式配置时默认启用文件和技能工具
        if not configured_tools:
            configured_tools = {"file_processor", "skills_learner", "email_sender", "python_executor"}

        # 1. 文件处理工具
        if "file_processor" in configured_tools:
            tools.append(FileProcessorTool())

        # 2. Skills 技能学习工具
        if "skills_learner" in configured_tools:
            tools.append(SkillsTool())

        # 3. 邮件发送工具
        if "email_sender" in configured_tools:
            tools.append(EmailTool())

        # 4. Python 代码执行工具
        if "python_executor" in configured_tools:
            tools.append(PythonExecutorTool())

        # 5. 知识库工具（有知识库绑定时自动启用，无需显式配置）
        if self.agent_config.knowledge_bases:
            tools.append(KnowledgeTool(db=self.db))
        
        logger.info(f"已加载 {len(tools)} 个工具")
        return tools
    
    def _load_history(self):
        """
        从数据库加载历史消息，并自动修复断裂的 tool_calls 序列。

        LLM API 要求：
        - role=tool 消息必须紧跟在含 tool_calls 的 assistant 消息之后
        - 含 tool_calls 的 assistant 消息必须有所有调用的 tool 响应

        修复策略：
        - 预先计算哪些 tool_call_id 在本窗口内有对应 tool 响应
        - assistant 含 tool_calls 但部分/全部无响应 → 降级为普通文本消息（strip tool_calls）
        - tool 消息无对应前驱 assistant tool_calls → 直接跳过
        """
        db_messages = (
            self.db.query(ChatMessage)
            .filter(ChatMessage.session_id == self.session.id)
            .order_by(ChatMessage.created_at.desc())
            .limit(self.agent_config.max_messages)
            .all()
        )
        db_messages = list(reversed(db_messages))

        # 预计算：窗口内有 tool 响应的 call_id 集合
        responded_ids: set = {
            m.tool_call_id
            for m in db_messages
            if m.role == "tool" and m.tool_call_id
        }

        # 当前 assistant 已登记但尚未被 tool 消息消费的 call_id
        pending_tool_call_ids: set = set()

        for msg in db_messages:
            if msg.role == "user":
                self.message_history.add_user_message(msg.content or "")
                pending_tool_call_ids.clear()

            elif msg.role == "assistant":
                if msg.tool_calls:
                    call_ids = {
                        tc.get("id") if isinstance(tc, dict) else getattr(tc, "id", None)
                        for tc in msg.tool_calls
                    }
                    if call_ids and call_ids.issubset(responded_ids):
                        # 完整序列，正常加载
                        self.message_history.add_message(
                            AIMessage(content=msg.content or "", tool_calls=msg.tool_calls)
                        )
                        pending_tool_call_ids = set(call_ids)
                    else:
                        # 不完整：strip tool_calls，作为普通消息避免 400
                        missing = call_ids - responded_ids
                        logger.warning(
                            "历史 tool_calls 无对应响应 (missing=%s)，降级为普通消息", missing
                        )
                        content = msg.content or "[工具调用历史（不完整，已忽略）]"
                        self.message_history.add_ai_message(content)
                        pending_tool_call_ids.clear()
                else:
                    self.message_history.add_ai_message(msg.content or "")
                    pending_tool_call_ids.clear()

            elif msg.role == "tool":
                if msg.tool_call_id and msg.tool_call_id in pending_tool_call_ids:
                    self.message_history.add_message(
                        ToolMessage(
                            content=msg.content or "",
                            tool_call_id=msg.tool_call_id,
                        )
                    )
                    pending_tool_call_ids.discard(msg.tool_call_id)
                else:
                    logger.warning(
                        "跳过孤立 tool message (tool_call_id=%s)", msg.tool_call_id
                    )

        logger.info("[ HIST ] 历史 %d 条 → 有效 %d 条",
                    len(db_messages), len(self.message_history.messages))
    
    def _create_prompt(self) -> ChatPromptTemplate:
        """创建 Prompt 模板（初始化时仅用基础 system_prompt，不触发 embedding）"""
        base = self.agent_config.system_prompt or ""
        return ChatPromptTemplate.from_messages([
            ("system", base),
            MessagesPlaceholder(variable_name="chat_history"),
            ("human", "{input}"),
        ])

    def _build_llm_messages(self, user_input: str = "") -> List:
        history = self.message_history.messages[-self.agent_config.max_messages:]
        return [SystemMessage(content=self._build_system_prompt(user_input)), *history]

    def _trim_history(self) -> None:
        if len(self.message_history.messages) > self.agent_config.max_messages:
            self.message_history.messages = self.message_history.messages[-self.agent_config.max_messages:]

    def _save_assistant_message(self, ai_message: AIMessage, auto_commit: bool = True) -> None:
        tool_calls_json = None
        if ai_message.tool_calls:
            tool_calls_json = [
                {
                    "id": tc.get("id") if isinstance(tc, dict) else getattr(tc, "id", None),
                    "name": tc.get("name") if isinstance(tc, dict) else getattr(tc, "name", None),
                    "args": tc.get("args") if isinstance(tc, dict) else getattr(tc, "args", {}),
                }
                for tc in ai_message.tool_calls
            ]
        
        db_msg = ChatMessage(
            session_id=self.session.id,
            role="assistant",
            content=str(ai_message.content or ""),
            tool_calls=tool_calls_json,
        )
        self.db.add(db_msg)
        if auto_commit:
            self.db.commit()

    def _save_tool_message(self, tool_call_id: str, content: str, auto_commit: bool = True) -> None:
        db_msg = ChatMessage(
            session_id=self.session.id,
            role="tool",
            content=content,
            tool_call_id=tool_call_id,
        )
        self.db.add(db_msg)
        if auto_commit:
            self.db.commit()

    def _run_tool_only(self, tool_call: dict) -> tuple:
        """仅执行工具逻辑，不写入 message_history 或 db（供并行调用使用，避免共享状态竞争）。"""
        tool_name = tool_call.get("name") if isinstance(tool_call, dict) else getattr(tool_call, "name", None)
        tool_call_id = tool_call.get("id") if isinstance(tool_call, dict) else getattr(tool_call, "id", "tool_call")
        if not tool_call_id:
            tool_call_id = "tool_call"

        tool = next((t for t in self.tools if t.name == tool_name), None)
        if not tool:
            result_text = f"工具 {tool_name} 不存在或未启用。"
            logger.warning(result_text)
            return tool_call_id, tool_name, result_text

        raw_args = tool_call.get("args") if isinstance(tool_call, dict) else getattr(tool_call, "args", {})
        if isinstance(raw_args, str):
            try:
                args = json.loads(raw_args)
            except Exception:
                args = {"input": raw_args}
        elif isinstance(raw_args, dict):
            args = raw_args
        else:
            args = {}

        try:
            logger.info("[ TOOL→] %s  %s", tool_name, str(args)[:80])
            t0 = time.time()
            result = tool.invoke(args)
            result_text = str(result)
            logger.info("[ TOOL←] %s  ✓  %.2fs │ %s",
                        tool_name, time.time() - t0, result_text[:80])
        except Exception as exc:
            logger.error("[ TOOL←] %s  ✗  %s", tool_name, exc, exc_info=True)
            result_text = f"工具 {tool_name} 执行失败：{exc}"

        return tool_call_id, tool_name, result_text

    def _execute_tool_call(self, tool_call: dict, auto_commit: bool = True) -> str:
        tool_name = tool_call.get("name") if isinstance(tool_call, dict) else getattr(tool_call, "name", None)
        tool_call_id = tool_call.get("id") if isinstance(tool_call, dict) else getattr(tool_call, "id", "tool_call")
        if not tool_call_id:
            tool_call_id = "tool_call"
        
        tool = next((t for t in self.tools if t.name == tool_name), None)
        if not tool:
            result_text = f"工具 {tool_name} 不存在或未启用。"
            logger.warning("[ TOOL←] %s  ✗  工具不存在", tool_name)
            self.message_history.add_message(
                ToolMessage(content=result_text, tool_call_id=tool_call_id)
            )
            self._save_tool_message(tool_call_id=tool_call_id, content=result_text)
            return result_text

        raw_args = tool_call.get("args") if isinstance(tool_call, dict) else getattr(tool_call, "args", {})
        if isinstance(raw_args, str):
            try:
                args = json.loads(raw_args)
            except Exception:
                args = {"input": raw_args}
        elif isinstance(raw_args, dict):
            args = raw_args
        else:
            args = {}

        try:
            logger.info("[ TOOL→] %s  %s", tool_name, str(args)[:80])
            t0 = time.time()
            result = tool.invoke(args)
            result_text = str(result)
            logger.info("[ TOOL←] %s  ✓  %.2fs │ %s",
                        tool_name, time.time() - t0, result_text[:80])
        except Exception as exc:
            logger.error("[ TOOL←] %s  ✗  %s", tool_name, exc, exc_info=True)
            result_text = f"工具 {tool_name} 执行失败：{exc}"

        self.message_history.add_message(
            ToolMessage(content=result_text, tool_call_id=tool_call_id)
        )
        self._save_tool_message(tool_call_id=tool_call_id, content=result_text, auto_commit=auto_commit)
        return result_text

    def _get_llm_with_tools(self):
        """延迟初始化带工具的 LLM"""
        if self._llm_with_tools is None:
            self._llm_with_tools = self.llm.bind_tools(self.tools) if self.tools else self.llm
        return self._llm_with_tools

    def _get_current_messages_for_memory(self) -> List[dict]:
        """获取当前会话所有消息（user/assistant），用于记忆服务。"""
        msgs = (
            self.db.query(ChatMessage)
            .filter(ChatMessage.session_id == self.session.id)
            .filter(ChatMessage.role.in_(["user", "assistant"]))
            .order_by(ChatMessage.created_at)
            .all()
        )
        return [{"role": m.role, "content": m.content} for m in msgs]

    def _trigger_memory_update_async(self):
        """在独立 db 会话的后台线程中更新工作记忆和长期记忆，避免使用请求结束后已关闭的 Session。"""
        from app.core.database import SyncSessionLocal

        all_msgs = self._get_current_messages_for_memory()
        if not self.working_memory_svc.should_update(self.session.id, len(all_msgs)):
            return

        session_id = self.session.id
        agent_id = self.agent_config.id
        user_id = self.user_id
        llm = self.llm

        def run_memory_update():
            new_db = SyncSessionLocal()
            try:
                wm_svc = WorkingMemoryService(llm, new_db)
                lt_svc = LongTermMemoryService(llm, new_db)
                wm = wm_svc.update(session_id, agent_id, user_id, all_msgs)
                if wm and wm.content:
                    lt_svc.reflect_and_extract(
                        working_memory_md=wm.content,
                        agent_id=agent_id,
                        user_id=user_id,
                        source_session_id=str(session_id)
                    )
            except Exception as e:
                logger.error("[ MEM  ] 后台更新失败: %s", e, exc_info=True)
            finally:
                new_db.close()

        t = threading.Thread(target=run_memory_update, daemon=True)
        t.start()
        logger.info("[ MEM  ] 后台记忆更新已触发  session=%s", str(session_id)[:8])

    def _run_think_execute_loop(self) -> AIMessage:
        last_ai_message: Optional[AIMessage] = None
        _last_user_input = ""
        for msg in reversed(self.message_history.messages):
            if hasattr(msg, 'type') and msg.type == 'human':
                _last_user_input = str(msg.content)
                break

        for step in range(1, self.MAX_STEPS + 1):
            logger.info("── 步骤 %2d/%-2d ───────────────────────────────────────────────", step, self.MAX_STEPS)
            n_ctx = len(self.message_history.messages)
            logger.info("[ LLM→ ] 上下文 %d 条…", n_ctx)
            t_llm = time.time()
            try:
                llm_response = self._get_llm_with_tools().invoke(
                    self._build_llm_messages(_last_user_input)
                )
            except Exception as e:
                logger.error("[ LLM← ] ✗ 调用失败: %s", e, exc_info=True)
                fallback = AIMessage(content=f"LLM 调用失败：{e}")
                self.message_history.add_message(fallback)
                self._save_assistant_message(fallback)
                self._trim_history()
                return fallback

            if isinstance(llm_response, AIMessage):
                ai_message = llm_response
            else:
                ai_message = AIMessage(content=str(getattr(llm_response, "content", llm_response)))

            last_ai_message = ai_message
            self.message_history.add_message(ai_message)
            self._save_assistant_message(ai_message)

            tool_calls = ai_message.tool_calls or []
            elapsed_llm = time.time() - t_llm
            if not tool_calls:
                logger.info("[ LLM← ] %.2fs │ 直接回答", elapsed_llm)
                self._trim_history()
                return ai_message

            tc_names = ", ".join(
                tc.get("name") if isinstance(tc, dict) else getattr(tc, "name", "?")
                for tc in tool_calls
            )
            logger.info("[ LLM← ] %.2fs │ 工具调用: %s", elapsed_llm, tc_names)

            # 并行执行多个工具调用（如果有多个）
            if len(tool_calls) > 1:
                par_results: dict = {}
                with ThreadPoolExecutor(max_workers=min(len(tool_calls), 3)) as executor:
                    futures = {executor.submit(self._run_tool_only, tc): idx for idx, tc in enumerate(tool_calls)}
                    for future in as_completed(futures):
                        idx = futures[future]
                        try:
                            par_results[idx] = future.result()
                        except Exception as e:
                            tc = tool_calls[idx]
                            t_name = tc.get("name") if isinstance(tc, dict) else getattr(tc, "name", "unknown")
                            t_id = tc.get("id") if isinstance(tc, dict) else getattr(tc, "id", "tool_call")
                            par_results[idx] = (t_id or "tool_call", t_name, f"工具 {t_name} 执行失败：{e}")
                            logger.error("[ TOOL←] %s  ✗  %s", t_name, e)
                for idx in range(len(tool_calls)):
                    t_id, t_name, result_text = par_results[idx]
                    self.message_history.add_message(ToolMessage(content=result_text, tool_call_id=t_id))
                    self._save_tool_message(tool_call_id=t_id, content=result_text, auto_commit=False)
                self.db.commit()
            else:
                for tool_call in tool_calls:
                    self._execute_tool_call(tool_call, auto_commit=True)

        logger.warning("[ DONE ] 达到最大步骤数 %d，强制退出", self.MAX_STEPS)
        fallback = AIMessage(content="已达到最大执行步数，请简化问题后重试。")
        self.message_history.add_message(fallback)
        self._save_assistant_message(fallback)
        self._trim_history()
        return fallback

    def _build_system_prompt(self, user_input: str = "") -> str:
        """构建系统提示词，附加知识库信息 + 工作记忆 + 长期记忆。"""
        base_prompt = self.agent_config.system_prompt or ""
        sections: List[str] = [base_prompt]

        # 1. 知识库信息
        kb_ids = self.agent_config.knowledge_bases or []
        if kb_ids:
            kb_lines: List[str] = []
            parsed_ids: List[PyUUID] = []
            for kb_id in kb_ids:
                try:
                    parsed_ids.append(PyUUID(str(kb_id)))
                except Exception:
                    continue
            try:
                if parsed_ids:
                    kb_rows = (
                        self.db.query(KnowledgeBase.id, KnowledgeBase.name)
                        .filter(KnowledgeBase.id.in_(parsed_ids))
                        .all()
                    )
                    kb_lines = [f"- {name} (id: {kb_id})" for kb_id, name in kb_rows]
            except Exception as e:
                logger.warning(f"读取知识库信息失败，回退到 ID 列表: {e}")
            if not kb_lines:
                kb_lines = [f"- id: {kb_id}" for kb_id in kb_ids]
            sections.append(
                "\n\n【当前可用知识库】\n"
                + "\n".join(kb_lines)
                + "\n\n当用户问题依赖知识库事实时，优先使用 knowledge_query 工具检索后再回答。"
            )

        # 2. 工作记忆（当前会话进展）
        try:
            wm_content = self.working_memory_svc.get_content(self.session.id)
            if wm_content:
                sections.append(f"\n\n## 📋 当前会话工作记忆\n{wm_content}")
        except Exception as e:
            logger.warning("注入工作记忆失败: %s", e)

        # 3. 长期记忆（跨会话）
        try:
            lt_context = self.long_term_memory_svc.build_memory_context(
                query=user_input or "通用检索",
                agent_id=self.agent_config.id,
                user_id=self.user_id
            )
            if lt_context:
                sections.append(f"\n\n{lt_context}")
        except Exception as e:
            logger.warning("注入长期记忆失败: %s", e)

        return "".join(sections)

    def chat(self, user_input: str) -> str:
        """
        处理用户消息
        
        Args:
            user_input: 用户输入
            
        Returns:
            AI 回复
        """
        try:
            # 保存用户消息
            user_msg = ChatMessage(
                session_id=self.session.id,
                role="user",
                content=user_input
            )
            self.db.add(user_msg)
            self.db.commit()
            
            # 添加到消息历史
            self.message_history.add_user_message(user_input)

            final_ai_message = self._run_think_execute_loop()
            ai_response = str(final_ai_message.content or "")
            
            logger.info(f"对话完成：session_id={self.session.id}")
            
            return ai_response
            
        except Exception as e:
            logger.error(f"Agent 执行失败：{e}", exc_info=True)
            
            # 保存错误消息
            error_msg = ChatMessage(
                session_id=self.session.id,
                role="assistant",
                content=f"抱歉，处理您的请求时出现错误：{str(e)}"
            )
            self.db.add(error_msg)
            self.db.commit()
            
            raise
    
    def _run_think_execute_loop_stream(self, on_event: Callable[[dict], None], user_input: str = "") -> AIMessage:
        """流式版本的 think-execute 循环，实时推送结构化事件（与 Java AI_THINKING/AI_EXECUTING 对齐）"""

        for step in range(1, self.MAX_STEPS + 1):
            logger.info("── 步骤 %2d/%-2d ───────────────────────────────────────────────", step, self.MAX_STEPS)
            on_event({
                "type": "AI_THINKING",
                "step": step,
                "maxSteps": self.MAX_STEPS,
                "statusText": f"第 {step}/{self.MAX_STEPS} 步：分析您的请求..."
            })

            n_ctx = len(self.message_history.messages)
            logger.info("[ LLM→ ] 上下文 %d 条…", n_ctx)
            t_llm = time.time()
            try:
                llm_response = self._get_llm_with_tools().invoke(
                    self._build_llm_messages(user_input)
                )
            except Exception as e:
                logger.error("[ LLM← ] ✗ 调用失败: %s", e, exc_info=True)
                fallback = AIMessage(content=f"LLM 调用失败：{e}")
                self.message_history.add_message(fallback)
                self._save_assistant_message(fallback)
                self._trim_history()
                on_event({"type": "answer_chunk", "content": str(fallback.content)})
                return fallback

            if isinstance(llm_response, AIMessage):
                ai_message = llm_response
            else:
                ai_message = AIMessage(content=str(getattr(llm_response, "content", llm_response)))

            self.message_history.add_message(ai_message)
            self._save_assistant_message(ai_message)

            tool_calls = ai_message.tool_calls or []
            elapsed_llm = time.time() - t_llm
            if not tool_calls:
                logger.info("[ LLM← ] %.2fs │ 直接回答", elapsed_llm)
                self._trim_history()
                content = str(ai_message.content or "")
                logger.info("[ DONE ] 回答预览: %s", content[:80])
                # 分块推送最终答案
                chunk_size = 30
                for idx in range(0, len(content), chunk_size):
                    on_event({"type": "answer_chunk", "content": content[idx: idx + chunk_size]})
                return ai_message

            tc_names = ", ".join(
                tc.get("name") if isinstance(tc, dict) else getattr(tc, "name", "?")
                for tc in tool_calls
            )
            logger.info("[ LLM← ] %.2fs │ 工具调用: %s", elapsed_llm, tc_names)

            if len(tool_calls) > 1:
                tool_names = [
                    tc.get("name") if isinstance(tc, dict) else getattr(tc, "name", "unknown")
                    for tc in tool_calls
                ]
                on_event({
                    "type": "AI_EXECUTING",
                    "statusText": f"并行执行 {len(tool_calls)} 个工具",
                    "toolNames": tool_names
                })
                par_results: dict = {}
                with ThreadPoolExecutor(max_workers=min(len(tool_calls), 3)) as executor:
                    futures = {
                        executor.submit(self._run_tool_only, tc): idx
                        for idx, tc in enumerate(tool_calls)
                    }
                    for future in as_completed(futures):
                        idx = futures[future]
                        tc = tool_calls[idx]
                        tool_name = tc.get("name") if isinstance(tc, dict) else getattr(tc, "name", "unknown")
                        try:
                            par_results[idx] = future.result()
                            on_event({
                                "type": "tool_result",
                                "toolName": tool_name,
                                "success": True,
                                "preview": str(par_results[idx][2])[:300]
                            })
                        except Exception as e:
                            t_id = tc.get("id") if isinstance(tc, dict) else getattr(tc, "id", "tool_call")
                            par_results[idx] = (t_id or "tool_call", tool_name, f"工具 {tool_name} 执行失败：{e}")
                            logger.error("[ TOOL←] %s  ✗  %s", tool_name, e)
                            on_event({
                                "type": "tool_result",
                                "toolName": tool_name,
                                "success": False,
                                "preview": str(e)[:300]
                            })
                for idx in range(len(tool_calls)):
                    t_id, t_name, result_text = par_results[idx]
                    self.message_history.add_message(ToolMessage(content=result_text, tool_call_id=t_id))
                    self._save_tool_message(tool_call_id=t_id, content=result_text, auto_commit=False)
                self.db.commit()
            else:
                for tool_call in tool_calls:
                    tool_name = tool_call.get("name") if isinstance(tool_call, dict) else getattr(tool_call, "name", "unknown")
                    on_event({
                        "type": "AI_EXECUTING",
                        "statusText": f"执行工具: {tool_name}",
                        "toolName": tool_name
                    })
                    try:
                        result = self._execute_tool_call(tool_call, auto_commit=True)
                        on_event({
                            "type": "tool_result",
                            "toolName": tool_name,
                            "success": True,
                            "preview": str(result)[:300] if result else "完成"
                        })
                    except Exception as e:
                        on_event({
                            "type": "tool_result",
                            "toolName": tool_name,
                            "success": False,
                            "preview": str(e)[:300]
                        })

        logger.warning("[ DONE ] 达到最大步骤数 %d，强制退出", self.MAX_STEPS)
        fallback = AIMessage(content="已达到最大执行步数，请简化问题后重试。")
        self.message_history.add_message(fallback)
        self._save_assistant_message(fallback)
        self._trim_history()
        on_event({"type": "answer_chunk", "content": "已达到最大执行步数，请简化问题后重试。"})
        return fallback

    def chat_stream(self, user_input: str) -> Iterator[dict]:
        """
        流式处理用户消息

        Yields:
            结构化事件字典，例如:
            - {"type": "AI_THINKING", "step": 1, "maxSteps": 20, "statusText": "..."}
            - {"type": "AI_EXECUTING", "toolName": "...", "statusText": "..."}
            - {"type": "tool_result", "toolName": "...", "success": True, "preview": "..."}
            - {"type": "answer_chunk", "content": "..."}
        """
        _t_chat = time.time()
        logger.info("─" * 60)
        try:
            user_msg = ChatMessage(
                session_id=self.session.id,
                role="user",
                content=user_input
            )
            self.db.add(user_msg)
            self.db.commit()
            self.message_history.add_user_message(user_input)

            events_buffer: List[dict] = []

            def stream_callback(event: dict):
                events_buffer.append(event)

            result_holder = {"message": None, "error": None}

            def run_loop():
                try:
                    result_holder["message"] = self._run_think_execute_loop_stream(
                        stream_callback, user_input=user_input
                    )
                except Exception as e:
                    result_holder["error"] = e

            thread = threading.Thread(target=run_loop)
            thread.start()

            while thread.is_alive() or events_buffer:
                while events_buffer:
                    yield events_buffer.pop(0)
                time.sleep(0.01)

            thread.join()

            if result_holder["error"]:
                raise result_holder["error"]

            # 对话完成后异步触发记忆更新
            self._trigger_memory_update_async()

            logger.info("─" * 60)
            logger.info("[ DONE ] 对话完成  耗时 %.2fs  session=%s",
                        time.time() - _t_chat, str(self.session.id)[:8])

        except Exception as e:
            logger.error("[ ERR  ] 流式对话失败: %s", e, exc_info=True)
            error_msg = ChatMessage(
                session_id=self.session.id,
                role="assistant",
                content=f"抱歉，处理您的请求时出现错误：{str(e)}"
            )
            self.db.add(error_msg)
            self.db.commit()
            raise
    
    def get_history(self) -> List[Dict[str, Any]]:
        """
        获取会话历史
        
        Returns:
            消息列表
        """
        messages = (
            self.db.query(ChatMessage)
            .filter(ChatMessage.session_id == self.session.id)
            .order_by(ChatMessage.created_at)
            .all()
        )
        
        return [
            {
                "id": str(msg.id),
                "role": msg.role,
                "content": msg.content,
                "created_at": msg.created_at.isoformat()
            }
            for msg in messages
        ]
