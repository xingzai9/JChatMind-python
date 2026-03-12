"""
KnowledgeTool - 知识库检索工具
"""
from langchain.tools import BaseTool
from typing import Optional, Type
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session
import logging

from app.services.rag_service import RagService

logger = logging.getLogger(__name__)


class KnowledgeQueryInput(BaseModel):
    """知识库查询输入参数"""
    kb_id: str = Field(description="知识库 ID")
    query: str = Field(description="查询问题")


class KnowledgeTool(BaseTool):
    """
    知识库检索工具
    
    用于从指定知识库中检索相关文档片段
    """
    name: str = "knowledge_query"
    description: str = """
    从知识库中检索相关信息。
    输入应该是一个包含 kb_id（知识库ID）和 query（查询问题）的 JSON 对象。
    例如：{"kb_id": "uuid", "query": "Go 语言的接口是如何实现的？"}
    """
    args_schema: Type[BaseModel] = KnowledgeQueryInput
    
    db: Session = Field(exclude=True)
    
    class Config:
        arbitrary_types_allowed = True
    
    def _run(self, kb_id: str, query: str) -> str:
        """
        同步执行知识库检索
        
        Args:
            kb_id: 知识库 ID
            query: 查询问题
            
        Returns:
            检索到的文档内容（多个片段用换行符分隔）
        """
        try:
            rag_service = RagService(db=self.db)
            
            # 执行 RAG 检索
            results = rag_service.search_with_rerank(kb_id=kb_id, query=query)
            
            if not results:
                return f"在知识库 {kb_id} 中未找到与「{query}」相关的信息。"
            
            # 格式化返回结果
            formatted_results = "\n\n---\n\n".join(results)
            
            logger.info(f"知识库检索成功：kb_id={kb_id}, query={query}, results={len(results)}")
            
            return f"检索到 {len(results)} 条相关信息：\n\n{formatted_results}"
            
        except Exception as e:
            logger.error(f"知识库检索失败：{e}")
            return f"检索失败：{str(e)}"
    
    async def _arun(self, kb_id: str, query: str) -> str:
        """异步执行（暂不支持，回退到同步）"""
        return self._run(kb_id, query)
