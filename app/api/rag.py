from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from app.core.database import AsyncSessionLocal, get_sync_db
from app.services.rag_service import RagService
from app.schemas.rag import (
    RagQueryRequest,
    RagQueryResponse,
    EmbedRequest,
    EmbedResponse
)
import logging
import time

logger = logging.getLogger(__name__)

router = APIRouter()




@router.post("/query", response_model=RagQueryResponse)
def rag_query(
    request: RagQueryRequest,
    db: Session = Depends(get_sync_db)
):
    """
    RAG 检索接口：向量检索 + BM25 重排序
    
    该接口用于调试和测试 RAG 检索效果
    """
    start_time = time.time()
    
    try:
        rag_service = RagService(db=db)
        
        results = rag_service.search_with_rerank(
            kb_id=request.kb_id,
            query=request.query
        )
        
        if request.top_k and len(results) > request.top_k:
            results = results[:request.top_k]
        
        elapsed_time = time.time() - start_time
        
        return RagQueryResponse(
            results=results,
            count=len(results),
            metadata={
                "recall_count": rag_service.recall_count,
                "rerank_top_k": rag_service.rerank_top_k,
                "elapsed_seconds": round(elapsed_time, 3)
            }
        )
        
    except Exception as e:
        logger.error(f"RAG 查询失败: {e}")
        raise HTTPException(status_code=500, detail=f"RAG 查询失败: {str(e)}")


@router.post("/embed", response_model=EmbedResponse)
def generate_embedding(
    request: EmbedRequest,
    db: Session = Depends(get_sync_db)
):
    """
    生成文本的 Embedding 向量（调试用）
    
    调用 Ollama API 生成 bge-m3 向量
    """
    try:
        rag_service = RagService(db=db)
        embedding = rag_service.embed(request.text)
        
        return EmbedResponse(
            embedding=embedding,
            dimension=len(embedding)
        )
        
    except Exception as e:
        logger.error(f"生成 embedding 失败: {e}")
        raise HTTPException(status_code=500, detail=f"生成 embedding 失败: {str(e)}")
