from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from sqlalchemy import func
from typing import Optional
from uuid import UUID
import logging

from app.schemas.agent import AgentCreate, AgentUpdate, AgentResponse, AgentListResponse
from app.models import Agent
from app.core.database import get_sync_db

logger = logging.getLogger(__name__)

router = APIRouter()




@router.post("/", response_model=AgentResponse, status_code=201)
def create_agent(
    agent_data: AgentCreate,
    db: Session = Depends(get_sync_db)
):
    """创建 Agent"""
    try:
        agent = Agent(
            name=agent_data.name,
            description=agent_data.description,
            system_prompt=agent_data.system_prompt,
            model_type=agent_data.model_type,
            model_name=agent_data.model_name,
            temperature=agent_data.temperature,
            max_tokens=agent_data.max_tokens,
            max_messages=agent_data.max_messages,
            tools=agent_data.tools or [],
            knowledge_bases=agent_data.knowledge_bases or []
        )
        db.add(agent)
        db.commit()
        db.refresh(agent)
        
        logger.info(f"创建 Agent 成功: {agent.id} - {agent.name}")
        return agent
        
    except Exception as e:
        db.rollback()
        logger.error(f"创建 Agent 失败: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"创建失败: {str(e)}")


@router.get("/", response_model=AgentListResponse)
def list_agents(
    skip: int = Query(0, ge=0, description="跳过记录数"),
    limit: int = Query(100, ge=1, le=1000, description="返回记录数"),
    is_active: Optional[bool] = Query(None, description="是否激活"),
    db: Session = Depends(get_sync_db)
):
    """列出 Agents"""
    try:
        query = db.query(Agent)
        
        if is_active is not None:
            query = query.filter(Agent.is_active == is_active)
        
        # 优化：先获取分页数据，然后单独 count（仅在需要时）
        agents = query.offset(skip).limit(limit).all()
        
        # 如果是第一页且返回数小于 limit，直接计算 total
        if skip == 0 and len(agents) < limit:
            total = len(agents)
        else:
            # 否则执行 count 查询
            total = query.count()
        
        return AgentListResponse(agents=agents, total=total)
        
    except Exception as e:
        logger.error(f"查询 Agents 失败: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"查询失败: {str(e)}")


@router.get("/{agent_id}", response_model=AgentResponse)
def get_agent(
    agent_id: UUID,
    db: Session = Depends(get_sync_db)
):
    """获取 Agent 详情"""
    agent = db.query(Agent).filter(Agent.id == agent_id).first()
    if not agent:
        raise HTTPException(status_code=404, detail=f"Agent {agent_id} 不存在")
    
    return agent


@router.put("/{agent_id}", response_model=AgentResponse)
def update_agent(
    agent_id: UUID,
    agent_data: AgentUpdate,
    db: Session = Depends(get_sync_db)
):
    """更新 Agent"""
    agent = db.query(Agent).filter(Agent.id == agent_id).first()
    if not agent:
        raise HTTPException(status_code=404, detail=f"Agent {agent_id} 不存在")
    
    try:
        # 只更新提供的字段
        update_data = agent_data.model_dump(exclude_unset=True)
        for field, value in update_data.items():
            setattr(agent, field, value)
        
        db.commit()
        db.refresh(agent)
        
        logger.info(f"更新 Agent 成功: {agent.id} - {agent.name}")
        return agent
        
    except Exception as e:
        db.rollback()
        logger.error(f"更新 Agent 失败: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"更新失败: {str(e)}")


@router.delete("/{agent_id}", status_code=204)
def delete_agent(
    agent_id: UUID,
    db: Session = Depends(get_sync_db)
):
    """删除 Agent（级联删除关联的 Sessions 和 Messages）"""
    agent = db.query(Agent).filter(Agent.id == agent_id).first()
    if not agent:
        raise HTTPException(status_code=404, detail=f"Agent {agent_id} 不存在")
    
    try:
        db.delete(agent)
        db.commit()
        
        logger.info(f"删除 Agent 成功: {agent_id}")
        
    except Exception as e:
        db.rollback()
        logger.error(f"删除 Agent 失败: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"删除失败: {str(e)}")
