import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker, Session
from sqlalchemy.pool import StaticPool
from fastapi.testclient import TestClient
from app.core.database import Base
from app.core.config import settings

# 确保所有模型都被导入
from app.models import KnowledgeBase, Document, ChunkBgeM3, Agent, ChatSession, ChatMessage
from app.models.memory import WorkingMemory, SemanticMemory, EpisodicMemory


@pytest.fixture(scope="session")
def test_engine():
    # ⚠️ 使用独立测试数据库，避免清空生产数据
    # 如果环境变量中有 DATABASE_URL，优先使用；否则使用默认测试库
    import os
    test_db_url = os.getenv("TEST_DATABASE_URL") or "postgresql://postgres:postgres@localhost:5432/jchatmind_test"
    
    # 如果仍然使用生产库，抛出错误
    if "jchatmind_test" not in test_db_url and test_db_url == settings.database_url:
        raise RuntimeError(
            "⚠️ 测试将清空数据库！请设置 TEST_DATABASE_URL 环境变量指向独立测试数据库。\n"
            f"当前生产库: {settings.database_url}\n"
            "推荐测试库: postgresql://postgres:postgres@localhost:5432/jchatmind_test"
        )
    
    sync_db_url = test_db_url.replace("postgresql+psycopg://", "postgresql://")
    
    engine = create_engine(
        sync_db_url,
        poolclass=StaticPool,
        echo=False,
    )
    
    # 启用 pgvector 扩展（semantic_memory / episodic_memory 需要）
    with engine.begin() as conn:
        conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))

    # 使用原始 SQL 删除表（避免外键约束问题）
    with engine.begin() as conn:
        # 删除 Python 版本的表
        for table in reversed(Base.metadata.sorted_tables):
            conn.execute(text(f"DROP TABLE IF EXISTS {table.name} CASCADE"))
    
    # 创建所有表
    Base.metadata.create_all(engine)
    
    yield engine
    
    # 测试结束后清理
    with engine.begin() as conn:
        for table in reversed(Base.metadata.sorted_tables):
            conn.execute(text(f"DROP TABLE IF EXISTS {table.name} CASCADE"))
    engine.dispose()


@pytest.fixture(scope="function")
def db_session(test_engine):
    """为每个测试创建新的数据库会话"""
    Session = sessionmaker(bind=test_engine)
    session = Session()
    yield session
    session.close()


@pytest.fixture(scope="function")
def api_client(db_session):
    """API 测试客户端，自动 override 所有 get_sync_db 依赖"""
    from app.main import app
    from app.core.database import get_sync_db
    
    def override_get_sync_db():
        try:
            yield db_session
        finally:
            pass
    
    # Override get_sync_db
    app.dependency_overrides[get_sync_db] = override_get_sync_db
    
    client = TestClient(app)
    yield client
    
    # 清理
    app.dependency_overrides.clear()
