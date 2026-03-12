from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from sqlalchemy import func
from typing import Optional, List
from uuid import UUID
import logging

from app.core.database import get_sync_db
from app.models.memory import WorkingMemory, SemanticMemory, EpisodicMemory

logger = logging.getLogger(__name__)

router = APIRouter()


# ──────────────────────────────────────────────
# Working Memory
# ──────────────────────────────────────────────

@router.get("/working/{session_id}")
def get_working_memory(
    session_id: UUID,
    db: Session = Depends(get_sync_db)
):
    """获取指定会话的工作记忆（Markdown 文档）"""
    wm = (
        db.query(WorkingMemory)
        .filter(WorkingMemory.session_id == session_id)
        .order_by(WorkingMemory.updated_at.desc())
        .first()
    )
    if not wm:
        raise HTTPException(status_code=404, detail=f"会话 {session_id} 暂无工作记忆")

    return {
        "session_id": str(wm.session_id),
        "content": wm.content,
        "message_count": wm.message_count,
        "version": wm.version,
        "created_at": wm.created_at.isoformat() if wm.created_at else None,
        "updated_at": wm.updated_at.isoformat() if wm.updated_at else None,
    }


# ──────────────────────────────────────────────
# Semantic Memory
# ──────────────────────────────────────────────

@router.get("/semantic")
def list_semantic_memories(
    agent_id: Optional[UUID] = Query(None, description="过滤指定 Agent"),
    user_id: Optional[str] = Query(None, description="过滤指定用户"),
    topic: Optional[str] = Query(None, description="按主题模糊搜索"),
    skip: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_sync_db)
):
    """列出语义记忆（用户知识、偏好、技能等）"""
    q = db.query(SemanticMemory)
    if agent_id:
        q = q.filter(SemanticMemory.agent_id == agent_id)
    if user_id:
        q = q.filter(SemanticMemory.user_id == user_id)
    if topic:
        q = q.filter(SemanticMemory.topic.ilike(f"%{topic}%"))

    total = q.count()
    items = (
        q.order_by(SemanticMemory.importance_score.desc())
        .offset(skip)
        .limit(limit)
        .all()
    )

    return {
        "total": total,
        "items": [
            {
                "id": str(m.id),
                "agent_id": str(m.agent_id) if m.agent_id else None,
                "user_id": m.user_id,
                "memory_type": m.memory_type,
                "topic": m.topic,
                "content": m.content,
                "importance_score": m.importance_score,
                "source_session_id": m.source_session_id,
                "created_at": m.created_at.isoformat() if m.created_at else None,
            }
            for m in items
        ],
    }


@router.delete("/semantic/{memory_id}", status_code=204)
def delete_semantic_memory(
    memory_id: UUID,
    db: Session = Depends(get_sync_db)
):
    """删除指定语义记忆"""
    m = db.query(SemanticMemory).filter(SemanticMemory.id == memory_id).first()
    if not m:
        raise HTTPException(status_code=404, detail=f"语义记忆 {memory_id} 不存在")
    db.delete(m)
    db.commit()


# ──────────────────────────────────────────────
# Episodic Memory
# ──────────────────────────────────────────────

@router.get("/episodic")
def list_episodic_memories(
    agent_id: Optional[UUID] = Query(None, description="过滤指定 Agent"),
    user_id: Optional[str] = Query(None, description="过滤指定用户"),
    skip: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_sync_db)
):
    """列出情节记忆（按时间倒序）"""
    q = db.query(EpisodicMemory)
    if agent_id:
        q = q.filter(EpisodicMemory.agent_id == agent_id)
    if user_id:
        q = q.filter(EpisodicMemory.user_id == user_id)

    total = q.count()
    items = (
        q.order_by(EpisodicMemory.event_time.desc())
        .offset(skip)
        .limit(limit)
        .all()
    )

    return {
        "total": total,
        "items": [
            {
                "id": str(m.id),
                "agent_id": str(m.agent_id) if m.agent_id else None,
                "user_id": m.user_id,
                "event_summary": m.event_summary,
                "event_detail": m.event_detail,
                "importance_score": m.importance_score,
                "decay_score": m.decay_score,
                "event_time": m.event_time.isoformat() if m.event_time else None,
                "source_session_id": m.source_session_id,
                "created_at": m.created_at.isoformat() if m.created_at else None,
            }
            for m in items
        ],
    }


@router.delete("/episodic/{memory_id}", status_code=204)
def delete_episodic_memory(
    memory_id: UUID,
    db: Session = Depends(get_sync_db)
):
    """删除指定情节记忆"""
    m = db.query(EpisodicMemory).filter(EpisodicMemory.id == memory_id).first()
    if not m:
        raise HTTPException(status_code=404, detail=f"情节记忆 {memory_id} 不存在")
    db.delete(m)
    db.commit()


# ──────────────────────────────────────────────
# Summary stats
# ──────────────────────────────────────────────

@router.get("/stats")
def memory_stats(
    agent_id: Optional[UUID] = Query(None),
    user_id: Optional[str] = Query(None),
    db: Session = Depends(get_sync_db)
):
    """记忆系统统计概览"""
    sem_q = db.query(func.count(SemanticMemory.id))
    epi_q = db.query(func.count(EpisodicMemory.id))
    wm_q = db.query(func.count(WorkingMemory.id))

    if agent_id:
        sem_q = sem_q.filter(SemanticMemory.agent_id == agent_id)
        epi_q = epi_q.filter(EpisodicMemory.agent_id == agent_id)
    if user_id:
        sem_q = sem_q.filter(SemanticMemory.user_id == user_id)
        epi_q = epi_q.filter(EpisodicMemory.user_id == user_id)

    return {
        "semantic_count": sem_q.scalar() or 0,
        "episodic_count": epi_q.scalar() or 0,
        "working_memory_count": wm_q.scalar() or 0,
    }
