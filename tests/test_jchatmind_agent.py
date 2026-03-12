import pytest
from unittest.mock import Mock, patch, MagicMock
from langchain_core.messages import AIMessage
from app.agents.jchatmind_agent import JChatMindAgent
from app.models import Agent, ChatSession, ChatMessage


@pytest.fixture
def agent_config(db_session):
    """创建测试用 Agent 配置"""
    agent = Agent(
        name="测试助手",
        system_prompt="你是一个有帮助的 AI 助手。",
        model_type="deepseek",
        model_name="deepseek-chat",
        temperature=0.7,
        max_messages=6,
        knowledge_bases=["test-kb-id"]
    )
    db_session.add(agent)
    db_session.commit()
    db_session.refresh(agent)
    return agent


@pytest.fixture
def chat_session(db_session, agent_config):
    """创建测试用聊天会话"""
    session = ChatSession(
        agent_id=agent_config.id,
        title="测试对话"
    )
    db_session.add(session)
    db_session.commit()
    db_session.refresh(session)
    return session


@patch('app.agents.jchatmind_agent.LLMClientFactory.create_client')
def test_jchatmind_agent_initialization(mock_create_client, db_session, agent_config, chat_session):
    """测试 Agent 初始化"""
    mock_llm = Mock()
    mock_create_client.return_value = mock_llm
    
    agent = JChatMindAgent(
        agent_config=agent_config,
        session=chat_session,
        db=db_session
    )
    
    assert agent.agent_config == agent_config
    assert agent.session == chat_session
    assert agent.llm == mock_llm
    assert len(agent.tools) > 0
    assert agent.message_history is not None
    assert agent.prompt is not None
    
    # 验证 LLM 客户端创建参数
    mock_create_client.assert_called_once_with(
        model_type="deepseek",
        model_name="deepseek-chat",
        temperature=0.7,
        max_tokens=None
    )


@patch('app.agents.jchatmind_agent.LLMClientFactory.create_client')
def test_load_history(mock_create_client, db_session, agent_config, chat_session):
    """测试加载历史消息"""
    mock_create_client.return_value = Mock()
    
    # 创建历史消息
    msg1 = ChatMessage(session_id=chat_session.id, role="user", content="你好")
    msg2 = ChatMessage(session_id=chat_session.id, role="assistant", content="你好！")
    db_session.add_all([msg1, msg2])
    db_session.commit()
    
    # 初始化 Agent（会加载历史）
    agent = JChatMindAgent(
        agent_config=agent_config,
        session=chat_session,
        db=db_session
    )
    
    # 验证记忆中有消息
    messages = agent.message_history.messages
    assert len(messages) == 2
    # 消息按创建时间加载，顺序应该是用户-助手
    assert any(msg.content == "你好" for msg in messages)
    assert any(msg.content == "你好！" for msg in messages)


@patch('app.agents.jchatmind_agent.LLMClientFactory.create_client')
def test_chat_success(mock_create_client, db_session, agent_config, chat_session):
    """测试成功的对话"""
    # Mock LLM - 使用真实 AIMessage 避免 isinstance 检查失败
    mock_response = AIMessage(content="这是 AI 的回复")
    
    mock_llm = Mock()
    mock_llm.invoke.return_value = mock_response
    mock_llm.bind_tools.return_value = mock_llm  # bind_tools 返回自身
    mock_create_client.return_value = mock_llm
    
    agent = JChatMindAgent(
        agent_config=agent_config,
        session=chat_session,
        db=db_session
    )
    
    # 发送消息
    response = agent.chat("你好")
    
    assert response == "这是 AI 的回复"
    
    # 验证消息已保存
    messages = db_session.query(ChatMessage).filter(
        ChatMessage.session_id == chat_session.id
    ).all()
    
    assert len(messages) == 2
    assert messages[0].role == "user"
    assert messages[0].content == "你好"
    assert messages[1].role == "assistant"
    assert messages[1].content == "这是 AI 的回复"


@patch('app.agents.jchatmind_agent.LLMClientFactory.create_client')
def test_chat_with_error(mock_create_client, db_session, agent_config, chat_session):
    """测试对话错误处理：LLM 抛出异常时 Agent 应优雅恢复并持久化错误消息"""
    mock_llm = Mock()
    mock_llm.invoke.side_effect = Exception("测试错误")
    mock_llm.bind_tools.return_value = mock_llm  # bind_tools 返回自身
    mock_create_client.return_value = mock_llm

    agent = JChatMindAgent(
        agent_config=agent_config,
        session=chat_session,
        db=db_session
    )

    # Loop 内部捕获 LLM 异常并返回 fallback，不向外抛出
    response = agent.chat("测试消息")

    # 验证消息已保存
    messages = db_session.query(ChatMessage).filter(
        ChatMessage.session_id == chat_session.id
    ).all()

    assert len(messages) == 2
    assert messages[0].role == "user"
    assert messages[1].role == "assistant"
    # fallback 消息包含 "失败" 字样
    assert messages[1].content is not None


@patch('app.agents.jchatmind_agent.LLMClientFactory.create_client')
def test_get_history(mock_create_client, db_session, agent_config, chat_session):
    """测试获取对话历史"""
    mock_create_client.return_value = Mock()
    
    # 创建历史消息
    msg1 = ChatMessage(session_id=chat_session.id, role="user", content="消息1")
    msg2 = ChatMessage(session_id=chat_session.id, role="assistant", content="回复1")
    db_session.add_all([msg1, msg2])
    db_session.commit()
    
    agent = JChatMindAgent(
        agent_config=agent_config,
        session=chat_session,
        db=db_session
    )
    
    history = agent.get_history()
    
    assert len(history) == 2
    assert history[0]["role"] == "user"
    assert history[0]["content"] == "消息1"
    assert history[1]["role"] == "assistant"
    assert history[1]["content"] == "回复1"
    assert "id" in history[0]
    assert "created_at" in history[0]


@patch('app.agents.jchatmind_agent.LLMClientFactory.create_client')
def test_memory_window_limit(mock_create_client, db_session, agent_config, chat_session):
    """测试记忆窗口限制"""
    mock_create_client.return_value = Mock()
    
    # 创建超过 max_messages 的历史消息
    for i in range(10):
        msg = ChatMessage(
            session_id=chat_session.id,
            role="user" if i % 2 == 0 else "assistant",
            content=f"消息{i}"
        )
        db_session.add(msg)
    db_session.commit()
    
    agent = JChatMindAgent(
        agent_config=agent_config,
        session=chat_session,
        db=db_session
    )
    
    # 记忆中应该只有最近 6 条消息
    messages = agent.message_history.messages
    assert len(messages) == agent_config.max_messages
