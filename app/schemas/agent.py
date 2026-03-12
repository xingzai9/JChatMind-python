from pydantic import BaseModel, Field, field_serializer
from typing import Optional, List
from datetime import datetime
from uuid import UUID


class AgentCreate(BaseModel):
    """创建 Agent 请求"""
    name: str = Field(..., min_length=1, max_length=255, description="Agent 名称")
    description: Optional[str] = Field(None, description="Agent 描述")
    system_prompt: str = Field(..., min_length=1, description="系统提示词")
    model_type: str = Field(..., description="模型类型", pattern="^(deepseek|zhipuai|openai)$")
    model_name: str = Field(..., min_length=1, max_length=100, description="模型名称")
    temperature: float = Field(0.7, ge=0.0, le=2.0, description="温度参数")
    max_tokens: Optional[int] = Field(None, gt=0, description="最大 token 数")
    max_messages: int = Field(6, gt=0, le=100, description="短期记忆窗口大小")
    tools: Optional[List[str]] = Field(default=[], description="工具列表")
    knowledge_bases: Optional[List[str]] = Field(default=[], description="知识库 ID 列表")
    
    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "name": "Go 语言助手",
                    "description": "专注于 Go 语言开发的 AI 助手",
                    "system_prompt": "你是一个专业的 Go 语言专家...",
                    "model_type": "deepseek",
                    "model_name": "deepseek-chat",
                    "temperature": 0.7,
                    "max_messages": 10,
                    "knowledge_bases": ["uuid-1", "uuid-2"]
                }
            ]
        }
    }


class AgentUpdate(BaseModel):
    """更新 Agent 请求"""
    name: Optional[str] = Field(None, min_length=1, max_length=255)
    description: Optional[str] = None
    system_prompt: Optional[str] = Field(None, min_length=1)
    model_type: Optional[str] = Field(None, pattern="^(deepseek|zhipuai|openai)$")
    model_name: Optional[str] = Field(None, min_length=1, max_length=100)
    temperature: Optional[float] = Field(None, ge=0.0, le=2.0)
    max_tokens: Optional[int] = Field(None, gt=0)
    max_messages: Optional[int] = Field(None, gt=0, le=100)
    tools: Optional[List[str]] = None
    knowledge_bases: Optional[List[str]] = None
    is_active: Optional[bool] = None


class AgentResponse(BaseModel):
    """Agent 响应"""
    id: UUID | str  # 接受 UUID 或 str
    name: str
    description: Optional[str]
    system_prompt: str
    model_type: str
    model_name: str
    temperature: float
    max_tokens: Optional[int]
    max_messages: int
    tools: List[str]
    knowledge_bases: List[str]
    is_active: bool
    created_at: datetime
    updated_at: datetime
    
    @field_serializer('id')
    def serialize_id(self, value: UUID | str, _info) -> str:
        """将 UUID 序列化为字符串"""
        return str(value)
    
    model_config = {"from_attributes": True}


class AgentListResponse(BaseModel):
    """Agent 列表响应"""
    agents: List[AgentResponse]
    total: int
