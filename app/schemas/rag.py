from pydantic import BaseModel, Field
from typing import Optional


class RagQueryRequest(BaseModel):
    """RAG 查询请求"""
    kb_id: str = Field(..., description="知识库 ID")
    query: str = Field(..., description="查询文本", min_length=1)
    top_k: Optional[int] = Field(None, description="返回结果数量", ge=1, le=20)
    
    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "kb_id": "d8e76ffb-1539-4362-a0a3-7edb6c39b9d8",
                    "query": "Go 语言的接口是如何实现的？",
                    "top_k": 5
                }
            ]
        }
    }


class RagQueryResponse(BaseModel):
    """RAG 查询响应"""
    results: list[str] = Field(..., description="检索到的文档片段列表")
    count: int = Field(..., description="结果数量")
    metadata: dict = Field(default_factory=dict, description="检索元数据（如耗时等）")
    
    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "results": [
                        "Go 语言的接口是一组方法签名的集合...",
                        "接口的实现是隐式的，无需显式声明..."
                    ],
                    "count": 2,
                    "metadata": {
                        "recall_count": 40,
                        "rerank_top_k": 5
                    }
                }
            ]
        }
    }


class EmbedRequest(BaseModel):
    """生成 Embedding 请求"""
    text: str = Field(..., description="待嵌入的文本", min_length=1)


class EmbedResponse(BaseModel):
    """生成 Embedding 响应"""
    embedding: list[float] = Field(..., description="向量（1024维）")
    dimension: int = Field(..., description="向量维度")
