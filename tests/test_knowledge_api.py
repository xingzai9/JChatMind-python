import pytest
from unittest.mock import patch
from app.models import KnowledgeBase, Document, ChunkBgeM3


def test_create_knowledge_base(api_client, db_session):
    """测试创建知识库"""
    resp = api_client.post(
        "/api/knowledge/",
        json={
            "name": "测试知识库",
            "description": "测试描述",
            "embedding_model": "bge-m3"
        }
    )
    
    assert resp.status_code == 201
    data = resp.json()
    assert data["name"] == "测试知识库"
    assert data["embedding_model"] == "bge-m3"
    assert data["document_count"] == 0
    assert data["chunk_count"] == 0


def test_list_knowledge_bases(api_client, db_session):
    """测试列出知识库"""
    # 创建知识库
    for i in range(3):
        kb = KnowledgeBase(name=f"知识库{i}", embedding_model="bge-m3")
        db_session.add(kb)
    db_session.commit()
    
    resp = api_client.get("/api/knowledge/")
    
    assert resp.status_code == 200
    data = resp.json()
    assert data["total"] >= 3
    assert len(data["knowledge_bases"]) >= 3


def test_get_knowledge_base(api_client, db_session):
    """测试获取知识库详情"""
    kb = KnowledgeBase(name="测试KB", description="测试", embedding_model="bge-m3")
    db_session.add(kb)
    db_session.commit()
    db_session.refresh(kb)
    
    resp = api_client.get(f"/api/knowledge/{kb.id}")
    
    assert resp.status_code == 200
    data = resp.json()
    assert data["id"] == str(kb.id)
    assert data["name"] == "测试KB"


def test_update_knowledge_base(api_client, db_session):
    """测试更新知识库"""
    kb = KnowledgeBase(name="旧名称", embedding_model="bge-m3")
    db_session.add(kb)
    db_session.commit()
    db_session.refresh(kb)
    
    resp = api_client.put(
        f"/api/knowledge/{kb.id}",
        json={"name": "新名称", "description": "新描述"}
    )
    
    assert resp.status_code == 200
    data = resp.json()
    assert data["name"] == "新名称"
    assert data["description"] == "新描述"


def test_delete_knowledge_base(api_client, db_session):
    """测试删除知识库"""
    kb = KnowledgeBase(name="要删除的", embedding_model="bge-m3")
    db_session.add(kb)
    db_session.commit()
    db_session.refresh(kb)
    
    kb_id = kb.id
    
    resp = api_client.delete(f"/api/knowledge/{kb_id}")
    
    assert resp.status_code == 204
    
    # 验证已删除
    deleted_kb = db_session.query(KnowledgeBase).filter(KnowledgeBase.id == kb_id).first()
    assert deleted_kb is None


@patch('app.api.knowledge.RagService.embed')
def test_upload_document(mock_embed, api_client, db_session):
    """测试上传文档"""
    mock_embed.return_value = [0.1] * 1024

    kb = KnowledgeBase(name="测试KB", embedding_model="bge-m3")
    db_session.add(kb)
    db_session.commit()
    db_session.refresh(kb)

    file_content = b"\xe8\xbf\x99\xe6\x98\xaf\xe6\xb5\x8b\xe8\xaf\x95\xe5\x86\x85\xe5\xae\xb9\xe3\x80\x82\n\n\xe8\xbf\x99\xe6\x98\xaf\xe7\xac\xac\xe4\xba\x8c\xe6\xae\xb5\xe3\x80\x82\n\n\xe8\xbf\x99\xe6\x98\xaf\xe7\xac\xac\xe4\xb8\x89\xe6\xae\xb5\xe3\x80\x82"
    resp = api_client.post(
        f"/api/knowledge/{kb.id}/documents",
        data={"title": "测试文档", "chunk_size": "100", "chunk_overlap": "20"},
        files={"file": ("test.txt", file_content, "text/plain")}
    )

    assert resp.status_code == 201
    data = resp.json()
    assert data["title"] == "测试文档"
    assert data["chunk_count"] > 0


def test_knowledge_base_not_found(api_client):
    """测试获取不存在的知识库"""
    resp = api_client.get("/api/knowledge/00000000-0000-0000-0000-000000000000")
    assert resp.status_code == 404


def test_upload_document_kb_not_found(api_client):
    """测试上传文档到不存在的知识库"""
    resp = api_client.post(
        "/api/knowledge/00000000-0000-0000-0000-000000000000/documents",
        data={"title": "测试"},
        files={"file": ("test.txt", b"\xe6\xb5\x8b\xe8\xaf\x95", "text/plain")}
    )
    assert resp.status_code == 404
