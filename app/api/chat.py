from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session
from typing import Optional
import json
from app.schemas.chat import ChatRequest, ChatResponse, ChatHistoryResponse
from app.models import Agent, ChatSession, ChatMessage
from app.agents.jchatmind_agent import JChatMindAgent
from app.core.database import get_sync_db
import logging
import tempfile
import os
from datetime import datetime
import asyncio

logger = logging.getLogger(__name__)

router = APIRouter()




@router.post("/stream")
async def chat_stream(
    agent_id: str = Form(...),
    message: str = Form(...),
    session_id: Optional[str] = Form(None),
    user_id: Optional[str] = Form(None),
    file: Optional[UploadFile] = File(None),
    db: Session = Depends(get_sync_db)
):
    """
    SSE 流式聊天接口
    """
    import tempfile
    import os
    from uuid import UUID
    import asyncio
    
    # 先完整读取文件（避免流式响应时继续接收请求体）
    file_content = None
    file_name = None
    if file:
        file_content = await file.read()
        file_name = file.filename
        logger.info("[文件 ] 上传: %s  %s  %d bytes", file_name, file.content_type, len(file_content))
    
    # 定义异步生成器
    async def generate():
        temp_file_path = None
        try:
            # 获取 Agent
            agent_obj = db.query(Agent).filter(Agent.id == UUID(agent_id)).first()
            if not agent_obj:
                yield f"data: {json.dumps({'type': 'error', 'error': 'Agent not found'}, ensure_ascii=False)}\n\n"
                return
            
            # 获取或创建会话
            if session_id:
                chat_session = db.query(ChatSession).filter(ChatSession.id == UUID(session_id)).first()
                if not chat_session:
                    yield f"data: {json.dumps({'type': 'error', 'error': 'Session not found'}, ensure_ascii=False)}\n\n"
                    return
            else:
                _raw = message.strip()
                _title = (_raw[:28] + "…") if len(_raw) > 28 else (_raw or "新对话")
                chat_session = ChatSession(
                    agent_id=agent_obj.id,
                    title=_title,
                    user_id=user_id
                )
                db.add(chat_session)
                db.commit()
                db.refresh(chat_session)
            
            # 发送 session_id
            yield f"data: {json.dumps({'type': 'session_id', 'session_id': str(chat_session.id)}, ensure_ascii=False)}\n\n"
            
            # 处理文件
            enhanced_message = message
            if file:
                # 使用会话 ID 创建目录，文件保留在会话生命周期内
                session_dir = os.path.join("uploads", str(chat_session.id))
                os.makedirs(session_dir, exist_ok=True)
                
                # 保存文件（使用原始文件名），路径统一为绝对路径
                session_file_path = os.path.abspath(os.path.join(session_dir, file_name))
                with open(session_file_path, "wb") as f:
                    f.write(file_content)
                
                logger.info("[文件 ] 保存至: %s", session_file_path)
                
                # 将文件路径保存到会话元数据
                if chat_session.meta is None:
                    chat_session.meta = {}
                if "uploaded_files" not in chat_session.meta:
                    chat_session.meta["uploaded_files"] = []
                chat_session.meta["uploaded_files"].append({
                    "filename": file_name,
                    "path": session_file_path,
                    "uploaded_at": str(datetime.now())
                })
                db.commit()
                
                # 在消息中附加文件信息（绝对路径，供 python_executor 直接使用）
                enhanced_message = f"{message}\n\n[用户上传了文件: {file_name}，绝对路径: {session_file_path}]"
            
            # 创建 Agent
            agent = JChatMindAgent(agent_obj, chat_session, db, user_id=user_id)
            msg_preview = message[:60] + ("…" if len(message) > 60 else "")
            logger.info("[用户 ] '%s'  (%d字)  session=%s",
                        msg_preview, len(message), str(chat_session.id)[:8])

            # 在线程池中运行同步的 chat_stream
            loop = asyncio.get_event_loop()

            def get_stream_generator():
                return agent.chat_stream(enhanced_message)

            stream_gen = await loop.run_in_executor(None, get_stream_generator)

            # 直接转发结构化事件（AI_THINKING / AI_EXECUTING / tool_result / answer_chunk）
            for event in stream_gen:
                yield f"data: {json.dumps(event, ensure_ascii=False)}\n\n"
                await asyncio.sleep(0)

            # 发送完成标记
            yield f"data: {json.dumps({'type': 'AI_DONE'}, ensure_ascii=False)}\n\n"
            
        except Exception as e:
            logger.error("[流式 ] 错误: %s", e, exc_info=True)
            yield f"data: {json.dumps({'type': 'error', 'error': str(e)}, ensure_ascii=False)}\n\n"
        
        finally:
            # 文件保留在会话目录，不删除（可以后续多轮对话使用）
            pass
    
    return StreamingResponse(
        generate(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no"
        }
    )


