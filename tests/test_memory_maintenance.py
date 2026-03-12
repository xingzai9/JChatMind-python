"""
记忆维护功能测试：
  1. episodic_retrieval 访问统计更新
  2. _store_semantic 相似度去重
  3. prune_decayed 清理过期情节记忆
  4. MemoryMaintenanceScheduler 启动/停止
"""
import time
import math
from datetime import datetime, timedelta
from unittest.mock import patch, MagicMock
from uuid import uuid4

import pytest

from app.models.memory import SemanticMemory, EpisodicMemory
from app.models.agent import Agent
from app.services.memory.long_term_memory_service import LongTermMemoryService
from app.services.memory.memory_scheduler import MemoryMaintenanceScheduler


# ──────────────────────────────────────────────
# Fixtures
# ──────────────────────────────────────────────

@pytest.fixture
def mock_llm():
    return MagicMock()


@pytest.fixture
def test_agent(db_session):
    agent = Agent(
        name="测试Agent",
        system_prompt="测试",
        model_type="deepseek",
        model_name="deepseek-chat",
        temperature=0.7,
        max_messages=6,
    )
    db_session.add(agent)
    db_session.commit()
    db_session.refresh(agent)
    return agent


@pytest.fixture
def lt_svc(db_session, mock_llm):
    svc = LongTermMemoryService(mock_llm, db_session)
    svc._rag = MagicMock()
    svc._rag.embed.return_value = [0.1] * 1024
    return svc


def _make_semantic(db, agent, user_id, topic, content, importance=8.0, emb=None):
    """helper: 直接插入一条语义记忆"""
    mem = SemanticMemory(
        agent_id=agent.id,
        user_id=user_id,
        memory_type="knowledge",
        topic=topic,
        content=content,
        embedding=emb or [0.1] * 1024,
        importance_score=importance,
        access_count=0,
    )
    db.add(mem)
    db.commit()
    db.refresh(mem)
    return mem


def _make_episodic(db, agent, user_id, summary, importance=8.0,
                   days_old=0, emb=None):
    """helper: 直接插入一条情节记忆"""
    from sqlalchemy import text as sa_text
    mem = EpisodicMemory(
        agent_id=agent.id,
        user_id=user_id,
        event_summary=summary,
        embedding=emb or [0.1] * 1024,
        importance_score=importance,
        decay_score=importance,
        event_time=datetime.utcnow() - timedelta(days=days_old),
    )
    db.add(mem)
    db.flush()  # 获取 id
    # 直接更新 created_at 使其反映创建日期
    if days_old > 0:
        db.execute(
            sa_text("UPDATE episodic_memory SET created_at = :ts WHERE id = :id"),
            {"ts": datetime.utcnow() - timedelta(days=days_old), "id": mem.id}
        )
    db.commit()
    db.refresh(mem)
    return mem


# ──────────────────────────────────────────────
# 1. episodic_retrieval 访问统计
# ──────────────────────────────────────────────

def test_episodic_access_count_increments(db_session, lt_svc, test_agent):
    """episodic_retrieval 返回结果后 access_count 应 +1"""
    user_id = "test_user"
    mem = _make_episodic(db_session, test_agent, user_id, "测试事件")
    assert mem.access_count == 0

    results = lt_svc.episodic_retrieval("测试", test_agent.id, user_id, top_k=5)

    db_session.refresh(mem)
    assert len(results) >= 1
    assert mem.access_count == 1
    assert mem.last_accessed_at is not None


def test_episodic_access_count_increments_multiple(db_session, lt_svc, test_agent):
    """多次检索 access_count 累加"""
    user_id = "test_user2"
    mem = _make_episodic(db_session, test_agent, user_id, "累加测试事件")

    for _ in range(3):
        lt_svc.episodic_retrieval("测试", test_agent.id, user_id, top_k=5)

    db_session.refresh(mem)
    assert mem.access_count == 3


# ──────────────────────────────────────────────
# 2. semantic_search 访问统计（已有，回归测试）
# ──────────────────────────────────────────────

def test_semantic_access_count_increments(db_session, lt_svc, test_agent):
    """semantic_search 返回结果后 access_count 应 +1"""
    user_id = "test_user_sem"
    mem = _make_semantic(db_session, test_agent, user_id, "Python技能", "用户熟悉 Python")
    assert mem.access_count == 0

    lt_svc.semantic_search("Python", test_agent.id, user_id, top_k=5)

    db_session.refresh(mem)
    assert mem.access_count == 1
    assert mem.last_accessed_at is not None


