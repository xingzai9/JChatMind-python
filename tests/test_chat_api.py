from unittest.mock import patch

from fastapi.testclient import TestClient

from app.main import app
from app.models import Agent, ChatSession


def _create_agent(db_session, name: str = "测试助手") -> Agent:
    agent = Agent(
        name=name,
        system_prompt="你是一个有帮助的 AI 助手。",
        model_type="deepseek",
        model_name="deepseek-chat",
        temperature=0.7,
        max_messages=6,
        knowledge_bases=["test-kb-id"],
    )
    db_session.add(agent)
    db_session.commit()
    db_session.refresh(agent)
    return agent


def test_chat_create_new_session(api_client, db_session):
    agent = _create_agent(db_session)

    with patch("app.api.chat.JChatMindAgent.chat", return_value="你好，我是测试回复"):
        resp = api_client.post(
            "/api/chat/",
            data={
                "agent_id": str(agent.id),
                "message": "你好",
            },
        )

    assert resp.status_code == 200
    data = resp.json()
    assert data["message"] == "你好，我是测试回复"
    assert data["session_id"]

    session = db_session.query(ChatSession).filter(ChatSession.id == data["session_id"]).first()
    assert session is not None
    assert str(session.agent_id) == str(agent.id)


def test_chat_continue_existing_session(api_client, db_session):
    agent = _create_agent(db_session)

    session = ChatSession(agent_id=agent.id, title="测试会话")
    db_session.add(session)
    db_session.commit()
    db_session.refresh(session)

    with patch("app.api.chat.JChatMindAgent.chat", return_value="继续会话回复"):
        resp = api_client.post(
            "/api/chat/",
            data={
                "agent_id": str(agent.id),
                "session_id": str(session.id),
                "message": "继续",
            },
        )

    assert resp.status_code == 200
    data = resp.json()
    assert data["session_id"] == str(session.id)
    assert data["message"] == "继续会话回复"


def test_chat_session_not_belong_to_agent(api_client, db_session):
    agent_a = _create_agent(db_session, name="助手A")
    agent_b = _create_agent(db_session, name="助手B")

    session_b = ChatSession(agent_id=agent_b.id, title="B的会话")
    db_session.add(session_b)
    db_session.commit()
    db_session.refresh(session_b)

    resp = api_client.post(
        "/api/chat/",
        data={
            "agent_id": str(agent_a.id),
            "session_id": str(session_b.id),
            "message": "测试",
        },
    )

    assert resp.status_code == 400
    assert "会话不属于该 Agent" in resp.json()["detail"]


def test_get_chat_history(api_client, db_session):
    agent = _create_agent(db_session)

    session = ChatSession(agent_id=agent.id, title="历史会话")
    db_session.add(session)
    db_session.commit()
    db_session.refresh(session)

    mocked_history = [
        {"id": "1", "role": "user", "content": "你好", "created_at": "2026-01-01T00:00:00"},
        {"id": "2", "role": "assistant", "content": "你好！", "created_at": "2026-01-01T00:00:01"},
    ]

    with patch("app.api.chat.JChatMindAgent.get_history", return_value=mocked_history):
        resp = api_client.get(f"/api/chat/{session.id}/history")

    assert resp.status_code == 200
    data = resp.json()
    assert data["session_id"] == str(session.id)
    assert data["total"] == 2
    assert data["messages"][0]["role"] == "user"
    assert data["messages"][1]["role"] == "assistant"
