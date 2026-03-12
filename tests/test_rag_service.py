import pytest
from unittest.mock import Mock, patch
from app.services.rag_service import RagService
from app.models import KnowledgeBase, Document, ChunkBgeM3


@pytest.fixture
def rag_service(db_session):
    return RagService(db=db_session)


@pytest.fixture
def test_kb_with_chunks(db_session):
    """创建带有文本块的测试知识库"""
    kb = KnowledgeBase(name="Test KB", embedding_model="bge-m3")
    db_session.add(kb)
    db_session.commit()
    db_session.refresh(kb)
    
    doc = Document(kb_id=kb.id, title="测试文档", content="完整内容", filename="test.md")
    db_session.add(doc)
    db_session.commit()
    db_session.refresh(doc)
    
    # 添加几个测试块
    chunks_data = [
        ("Go 语言是 Google 开发的编程语言", [0.8] * 1024),
        ("Python 是一种高级编程语言", [0.6] * 1024),
        ("JavaScript 用于 Web 开发", [0.4] * 1024),
    ]
    
    chunks = []
    for content, embedding in chunks_data:
        chunk = ChunkBgeM3(
            kb_id=kb.id,
            document_id=doc.id,
            content=content,
            embedding=embedding
        )
        db_session.add(chunk)
        chunks.append(chunk)
    
    db_session.commit()
    
    return kb, doc, chunks


def test_embed_success(rag_service):
    """测试 embed 方法成功调用 Ollama API"""
    mock_response = Mock()
    mock_response.json.return_value = {"embedding": [0.1] * 1024}
    mock_response.raise_for_status = Mock()
    
    with patch("httpx.Client") as mock_client:
        mock_client.return_value.__enter__.return_value.post.return_value = mock_response
        
        result = rag_service.embed("测试文本")
        
        assert len(result) == 1024
        assert result[0] == 0.1


def test_embed_api_error(rag_service):
    """测试 embed 方法处理 API 错误"""
    with patch("httpx.Client") as mock_client:
        mock_client.return_value.__enter__.return_value.post.side_effect = Exception("API Error")
        
        with pytest.raises(RuntimeError, match="无法生成 embedding"):
            rag_service.embed("测试文本")


def test_similarity_search(rag_service, test_kb_with_chunks):
    """测试向量相似度检索"""
    kb, doc, chunks = test_kb_with_chunks
    test_query_embedding = [0.75] * 1024
    
    results = rag_service.similarity_search(
        kb_id=str(kb.id),
        query_embedding=test_query_embedding,
        top_k=3
    )
    
    assert len(results) >= 1
    assert "content" in results[0]
    assert "document_id" in results[0]


def test_similarity_search_empty_kb(rag_service, db_session):
    """测试空知识库的向量搜索"""
    kb = KnowledgeBase(name="空知识库")
    db_session.add(kb)
    db_session.commit()
    db_session.refresh(kb)
    
    query_embedding = [0.5] * 1024
    results = rag_service.similarity_search(
        kb_id=str(kb.id),
        query_embedding=query_embedding
    )
    
    assert results == []


def test_rerank_bm25(rag_service):
    """测试 BM25 重排序"""
    candidates = [
        {"id": "1", "content": "Go 语言接口实现", "doc_id": "doc1"},
        {"id": "2", "content": "Python 装饰器", "doc_id": "doc2"},
        {"id": "3", "content": "Go 语言并发编程 goroutine", "doc_id": "doc3"},
    ]
    
    query = "Go 语言"
    
    reranked = rag_service.rerank_bm25(query, candidates)
    
    assert len(reranked) <= rag_service.rerank_top_k
    assert reranked[0]["content"] in ["Go 语言接口实现", "Go 语言并发编程 goroutine"]


def test_rerank_bm25_empty_candidates(rag_service):
    """测试空候选列表的 BM25 重排序"""
    result = rag_service.rerank_bm25("测试查询", [])
    assert result == []


def test_rerank_bm25_less_than_topk(rag_service):
    """测试候选数量少于 top_k 的情况"""
    candidates = [
        {"id": "1", "content": "测试内容1", "doc_id": "doc1"},
        {"id": "2", "content": "测试内容2", "doc_id": "doc2"},
    ]
    
    result = rag_service.rerank_bm25("测试", candidates)
    assert len(result) == 2


@patch.object(RagService, "embed")
def test_search_with_rerank_full_pipeline(mock_embed, rag_service, test_kb_with_chunks):
    """测试完整的检索+重排序流程"""
    kb, doc, chunks = test_kb_with_chunks
    test_query_embedding = [0.7] * 1024
    mock_embed.return_value = test_query_embedding
    
    results = rag_service.search_with_rerank(
        kb_id=str(kb.id),
        query="编程语言"
    )
    
    assert len(results) > 0
    assert isinstance(results[0], str)
    mock_embed.assert_called_once_with("编程语言")


@patch.object(RagService, "embed")
def test_search_with_rerank_no_results(mock_embed, rag_service, db_session):
    """测试没有检索结果的情况"""
    kb = KnowledgeBase(name="空知识库")
    db_session.add(kb)
    db_session.commit()
    db_session.refresh(kb)
    
    mock_embed.return_value = [0.5] * 1024
    
    results = rag_service.search_with_rerank(
        kb_id=str(kb.id),
        query="测试查询"
    )
    
    assert results == []
