from pydantic import BaseModel, Field, field_serializer
from typing import Optional, List
from datetime import datetime
from uuid import UUID


class SessionResponse(BaseModel):
    """Session 响应"""
    id: UUID | str
    agent_id: UUID | str
    title: Optional[str]
    metadata: Optional[dict]
    created_at: datetime
    updated_at: datetime
    message_count: int = Field(default=0, description="消息数量")
    
    @field_serializer('id', 'agent_id')
    def serialize_uuid(self, value: UUID | str, _info) -> str:
        """将 UUID 序列化为字符串"""
        return str(value)
    
    model_config = {"from_attributes": True}


class SessionListResponse(BaseModel):
    """Session 列表响应"""
    sessions: List[SessionResponse]
    total: int


class SessionUpdateRequest(BaseModel):
    """更新 Session 请求"""
    title: Optional[str] = Field(None, max_length=255, description="会话标题")
    metadata: Optional[dict] = Field(None, description="元数据")
