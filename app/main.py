from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import logging
from app.core.config import settings
from app.core.logger import setup_logging
from app.core.database import ensure_tables_exist
from app.middleware.logging_middleware import LoggingMiddleware
from app.api import rag, chat, agents, sessions, knowledge, tools, memory, files
from app.services.memory.memory_scheduler import MemoryMaintenanceScheduler

# 初始化日志系统
setup_logging()
logger = logging.getLogger(__name__)

app = FastAPI(
    title=settings.app_name,
    version=settings.app_version,
    debug=settings.debug,
)

# 日志中间件（记录所有请求/响应）
app.add_middleware(LoggingMiddleware)

# CORS 中间件
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 注册路由
app.include_router(agents.router, prefix="/api/agents", tags=["Agents"])
app.include_router(sessions.router, prefix="/api/sessions", tags=["Sessions"])
app.include_router(knowledge.router, prefix="/api/knowledge", tags=["Knowledge"])
app.include_router(tools.router, prefix="/api/tools", tags=["Tools"])
app.include_router(rag.router, prefix="/api/rag", tags=["RAG"])
app.include_router(chat.router, prefix="/api/chat", tags=["Chat"])
app.include_router(memory.router, prefix="/api/memory", tags=["Memory"])
app.include_router(files.router, prefix="/api/files", tags=["Files"])


@app.on_event("startup")
async def startup_event():
    ensure_tables_exist()
    MemoryMaintenanceScheduler.get_instance().start()


@app.on_event("shutdown")
async def shutdown_event():
    MemoryMaintenanceScheduler.get_instance().stop()


@app.get("/")
async def root():
    return {
        "message": "JChatMind-Python API",
        "version": settings.app_version,
        "status": "running"
    }


@app.get("/health")
async def health_check():
    return {"status": "healthy"}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "app.main:app",
        host="0.0.0.0",
        port=8000,
        reload=settings.debug
    )
