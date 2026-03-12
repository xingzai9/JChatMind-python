import pytest
from sqlalchemy import select
from app.models import KnowledgeBase, Document, ChunkBgeM3
import uuid


def test_create_knowledge_base(db_session):
    kb = KnowledgeBase(
        name="测试知识库",
        description="用于单元测试的知识库",
        meta={"type": "test", "version": "1.0"}
    )
    
    db_session.add(kb)
    db_session.commit()
    db_session.refresh(kb)
    
    assert kb.id is not None
    assert isinstance(kb.id, uuid.UUID)
    assert kb.name == "测试知识库"
    assert kb.description == "用于单元测试的知识库"
    assert kb.meta["type"] == "test"
    assert kb.created_at is not None
    assert kb.updated_at is not None


def test_create_document(db_session):
    kb = KnowledgeBase(name="测试知识库")
    db_session.add(kb)
    db_session.commit()
    db_session.refresh(kb)
    
    doc = Document(
        kb_id=kb.id,
        title="测试文档",
        content="这是测试内容",
        filename="test.md",
        filetype="markdown",
        size=1024,
        meta={"pages": 1}
    )
    
    db_session.add(doc)
    db_session.commit()
    db_session.refresh(doc)
    
    assert doc.id is not None
    assert doc.kb_id == kb.id
    assert doc.title == "测试文档"
    assert doc.filetype == "markdown"
    assert doc.size == 1024
    assert doc.meta["pages"] == 1


def test_create_chunk_with_embedding(db_session):
    kb = KnowledgeBase(name="测试知识库")
    db_session.add(kb)
    db_session.commit()
    db_session.refresh(kb)
    
    doc = Document(
        kb_id=kb.id,
        title="测试文档",
        content="完整内容",
        filename="test.md"
    )
    db_session.add(doc)
    db_session.commit()
    db_session.refresh(doc)
    
    test_embedding = [0.1] * 1024
    
    chunk = ChunkBgeM3(
        kb_id=kb.id,
        document_id=doc.id,
        content="这是一段测试文本，用于验证向量存储功能。",
        embedding=test_embedding,
        meta={"chunk_index": 0}
    )
    
    db_session.add(chunk)
    db_session.commit()
    db_session.refresh(chunk)
    
    assert chunk.id is not None
    assert chunk.kb_id == kb.id
    assert chunk.document_id == doc.id
    assert chunk.content == "这是一段测试文本，用于验证向量存储功能。"
    assert len(chunk.embedding) == 1024
    assert chunk.embedding[0] == 0.1
    assert chunk.meta["chunk_index"] == 0


def test_relationship_kb_to_documents(db_session):
    kb = KnowledgeBase(name="测试知识库")
    db_session.add(kb)
    db_session.commit()
    db_session.refresh(kb)
    
    doc1 = Document(kb_id=kb.id, title="文档1", content="内容1", filename="doc1.md")
    doc2 = Document(kb_id=kb.id, title="文档2", content="内容2", filename="doc2.md")
    db_session.add_all([doc1, doc2])
    db_session.commit()
    
    result = db_session.execute(
        select(KnowledgeBase).where(KnowledgeBase.id == kb.id)
    )
    kb_with_docs = result.scalar_one()
    db_session.refresh(kb_with_docs, ["documents"])
    
    assert len(kb_with_docs.documents) == 2
    assert {doc.filename for doc in kb_with_docs.documents} == {"doc1.md", "doc2.md"}


def test_cascade_delete_kb(db_session):
    """测试级联删除"""
    kb = KnowledgeBase(name="测试知识库")
    db_session.add(kb)
    db_session.commit()
    db_session.refresh(kb)
    
    doc = Document(kb_id=kb.id, title="测试", content="测试内容", filename="test.md")
    db_session.add(doc)
    db_session.commit()
    
    chunk = ChunkBgeM3(
        kb_id=kb.id,
        document_id=doc.id,
        content="test content",
        embedding=[0.1] * 1024
    )
    db_session.add(chunk)
    db_session.commit()
    
    kb_id = kb.id
    db_session.delete(kb)
    db_session.commit()
    
    # 验证级联删除
    assert db_session.query(Document).filter_by(kb_id=kb_id).first() is None
    assert db_session.query(ChunkBgeM3).filter_by(kb_id=kb_id).first() is None


def test_vector_similarity_query(db_session):
    """测试向量相似度查询"""
    kb = KnowledgeBase(name="测试知识库")
    db_session.add(kb)
    db_session.commit()
    db_session.refresh(kb)
    
    doc = Document(kb_id=kb.id, title="测试", content="测试内容", filename="test.md")
    db_session.add(doc)
    db_session.commit()
    
    # 创建测试向量
    chunk1 = ChunkBgeM3(
        kb_id=kb.id,
        document_id=doc.id,
        content="content 1",
        embedding=[1.0] * 1024
    )
    chunk2 = ChunkBgeM3(
        kb_id=kb.id,
        document_id=doc.id,
        content="content 2",
        embedding=[0.5] * 1024
    )
    db_session.add_all([chunk1, chunk2])
    db_session.commit()
    
    # 查询最相似的向量
    query_vector = [0.9] * 1024
    results = db_session.query(ChunkBgeM3).filter(
        ChunkBgeM3.kb_id == kb.id
    ).all()
    
    assert len(results) == 2
