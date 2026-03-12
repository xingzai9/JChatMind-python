import pytest
from app.models import Agent, ChatSession, ChatMessage


def test_list_agent_sessions(api_client, db_session):
    """测试列出 Agent 的所有会话"""
    # 创建 Agent
    agent = Agent(
        name="测试助手",
        system_prompt="测试",
        model_type="deepseek",
        model_name="deepseek-chat"
    )
    db_session.add(agent)
    db_session.commit()
    db_session.refresh(agent)
    
    # 创建会话
    for i in range(3):
        session = ChatSession(agent_id=agent.id, title=f"会话{i}")
        db_session.add(session)
    db_session.commit()
    
    resp = api_client.get(f"/api/sessions/agent/{agent.id}")
    
    assert resp.status_code == 200
    data = resp.json()
    assert data["total"] == 3
    assert len(data["sessions"]) == 3


def test_list_agent_sessions_with_message_count(api_client, db_session):
    """测试会话列表包含消息数量"""
    agent = Agent(
        name="测试助手",
        system_prompt="测试",
        model_type="deepseek",
        model_name="deepseek-chat"
    )
    db_session.add(agent)
    db_session.commit()
    db_session.refresh(agent)
    
    session = ChatSession(agent_id=agent.id, title="测试会话")
    db_session.add(session)
    db_session.commit()
    db_session.refresh(session)
    
    # 添加消息
    for i in range(5):
        msg = ChatMessage(
            session_id=session.id,
            role="user" if i % 2 == 0 else "assistant",
            content=f"消息{i}"
        )
        db_session.add(msg)
    db_session.commit()
    
    resp = api_client.get(f"/api/sessions/agent/{agent.id}")
    
    assert resp.status_code == 200
    data = resp.json()
    assert data["sessions"][0]["message_count"] == 5


def test_get_session(api_client, db_session):
    """测试获取会话详情"""
    agent = Agent(
        name="测试助手",
        system_prompt="测试",
        model_type="deepseek",
        model_name="deepseek-chat"
    )
    db_session.add(agent)
    db_session.commit()
    
    session = ChatSession(
        agent_id=agent.id,
        title="测试会话",
        meta={"key": "value"}
    )
    db_session.add(session)
    db_session.commit()
    db_session.refresh(session)
    
    resp = api_client.get(f"/api/sessions/{session.id}")
    
    assert resp.status_code == 200
    data = resp.json()
    assert data["id"] == str(session.id)
    assert data["title"] == "测试会话"
    assert data["metadata"]["key"] == "value"
    assert data["message_count"] == 0


def test_get_session_not_found(api_client):
    """测试获取不存在的会话"""
    resp = api_client.get("/api/sessions/00000000-0000-0000-0000-000000000000")
    
    assert resp.status_code == 404


def test_update_session(api_client, db_session):
    """测试更新会话"""
    agent = Agent(
        name="测试助手",
        system_prompt="测试",
        model_type="deepseek",
        model_name="deepseek-chat"
    )
    db_session.add(agent)
    db_session.commit()
    
    session = ChatSession(agent_id=agent.id, title="旧标题")
    db_session.add(session)
    db_session.commit()
    db_session.refresh(session)
    
    resp = api_client.put(
        f"/api/sessions/{session.id}",
        json={
            "title": "新标题",
            "metadata": {"updated": True}
        }
    )
    
    assert resp.status_code == 200
    data = resp.json()
    assert data["title"] == "新标题"
    assert data["metadata"]["updated"] is True


def test_delete_session(api_client, db_session):
    """测试删除会话"""
    agent = Agent(
        name="测试助手",
        system_prompt="测试",
        model_type="deepseek",
        model_name="deepseek-chat"
    )
    db_session.add(agent)
    db_session.commit()
    
    session = ChatSession(agent_id=agent.id, title="要删除的会话")
    db_session.add(session)
    db_session.commit()
    db_session.refresh(session)
    
    # 添加消息
    msg = ChatMessage(session_id=session.id, role="user", content="测试")
    db_session.add(msg)
    db_session.commit()
    
    session_id = session.id
    
    resp = api_client.delete(f"/api/sessions/{session_id}")
    
    assert resp.status_code == 204
    
    # 验证已删除（包括消息）
    deleted_session = db_session.query(ChatSession).filter(ChatSession.id == session_id).first()
    assert deleted_session is None
    
    deleted_msg = db_session.query(ChatMessage).filter(ChatMessage.session_id == session_id).first()
    assert deleted_msg is None


def test_delete_session_not_found(api_client):
    """测试删除不存在的会话"""
    resp = api_client.delete("/api/sessions/00000000-0000-0000-0000-000000000000")
    
    assert resp.status_code == 404


def test_list_sessions_pagination(api_client, db_session):
    """测试会话列表分页"""
    agent = Agent(
        name="测试助手",
        system_prompt="测试",
        model_type="deepseek",
        model_name="deepseek-chat"
    )
    db_session.add(agent)
    db_session.commit()
    db_session.refresh(agent)
    
    # 创建 10 个会话
    for i in range(10):
        session = ChatSession(agent_id=agent.id, title=f"会话{i}")
        db_session.add(session)
    db_session.commit()
    
    resp = api_client.get(f"/api/sessions/agent/{agent.id}?skip=3&limit=4")
    
    assert resp.status_code == 200
    data = resp.json()
    assert data["total"] == 10
    assert len(data["sessions"]) == 4
