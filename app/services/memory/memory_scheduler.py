"""
MemoryMaintenanceScheduler - 记忆维护后台调度器

功能：
  1. 每 CLEANUP_INTERVAL_HOURS 小时执行一次 prune_decayed，清理衰减过低的情节记忆
  2. 守护线程运行，应用关闭时自动退出
  3. 应用启动时注册，通过 start() / stop() 管理生命周期
"""
import threading
import logging
from typing import Optional

logger = logging.getLogger(__name__)

CLEANUP_INTERVAL_HOURS = 24  # 每 24 小时清理一次


class MemoryMaintenanceScheduler:
    """单例调度器，应用启动时创建一个实例。"""

    _instance: Optional["MemoryMaintenanceScheduler"] = None

    def __init__(self, interval_hours: float = CLEANUP_INTERVAL_HOURS):
        self._interval = interval_hours * 3600
        self._timer: Optional[threading.Timer] = None
        self._running = False

    @classmethod
    def get_instance(cls) -> "MemoryMaintenanceScheduler":
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    def start(self):
        if self._running:
            return
        self._running = True
        self._schedule_next()
        logger.info("记忆维护调度器已启动（间隔 %.0fh）", self._interval / 3600)

    def stop(self):
        self._running = False
        if self._timer:
            self._timer.cancel()
            self._timer = None
        logger.info("记忆维护调度器已停止")

    def _schedule_next(self):
        if not self._running:
            return
        self._timer = threading.Timer(self._interval, self._run_cleanup)
        self._timer.daemon = True
        self._timer.start()

    def _run_cleanup(self):
        """执行一次全局记忆清理，遍历所有 agent/user 组合。"""
        if not self._running:
            return
        try:
            self._do_cleanup()
        except Exception as e:
            logger.error("记忆维护任务异常: %s", e, exc_info=True)
        finally:
            self._schedule_next()  # 无论成功失败都调度下一次

    def _do_cleanup(self):
        from app.core.database import SyncSessionLocal
        from app.models.memory import EpisodicMemory, SemanticMemory
        from app.services.memory.long_term_memory_service import LongTermMemoryService

        db = SyncSessionLocal()
        total_pruned = 0
        try:
            # 查询所有 (agent_id, user_id) 组合
            pairs = (
                db.query(EpisodicMemory.agent_id, EpisodicMemory.user_id)
                .distinct()
                .all()
            )
            if not pairs:
                logger.debug("记忆维护：无情节记忆，跳过清理")
                return

            # 轻量服务实例（清理不需要 LLM）
            svc = _make_dummy_service(db)
            for agent_id, user_id in pairs:
                try:
                    pruned = svc.prune_decayed(agent_id, user_id)
                    total_pruned += pruned
                except Exception as e:
                    logger.warning("清理 agent=%s user=%s 失败: %s", agent_id, user_id, e)

            logger.info("记忆维护完成：共清理 %d 条衰减情节记忆", total_pruned)
        except Exception as e:
            db.rollback()
            logger.error("记忆维护 DB 错误: %s", e, exc_info=True)
        finally:
            db.close()


def _make_dummy_service(db):
    """仅用于维护任务的轻量服务实例（无需真实 LLM）"""
    from app.services.memory.long_term_memory_service import LongTermMemoryService
    from app.services.rag_service import RagService

    svc = LongTermMemoryService.__new__(LongTermMemoryService)
    svc.db = db
    svc.llm = None
    svc._rag = RagService(db)
    return svc
