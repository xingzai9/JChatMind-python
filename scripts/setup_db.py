"""
一键执行所有数据库初始化操作：
1. 创建测试数据库 jchatmind_test
2. 在生产数据库 jchatmind 上创建性能索引
"""
import sys
import os

# 加入项目路径
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy import create_engine, text
from app.core.config import settings

# ─── 1. 生产库连接 ───────────────────────────────────────────────
PROD_URL = settings.database_url.replace("postgresql+psycopg://", "postgresql://")

# 用于连接 postgres 默认库来创建 jchatmind_test
BASE_URL = PROD_URL.rsplit("/", 1)[0] + "/postgres"

# ─── 2. 创建测试数据库 ──────────────────────────────────────────
def create_test_database():
    print("\n[1/2] 创建测试数据库 jchatmind_test ...")
    engine = create_engine(BASE_URL, isolation_level="AUTOCOMMIT")
    with engine.connect() as conn:
        exists = conn.execute(
            text("SELECT 1 FROM pg_database WHERE datname = 'jchatmind_test'")
        ).fetchone()
        if exists:
            print("  ✓ jchatmind_test 已存在，跳过创建")
        else:
            conn.execute(text("CREATE DATABASE jchatmind_test"))
            print("  ✓ jchatmind_test 创建成功")
    engine.dispose()

# ─── 3. 在生产库上创建性能索引 ──────────────────────────────────
INDEXES = [
    # agent
    ("idx_agent_is_active",          "agent",        "CREATE INDEX IF NOT EXISTS idx_agent_is_active ON agent (is_active)"),
    ("idx_agent_created_at",         "agent",        "CREATE INDEX IF NOT EXISTS idx_agent_created_at ON agent (created_at DESC)"),
    # chat_session
    ("idx_chat_session_agent_id",    "chat_session", "CREATE INDEX IF NOT EXISTS idx_chat_session_agent_id ON chat_session (agent_id)"),
    ("idx_chat_session_updated_at",  "chat_session", "CREATE INDEX IF NOT EXISTS idx_chat_session_updated_at ON chat_session (updated_at DESC)"),
    # chat_message
    ("idx_chat_message_session_id",  "chat_message", "CREATE INDEX IF NOT EXISTS idx_chat_message_session_id ON chat_message (session_id)"),
    ("idx_chat_message_role",        "chat_message", "CREATE INDEX IF NOT EXISTS idx_chat_message_role ON chat_message (role)"),
    ("idx_chat_message_created_at",  "chat_message", "CREATE INDEX IF NOT EXISTS idx_chat_message_created_at ON chat_message (created_at DESC)"),
    # document
    ("idx_document_kb_id",           "document",     "CREATE INDEX IF NOT EXISTS idx_document_kb_id ON document (kb_id)"),
    ("idx_document_kb_created",      "document",     "CREATE INDEX IF NOT EXISTS idx_document_kb_created ON document (kb_id, created_at DESC)"),
    # chunk_bge_m3
    ("idx_chunk_document_id",        "chunk_bge_m3", "CREATE INDEX IF NOT EXISTS idx_chunk_document_id ON chunk_bge_m3 (document_id)"),
]

def create_indexes():
    print("\n[2/2] 在生产库上创建性能索引 ...")
    engine = create_engine(PROD_URL, isolation_level="AUTOCOMMIT")
    with engine.connect() as conn:
        for name, table, sql in INDEXES:
            try:
                conn.execute(text(sql))
                print(f"  ✓ {name}")
            except Exception as e:
                print(f"  ✗ {name}: {e}")
    engine.dispose()

# ─── 补充：建表（如果表还不存在） ──────────────────────────────
def create_tables():
    print("\n[补充] 确保生产库表结构存在 ...")
    from app.core.database import Base
    import app.models  # noqa: 确保所有模型注册
    prod_engine = create_engine(PROD_URL)
    Base.metadata.create_all(bind=prod_engine)
    prod_engine.dispose()
    print("  ✓ 所有表已就绪")

# ─── 主流程 ──────────────────────────────────────────────────────
if __name__ == "__main__":
    print("=" * 55)
    print("  JChatMind 数据库初始化")
    print("=" * 55)
    print(f"  生产库: {PROD_URL}")

    try:
        create_test_database()
    except Exception as e:
        print(f"  ✗ 创建测试数据库失败: {e}")

    try:
        create_tables()
    except Exception as e:
        print(f"  ✗ 建表失败: {e}")

    try:
        create_indexes()
    except Exception as e:
        print(f"  ✗ 创建索引失败: {e}")

    print("\n✅ 完成！")
