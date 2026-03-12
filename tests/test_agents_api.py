import pytest
from app.models import Agent


def test_create_agent(api_client, db_session):
    """测试创建 Agent"""
    resp = api_client.post(
        "/api/agents/",
        json={
            "name": "测试助手",
            "system_prompt": "你是一个有帮助的 AI 助手。",
            "model_type": "deepseek",
            "model_name": "deepseek-chat",
            "temperature": 0.7,
            "max_messages": 6,
            "knowledge_bases": ["kb-1", "kb-2"]
        }
    )
    
    assert resp.status_code == 201
    data = resp.json()
    assert data["name"] == "测试助手"
    assert data["model_type"] == "deepseek"
    assert data["is_active"] is True
    assert "id" in data
    assert "created_at" in data


def test_create_agent_invalid_model_type(api_client):
    """测试创建 Agent - 无效模型类型"""
    resp = api_client.post(
        "/api/agents/",
        json={
            "name": "测试",
            "system_prompt": "测试",
            "model_type": "invalid",
            "model_name": "test"
        }
    )
    
    assert resp.status_code == 422  # Validation error


def test_list_agents(api_client, db_session):
    """测试列出 Agents"""
    # 创建几个 Agent
    for i in range(3):
        agent = Agent(
            name=f"助手{i}",
            system_prompt="测试",
            model_type="deepseek",
            model_name="deepseek-chat"
        )
        db_session.add(agent)
    db_session.commit()
    
    resp = api_client.get("/api/agents/")
    
    assert resp.status_code == 200
    data = resp.json()
    assert data["total"] >= 3
    assert len(data["agents"]) >= 3


def test_list_agents_with_pagination(api_client, db_session):
    """测试分页列出 Agents"""
    # 创建多个 Agent
    for i in range(5):
        agent = Agent(
            name=f"助手{i}",
            system_prompt="测试",
            model_type="deepseek",
            model_name="deepseek-chat"
        )
        db_session.add(agent)
    db_session.commit()
    
    resp = api_client.get("/api/agents/?skip=2&limit=2")
    
    assert resp.status_code == 200
    data = resp.json()
    assert len(data["agents"]) == 2


def test_list_agents_filter_by_active(api_client, db_session):
    """测试按激活状态过滤"""
    agent_active = Agent(
        name="激活的",
        system_prompt="测试",
        model_type="deepseek",
        model_name="deepseek-chat",
        is_active=True
    )
    agent_inactive = Agent(
        name="未激活的",
        system_prompt="测试",
        model_type="deepseek",
        model_name="deepseek-chat",
        is_active=False
    )
    db_session.add_all([agent_active, agent_inactive])
    db_session.commit()
    
    resp = api_client.get("/api/agents/?is_active=true")
    
    assert resp.status_code == 200
    data = resp.json()
    assert all(agent["is_active"] for agent in data["agents"])


def test_get_agent(api_client, db_session):
    """测试获取 Agent 详情"""
    agent = Agent(
        name="测试助手",
        system_prompt="测试",
        model_type="deepseek",
        model_name="deepseek-chat"
    )
    db_session.add(agent)
    db_session.commit()
    db_session.refresh(agent)
    
    resp = api_client.get(f"/api/agents/{agent.id}")
    
    assert resp.status_code == 200
    data = resp.json()
    assert data["id"] == str(agent.id)
    assert data["name"] == "测试助手"


def test_get_agent_not_found(api_client):
    """测试获取不存在的 Agent"""
    resp = api_client.get("/api/agents/00000000-0000-0000-0000-000000000000")
    
    assert resp.status_code == 404


def test_update_agent(api_client, db_session):
    """测试更新 Agent"""
    agent = Agent(
        name="旧名称",
        system_prompt="旧提示词",
        model_type="deepseek",
        model_name="deepseek-chat",
        temperature=0.5
    )
    db_session.add(agent)
    db_session.commit()
    db_session.refresh(agent)
    
    resp = api_client.put(
        f"/api/agents/{agent.id}",
        json={
            "name": "新名称",
            "temperature": 0.9
        }
    )
    
    assert resp.status_code == 200
    data = resp.json()
    assert data["name"] == "新名称"
    assert data["temperature"] == 0.9
    assert data["system_prompt"] == "旧提示词"  # 未修改的字段保持


def test_update_agent_not_found(api_client):
    """测试更新不存在的 Agent"""
    resp = api_client.put(
        "/api/agents/00000000-0000-0000-0000-000000000000",
        json={"name": "测试"}
    )
    
    assert resp.status_code == 404


def test_delete_agent(api_client, db_session):
    """测试删除 Agent"""
    agent = Agent(
        name="要删除的",
        system_prompt="测试",
        model_type="deepseek",
        model_name="deepseek-chat"
    )
    db_session.add(agent)
    db_session.commit()
    db_session.refresh(agent)
    
    agent_id = agent.id
    
    resp = api_client.delete(f"/api/agents/{agent_id}")
    
    assert resp.status_code == 204
    
    # 验证已删除
    deleted_agent = db_session.query(Agent).filter(Agent.id == agent_id).first()
    assert deleted_agent is None


def test_delete_agent_not_found(api_client):
    """测试删除不存在的 Agent"""
    resp = api_client.delete("/api/agents/00000000-0000-0000-0000-000000000000")
    
    assert resp.status_code == 404
