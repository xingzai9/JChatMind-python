from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, sessionmaker
import logging
from app.core.config import settings

logger = logging.getLogger(__name__)


class Base(DeclarativeBase):
    pass


engine = create_async_engine(
    settings.database_url,
    echo=settings.debug,
    pool_size=10,
    max_overflow=20,
    pool_pre_ping=True,
)

AsyncSessionLocal = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autocommit=False,
    autoflush=False,
)


async def get_db():
    async with AsyncSessionLocal() as session:
        try:
            yield session
        finally:
            await session.close()


# 同步引擎（用于同步路由）- 全局单例
sync_db_url = settings.database_url.replace("postgresql+psycopg://", "postgresql://")
sync_engine = create_engine(
    sync_db_url,
    echo=settings.debug,
    pool_size=10,
    max_overflow=20,
    pool_pre_ping=True,
)

SyncSessionLocal = sessionmaker(
    bind=sync_engine,
    autocommit=False,
    autoflush=False,
)


def get_sync_db():
    """同步数据库会话依赖（全局引擎）"""
    db = SyncSessionLocal()
    try:
        yield db
    finally:
        db.close()


def ensure_tables_exist() -> None:
    """确保核心表存在（开发环境兜底，避免未初始化数据库导致接口报错）。"""
    # 延迟导入，确保模型全部注册到 Base.metadata
    from app import models  # noqa: F401

    try:
        Base.metadata.create_all(bind=sync_engine)
        logger.info("数据库表检查完成（create_all）。")
    except Exception as exc:
        logger.error("数据库表初始化失败: %s", exc, exc_info=True)
        raise
