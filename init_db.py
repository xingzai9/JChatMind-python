"""
数据库初始化脚本
创建所有表结构
"""
from sqlalchemy import create_engine
from app.core.database import Base
from app.core.config import settings
from app.models.knowledge import KnowledgeBase, Document, ChunkBgeM3
from app.models.agent import Agent, ChatSession, ChatMessage
from app.models.memory import WorkingMemory, SemanticMemory, EpisodicMemory

def init_database():
    """创建所有表"""
    print("开始创建数据库表...")
    print(f"数据库地址: {settings.database_url}")
    
    # 创建同步引擎
    sync_db_url = settings.database_url.replace("postgresql+psycopg://", "postgresql://")
    engine = create_engine(sync_db_url)
    
    # 创建所有表
    Base.metadata.create_all(bind=engine)
    
    print("\n✅ 数据库表创建成功！")
    print("\n已创建的表：")
    print("  - knowledge_base (知识库)")
    print("  - document (文档)")
    print("  - chunk_bge_m3 (文本块)")
    print("  - agent (Agent)")
    print("  - chat_session (会话)")
    print("  - chat_message (消息)")
    print("  - working_memory (工作记忆)")
    print("  - semantic_memory (语义记忆)")
    print("  - episodic_memory (情节记忆)")
    
    engine.dispose()

if __name__ == "__main__":
    init_database()
