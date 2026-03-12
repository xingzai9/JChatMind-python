from pydantic import BaseModel, Field, field_serializer
from typing import Optional, List
from datetime import datetime
from uuid import UUID


class KnowledgeBaseCreate(BaseModel):
    """创建知识库请求"""
    name: str = Field(..., min_length=1, max_length=255, description="知识库名称")
    description: Optional[str] = Field(None, description="知识库描述")
    embedding_model: str = Field("bge-m3", description="Embedding 模型")


class KnowledgeBaseUpdate(BaseModel):
    """更新知识库请求"""
    name: Optional[str] = Field(None, min_length=1, max_length=255)
    description: Optional[str] = None


class KnowledgeBaseResponse(BaseModel):
    """知识库响应"""
    id: UUID | str
    name: str
    description: Optional[str]
    embedding_model: str
    created_at: datetime
    document_count: int = Field(default=0, description="文档数量")
    chunk_count: int = Field(default=0, description="分块数量")
    
    @field_serializer('id')
    def serialize_id(self, value: UUID | str, _info) -> str:
        return str(value)
    
    model_config = {"from_attributes": True}


class KnowledgeBaseListResponse(BaseModel):
    """知识库列表响应"""
    knowledge_bases: List[KnowledgeBaseResponse]
    total: int


class DocumentUploadRequest(BaseModel):
    """文档上传请求"""
    title: str = Field(..., min_length=1, max_length=500, description="文档标题")
    content: str = Field(..., min_length=1, description="文档内容")
    metadata: Optional[dict] = Field(default=None, description="元数据")
    chunk_size: int = Field(500, ge=100, le=2000, description="分块大小")
    chunk_overlap: int = Field(50, ge=0, le=500, description="分块重叠")


class DocumentResponse(BaseModel):
    """文档响应"""
    id: UUID | str
    kb_id: UUID | str
    title: str
    content_length: int
    chunk_count: int
    created_at: datetime
    
    @field_serializer('id', 'kb_id')
    def serialize_uuid(self, value: UUID | str, _info) -> str:
        return str(value)
    
    model_config = {"from_attributes": True}


class DocumentDetailResponse(BaseModel):
    """文档详情响应（含 embedding 状态）"""
    id: UUID | str
    kb_id: UUID | str
    title: str
    filename: Optional[str]
    filetype: Optional[str]
    size: Optional[int]
    content_length: int
    chunk_count: int
    embedding_status: str = "unknown"   # processing / completed / failed / unknown
    created_at: datetime

    @field_serializer('id', 'kb_id')
    def serialize_uuid(self, value: UUID | str, _info) -> str:
        return str(value)

    model_config = {"from_attributes": True}


class DocumentListResponse(BaseModel):
    """文档列表响应"""
    documents: List[DocumentDetailResponse]
    total: int