@router.post("/", response_model=ChatResponse)
async def chat(
    agent_id: str = Form(...),
    message: str = Form(...),
    session_id: Optional[str] = Form(None),
    user_id: Optional[str] = Form(None),
    file: Optional[UploadFile] = File(None),
    db: Session = Depends(get_sync_db)
):
    """
    聊天接口（支持文件上传）
    
    - agent_id: Agent ID
    - message: 用户消息
    - session_id: 会话ID（可选，不提供则创建新会话）
    - file: 上传的文件（可选，支持 PDF/DOCX/XLSX/PPTX）
    """
    try:
        # 查询 Agent
        agent_config = db.query(Agent).filter(Agent.id == agent_id).first()
        if not agent_config:
            raise HTTPException(status_code=404, detail=f"Agent {agent_id} 不存在")
        
        # 获取或创建会话
        if session_id:
            session = db.query(ChatSession).filter(ChatSession.id == session_id).first()
            if not session:
                raise HTTPException(status_code=404, detail=f"会话 {session_id} 不存在")
            if session.agent_id != agent_config.id:
                raise HTTPException(status_code=400, detail="会话不属于该 Agent")
        else:
            # 创建新会话
            session = ChatSession(agent_id=agent_config.id, user_id=user_id)
            db.add(session)
            db.commit()
            db.refresh(session)
        
        # 处理上传的文件
        enhanced_message = message
        if file:
            # 使用会话 ID 创建目录
            session_dir = os.path.join("uploads", str(session.id))
            os.makedirs(session_dir, exist_ok=True)
            
            # 保存文件
            session_file_path = os.path.join(session_dir, file.filename)
            with open(session_file_path, "wb") as f:
                content = await file.read()
                f.write(content)
            
            logger.info("[文件 ] 保存至: %s", session_file_path)
            
            # 将文件路径保存到会话元数据
            if session.meta is None:
                session.meta = {}
            if "uploaded_files" not in session.meta:
                session.meta["uploaded_files"] = []
            session.meta["uploaded_files"].append({
                "filename": file.filename,
                "path": session_file_path,
                "uploaded_at": str(datetime.now())
            })
            db.commit()
            
            enhanced_message = f"{message}\n\n[用户上传了文件: {file.filename}，文件路径: {session_file_path}]"
        
        # 创建 Agent 并发送消息
        jchatmind_agent = JChatMindAgent(
            agent_config=agent_config,
            session=session,
            db=db,
            user_id=user_id
        )
        
        response_message = jchatmind_agent.chat(enhanced_message)
        
        return ChatResponse(
            session_id=str(session.id),
            message=response_message
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error("[聊天 ] 处理失败: %s", e, exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))
    # 注意：文件不删除，保留在 uploads/{session_id}/ 目录中


@router.get("/{session_id}/history", response_model=ChatHistoryResponse)
def get_history(
    session_id: str,
    db: Session = Depends(get_sync_db)
):
    """获取会话历史"""
    try:
        session = db.query(ChatSession).filter(ChatSession.id == session_id).first()
        if not session:
            raise HTTPException(status_code=404, detail=f"会话 {session_id} 不存在")
        
        agent_config = db.query(Agent).filter(Agent.id == session.agent_id).first()
        
        jchatmind_agent = JChatMindAgent(
            agent_config=agent_config,
            session=session,
            db=db
        )
        
        history = jchatmind_agent.get_history()
        
        return ChatHistoryResponse(
            session_id=str(session.id),
            messages=history,
            total=len(history)
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error("[历史 ] 获取失败: %s", e, exc_info=True)
        raise HTTPException(status_code=500, detail=f"获取历史失败: {str(e)}")
