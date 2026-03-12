from pydantic import BaseModel, Field
from typing import Optional, List
from datetime import datetime


class ChatRequest(BaseModel):
    """聊天请求"""
    agent_id: str = Field(..., description="Agent ID")
    session_id: Optional[str] = Field(None, description="会话 ID（不提供则创建新会话）")
    message: str = Field(..., description="用户消息", min_length=1)
    
    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "agent_id": "d8e76ffb-1539-4362-a0a3-7edb6c39b9d8",
                    "session_id": "a1b2c3d4-5678-90ab-cdef-1234567890ab",
                    "message": "Go 语言的接口是如何实现的？"
                }
            ]
        }
    }


class ChatResponse(BaseModel):
    """聊天响应"""
    session_id: str = Field(..., description="会话 ID")
    message: str = Field(..., description="AI 回复")
    
    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "session_id": "a1b2c3d4-5678-90ab-cdef-1234567890ab",
                    "message": "Go 语言的接口是一组方法签名的集合..."
                }
            ]
        }
    }


class ChatHistoryResponse(BaseModel):
    """聊天历史响应"""
    session_id: str
    messages: List[dict]
    total: int
