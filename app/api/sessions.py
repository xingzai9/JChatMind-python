from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from sqlalchemy import func
from typing import Optional
from uuid import UUID
import logging

from app.schemas.session import SessionResponse, SessionListResponse, SessionUpdateRequest
from app.models import ChatSession, ChatMessage
from app.core.database import get_sync_db

logger = logging.getLogger(__name__)

router = APIRouter()




@router.get("/", response_model=SessionListResponse)
def list_all_sessions(
    skip: int = Query(0, ge=0, description="跳过记录数"),
    limit: int = Query(100, ge=1, le=1000, description="返回记录数"),
    db: Session = Depends(get_sync_db)
):
    """列出所有会话"""
    try:
        # 查询所有会话，并统计消息数量
        query = (
            db.query(
                ChatSession,
                func.count(ChatMessage.id).label('message_count')
            )
            .outerjoin(ChatMessage, ChatSession.id == ChatMessage.session_id)
            .group_by(ChatSession.id)
        )
        
        total = db.query(ChatSession).count()
        
        results = query.order_by(ChatSession.updated_at.desc()).offset(skip).limit(limit).all()
        
        # 构建响应
        sessions = []
        for session, msg_count in results:
            session_dict = {
                'id': session.id,
                'agent_id': session.agent_id,
                'title': session.title,
                'metadata': session.meta,
                'created_at': session.created_at,
                'updated_at': session.updated_at,
                'message_count': msg_count or 0
            }
            sessions.append(SessionResponse(**session_dict))
        
        return SessionListResponse(sessions=sessions, total=total)
        
    except Exception as e:
        logger.error(f"查询所有会话失败: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"查询失败: {str(e)}")


@router.get("/agent/{agent_id}", response_model=SessionListResponse)
def list_agent_sessions(
    agent_id: UUID,
    skip: int = Query(0, ge=0, description="跳过记录数"),
    limit: int = Query(100, ge=1, le=1000, description="返回记录数"),
    db: Session = Depends(get_sync_db)
):
    """列出指定 Agent 的所有会话"""
    try:
        # 查询会话，并统计消息数量
        query = (
            db.query(
                ChatSession,
                func.count(ChatMessage.id).label('message_count')
            )
            .outerjoin(ChatMessage, ChatSession.id == ChatMessage.session_id)
            .filter(ChatSession.agent_id == agent_id)
            .group_by(ChatSession.id)
        )
        
        total = db.query(ChatSession).filter(ChatSession.agent_id == agent_id).count()
        
        results = query.order_by(ChatSession.updated_at.desc()).offset(skip).limit(limit).all()
        
        # 构建响应
        sessions = []
        for session, msg_count in results:
            session_dict = {
                'id': session.id,
                'agent_id': session.agent_id,
                'title': session.title,
                'metadata': session.meta,
                'created_at': session.created_at,
                'updated_at': session.updated_at,
                'message_count': msg_count or 0
            }
            sessions.append(SessionResponse(**session_dict))
        
        return SessionListResponse(sessions=sessions, total=total)
        
    except Exception as e:
        logger.error(f"查询会话列表失败: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"查询失败: {str(e)}")


@router.get("/{session_id}", response_model=SessionResponse)
def get_session(
    session_id: UUID,
    db: Session = Depends(get_sync_db)
):
    """获取会话详情"""
    session = db.query(ChatSession).filter(ChatSession.id == session_id).first()
    if not session:
        raise HTTPException(status_code=404, detail=f"会话 {session_id} 不存在")
    
    # 统计消息数量
    msg_count = db.query(func.count(ChatMessage.id)).filter(
        ChatMessage.session_id == session_id
    ).scalar()
    
    session_dict = {
        'id': session.id,
        'agent_id': session.agent_id,
        'title': session.title,
        'metadata': session.meta,
        'created_at': session.created_at,
        'updated_at': session.updated_at,
        'message_count': msg_count or 0
    }
    
    return SessionResponse(**session_dict)


@router.put("/{session_id}", response_model=SessionResponse)
def update_session(
    session_id: UUID,
    update_data: SessionUpdateRequest,
    db: Session = Depends(get_sync_db)
):
    """更新会话（标题、元数据）"""
    session = db.query(ChatSession).filter(ChatSession.id == session_id).first()
    if not session:
        raise HTTPException(status_code=404, detail=f"会话 {session_id} 不存在")
    
    try:
        # 只更新提供的字段
        if update_data.title is not None:
            session.title = update_data.title
        if update_data.metadata is not None:
            session.meta = update_data.metadata
        
        db.commit()
        db.refresh(session)
        
        # 统计消息数量
        msg_count = db.query(func.count(ChatMessage.id)).filter(
            ChatMessage.session_id == session_id
        ).scalar()
        
        session_dict = {
            'id': session.id,
            'agent_id': session.agent_id,
            'title': session.title,
            'metadata': session.meta,
            'created_at': session.created_at,
            'updated_at': session.updated_at,
            'message_count': msg_count or 0
        }
        
        logger.info(f"更新会话成功: {session_id}")
        return SessionResponse(**session_dict)
        
    except Exception as e:
        db.rollback()
        logger.error(f"更新会话失败: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"更新失败: {str(e)}")


@router.delete("/{session_id}", status_code=204)
def delete_session(
    session_id: UUID,
    db: Session = Depends(get_sync_db)
):
    """删除会话（级联删除所有消息）"""
    session = db.query(ChatSession).filter(ChatSession.id == session_id).first()
    if not session:
        raise HTTPException(status_code=404, detail=f"会话 {session_id} 不存在")
    
    try:
        db.delete(session)
        db.commit()
        
        logger.info(f"删除会话成功: {session_id}")
        
    except Exception as e:
        db.rollback()
        logger.error(f"删除会话失败: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"删除失败: {str(e)}")