# ──────────────────────────────────────────────
# 3. _store_semantic 去重
# ──────────────────────────────────────────────

def test_store_semantic_dedup_updates_existing(db_session, lt_svc, test_agent):
    """相似度 >= 0.92 时应更新已有记忆而非新建"""
    user_id = "dedup_user"

    existing = _make_semantic(
        db_session, test_agent, user_id,
        topic="Python偏好", content="用户喜欢Python", importance=7.0,
        emb=[0.1] * 1024,
    )
    initial_count = db_session.query(SemanticMemory).filter(
        SemanticMemory.agent_id == test_agent.id
    ).count()

    lt_svc._rag.embed.return_value = [0.1] * 1024

    items = [{
        "memory_type": "preference",
        "topic": "Python高手",
        "content": "用户精通Python编程",
        "importance_score": 9.0,
    }]
    lt_svc._store_semantic(items, test_agent.id, user_id, source_session_id=None)
    db_session.commit()

    after_count = db_session.query(SemanticMemory).filter(
        SemanticMemory.agent_id == test_agent.id
    ).count()

    assert after_count == initial_count
    db_session.refresh(existing)
    assert existing.importance_score == 9.0
    assert existing.topic == "Python高手"


def test_store_semantic_no_dedup_different_content(db_session, lt_svc, test_agent):
    """相似度低时应新建而非更新"""
    user_id = "nodedup_user"

    _make_semantic(
        db_session, test_agent, user_id,
        topic="Python", content="用户喜欢Python",
        emb=[1.0] + [0.0] * 1023,
    )
    lt_svc._rag.embed.return_value = [0.0] * 1023 + [1.0]

    items = [{
        "memory_type": "knowledge",
        "topic": "Java",
        "content": "用户也懂Java",
        "importance_score": 7.5,
    }]
    lt_svc._store_semantic(items, test_agent.id, user_id, source_session_id=None)
    db_session.commit()

    count = db_session.query(SemanticMemory).filter(
        SemanticMemory.agent_id == test_agent.id
    ).count()
    assert count == 2


# ──────────────────────────────────────────────
# 4. prune_decayed 清理
# ──────────────────────────────────────────────

def test_prune_decayed_removes_old_low_score(db_session, lt_svc, test_agent):
    """90天前的低 importance 记忆 decay_score 应低于阈值，被清理"""
    user_id = "prune_user"

    old_mem = _make_episodic(
        db_session, test_agent, user_id, "很久以前的事件",
        importance=5.0, days_old=90
    )

    pruned = lt_svc.prune_decayed(test_agent.id, user_id)

    assert pruned >= 1
    still_exists = db_session.get(EpisodicMemory, old_mem.id)
    assert still_exists is None


def test_prune_decayed_keeps_fresh_memories(db_session, lt_svc, test_agent):
    """刚创建的高 importance 记忆不应被清理"""
    user_id = "keep_user"

    fresh = _make_episodic(
        db_session, test_agent, user_id, "刚发生的重要事件",
        importance=9.0, days_old=0
    )

    lt_svc.prune_decayed(test_agent.id, user_id)

    still_exists = db_session.get(EpisodicMemory, fresh.id)
    assert still_exists is not None


# ──────────────────────────────────────────────
# 5. MemoryMaintenanceScheduler
# ──────────────────────────────────────────────

def test_scheduler_start_stop():
    """调度器能正常启动和停止"""
    scheduler = MemoryMaintenanceScheduler(interval_hours=24)
    scheduler.start()
    assert scheduler._running is True
    assert scheduler._timer is not None
    scheduler.stop()
    assert scheduler._running is False
    assert scheduler._timer is None


def test_scheduler_singleton():
    """get_instance 返回同一实例"""
    s1 = MemoryMaintenanceScheduler.get_instance()
    s2 = MemoryMaintenanceScheduler.get_instance()
    assert s1 is s2
    # 清理，避免影响其他测试
    MemoryMaintenanceScheduler._instance = None


def test_scheduler_no_double_start():
    """重复调用 start 不产生多个 timer"""
    scheduler = MemoryMaintenanceScheduler(interval_hours=24)
    scheduler.start()
    timer_before = scheduler._timer
    scheduler.start()  # 第二次 start 应该被忽略
    assert scheduler._timer is timer_before
    scheduler.stop()
