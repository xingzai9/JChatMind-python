import pytest
from sqlalchemy import select
from app.models import Agent, ChatSession, ChatMessage
import uuid


def test_create_agent(db_session):
    """测试创建 Agent"""
    agent = Agent(
        name="测试助手",
        description="用于测试的 AI 助手",
        system_prompt="你是一个有帮助的 AI 助手",
        model_type="deepseek",
        model_name="deepseek-chat",
        temperature=0.7,
        max_messages=6,
        tools=["knowledge_query"],
        knowledge_bases=["kb-123"]
    )
    
    db_session.add(agent)
    db_session.commit()
    db_session.refresh(agent)
    
    assert agent.id is not None
    assert isinstance(agent.id, uuid.UUID)
    assert agent.name == "测试助手"
    assert agent.model_type == "deepseek"
    assert agent.temperature == 0.7
    assert agent.max_messages == 6
    assert agent.is_active is True
    assert "knowledge_query" in agent.tools


def test_create_chat_session(db_session):
    """测试创建聊天会话"""
    agent = Agent(
        name="测试助手",
        system_prompt="你是一个有帮助的 AI 助手",
        model_type="deepseek",
        model_name="deepseek-chat"
    )
    db_session.add(agent)
    db_session.commit()
    db_session.refresh(agent)
    
    session = ChatSession(
        agent_id=agent.id,
        title="测试对话",
        meta={"source": "web"}
    )
    db_session.add(session)
    db_session.commit()
    db_session.refresh(session)
    
    assert session.id is not None
    assert session.agent_id == agent.id
    assert session.title == "测试对话"
    assert session.meta["source"] == "web"


def test_create_chat_messages(db_session):
    """测试创建聊天消息"""
    agent = Agent(
        name="测试助手",
        system_prompt="你是一个有帮助的 AI 助手",
        model_type="deepseek",
        model_name="deepseek-chat"
    )
    db_session.add(agent)
    db_session.commit()
    db_session.refresh(agent)
    
    session = ChatSession(agent_id=agent.id)
    db_session.add(session)
    db_session.commit()
    db_session.refresh(session)
    
    # 用户消息
    user_msg = ChatMessage(
        session_id=session.id,
        role="user",
        content="你好"
    )
    
    # AI 回复
    assistant_msg = ChatMessage(
        session_id=session.id,
        role="assistant",
        content="你好！有什么可以帮助你的吗？"
    )
    
    db_session.add_all([user_msg, assistant_msg])
    db_session.commit()
    
    # 查询会话消息
    result = db_session.execute(
        select(ChatMessage)
        .where(ChatMessage.session_id == session.id)
        .order_by(ChatMessage.created_at)
    )
    messages = result.scalars().all()
    
    assert len(messages) == 2
    assert messages[0].role == "user"
    assert messages[0].content == "你好"
    assert messages[1].role == "assistant"


def test_tool_call_message(db_session):
    """测试工具调用消息"""
    agent = Agent(
        name="测试助手",
        system_prompt="你是一个有帮助的 AI 助手",
        model_type="deepseek",
        model_name="deepseek-chat"
    )
    db_session.add(agent)
    db_session.commit()
    db_session.refresh(agent)
    
    session = ChatSession(agent_id=agent.id)
    db_session.add(session)
    db_session.commit()
    db_session.refresh(session)
    
    # AI 发起工具调用
    tool_call_msg = ChatMessage(
        session_id=session.id,
        role="assistant",
        content="",
        tool_calls=[{
            "id": "call_123",
            "type": "function",
            "function": {
                "name": "knowledge_query",
                "arguments": '{"kb_id": "kb-123", "query": "Go 接口"}'
            }
        }]
    )
    
    # 工具返回结果
    tool_result_msg = ChatMessage(
        session_id=session.id,
        role="tool",
        content="Go 语言的接口是...",
        tool_call_id="call_123"
    )
    
    db_session.add_all([tool_call_msg, tool_result_msg])
    db_session.commit()
    
    # 验证
    result = db_session.execute(
        select(ChatMessage).where(ChatMessage.session_id == session.id)
    )
    messages = result.scalars().all()
    
    assert len(messages) == 2
    assert messages[0].tool_calls is not None
    assert messages[0].tool_calls[0]["function"]["name"] == "knowledge_query"
    assert messages[1].role == "tool"
    assert messages[1].tool_call_id == "call_123"


def test_cascade_delete_agent(db_session):
    """测试级联删除 Agent"""
    agent = Agent(
        name="测试助手",
        system_prompt="你是一个有帮助的 AI 助手",
        model_type="deepseek",
        model_name="deepseek-chat"
    )
    db_session.add(agent)
    db_session.commit()
    db_session.refresh(agent)
    
    session = ChatSession(agent_id=agent.id)
    db_session.add(session)
    db_session.commit()
    db_session.refresh(session)
    
    message = ChatMessage(
        session_id=session.id,
        role="user",
        content="测试消息"
    )
    db_session.add(message)
    db_session.commit()
    
    session_id = session.id
    message_id = message.id
    
    # 删除 Agent
    db_session.delete(agent)
    db_session.commit()
    
    # 验证 Session 和 Message 都被删除
    session_result = db_session.execute(
        select(ChatSession).where(ChatSession.id == session_id)
    )
    assert session_result.scalar_one_or_none() is None
    
    message_result = db_session.execute(
        select(ChatMessage).where(ChatMessage.id == message_id)
    )
    assert message_result.scalar_one_or_none() is None


def test_agent_session_relationship(db_session):
    """测试 Agent 与 Session 的关系"""
    agent = Agent(
        name="测试助手",
        system_prompt="你是一个有帮助的 AI 助手",
        model_type="deepseek",
        model_name="deepseek-chat"
    )
    db_session.add(agent)
    db_session.commit()
    db_session.refresh(agent)
    
    session1 = ChatSession(agent_id=agent.id, title="会话1")
    session2 = ChatSession(agent_id=agent.id, title="会话2")
    db_session.add_all([session1, session2])
    db_session.commit()
    
    # 通过关系查询
    result = db_session.execute(
        select(Agent).where(Agent.id == agent.id)
    )
    agent_with_sessions = result.scalar_one()
    db_session.refresh(agent_with_sessions, ["chat_sessions"])
    
    assert len(agent_with_sessions.chat_sessions) == 2
    assert {s.title for s in agent_with_sessions.chat_sessions} == {"会话1", "会话2"}
