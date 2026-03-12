import httpx
import jieba
from rank_bm25 import BM25Okapi
from sqlalchemy import select
from sqlalchemy.orm import Session
from typing import Optional
import logging

from app.core.config import settings
from app.models.knowledge import ChunkBgeM3

logger = logging.getLogger(__name__)


class RagService:
    def __init__(self, db: Session):
        self.db = db
        self.ollama_base_url = settings.ollama_base_url
        self.embedding_model = settings.ollama_embedding_model
        self.recall_count = settings.rag_recall_count
        self.rerank_top_k = settings.rag_rerank_top_k
    
    def embed(self, text: str) -> list[float]:
        """
        调用 Ollama API 生成文本的 embedding 向量
        
        Args:
            text: 待嵌入的文本
            
        Returns:
            1024维向量（bge-m3）
        """
        url = f"{self.ollama_base_url}/api/embeddings"
        
        try:
            with httpx.Client(timeout=30.0) as client:
                response = client.post(
                    url,
                    json={
                        "model": self.embedding_model,
                        "prompt": text
                    }
                )
                response.raise_for_status()
                result = response.json()
                embedding = result.get("embedding")
                
                if not embedding:
                    raise ValueError("Ollama API 返回的 embedding 为空")
                
                logger.debug(f"Generated embedding, dimension: {len(embedding)}")
                return embedding
                
        except Exception as e:
            logger.error(f"Ollama API 调用失败: {e}")
            raise RuntimeError(f"无法生成 embedding: {e}")
    
    def similarity_search(
        self, 
        kb_id: str, 
        query_embedding: list[float], 
        top_k: Optional[int] = None
    ) -> list[dict]:
        """
        使用 pgvector 进行向量相似度搜索
        
        Args:
            kb_id: 知识库 ID
            query_embedding: 查询向量
            top_k: 返回前 K 个结果（默认使用 rag_recall_count）
            
        Returns:
            检索结果列表，每个元素包含 id, content, distance
        """
        if top_k is None:
            top_k = self.recall_count
        
        try:
            # bge-m3 使用 cosine 距离（等价于 cosine similarity 排序）
            stmt = (
                select(ChunkBgeM3)
                .where(ChunkBgeM3.kb_id == kb_id)
                .order_by(ChunkBgeM3.embedding.cosine_distance(query_embedding))
                .limit(top_k)
            )

            results = self.db.execute(stmt).scalars().all()

            import numpy as np
            q_arr = np.array(query_embedding, dtype=np.float32)
            q_norm = np.linalg.norm(q_arr) + 1e-9
            candidates = []
            for chunk in results:
                c_arr = np.array(chunk.embedding, dtype=np.float32)
                cosine_sim = float(np.dot(q_arr, c_arr) / (q_norm * (np.linalg.norm(c_arr) + 1e-9)))
                candidates.append({
                    "id": str(chunk.id),
                    "content": chunk.content,
                    "document_id": str(chunk.document_id),
                    "metadata": chunk.meta or {},
                    "similarity": cosine_sim,
                })

            logger.info("向量检索返回 %d 个结果", len(candidates))
            return candidates
            
        except Exception as e:
            logger.error(f"向量检索失败: {e}")
            raise
    
    def rerank_bm25(self, query: str, candidates: list[dict]) -> list[dict]:
        """
        使用 BM25 算法对候选结果进行重排序
        
        Args:
            query: 查询文本
            candidates: 候选文档列表（由 similarity_search 返回）
            
        Returns:
            重排序后的前 K 个结果
        """
        if not candidates:
            return []
        
        if len(candidates) <= self.rerank_top_k:
            return candidates
        
        try:
            # 使用 jieba 分词
            tokenized_corpus = [list(jieba.cut(doc["content"])) for doc in candidates]
            tokenized_query = list(jieba.cut(query))
            
            # BM25 评分
            bm25 = BM25Okapi(tokenized_corpus)
            scores = bm25.get_scores(tokenized_query)
            
            # 按分数排序并返回 Top-K
            ranked_docs = sorted(
                zip(candidates, scores),
                key=lambda x: x[1],
                reverse=True
            )
            
            top_results = [doc for doc, score in ranked_docs[:self.rerank_top_k]]
            
            logger.info(f"BM25 重排序：{len(candidates)} -> {len(top_results)}")
            return top_results
            
        except Exception as e:
            logger.error(f"BM25 重排序失败: {e}")
            # 失败时返回原始结果的前 K 个
            return candidates[:self.rerank_top_k]
    
    def search_with_rerank(self, kb_id: str, query: str) -> list[str]:
        """
        完整的 RAG 检索流程：向量检索 + BM25 重排
        
        Args:
            kb_id: 知识库 ID
            query: 查询文本
            
        Returns:
            重排序后的文档内容列表
        """
        # 1. 生成查询向量
        query_embedding = self.embed(query)
        
        # 2. 向量检索
        candidates = self.similarity_search(kb_id, query_embedding)
        
        if not candidates:
            logger.warning(f"知识库 {kb_id} 中没有找到相关文档")
            return []
        
        # 3. BM25 重排序
        reranked = self.rerank_bm25(query, candidates)
        
        # 4. 提取文档内容
        results = [doc["content"] for doc in reranked]
        
        logger.info(f"RAG 检索完成，返回 {len(results)} 个文档片段")
        return results
