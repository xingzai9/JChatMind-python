"""
统一日志配置模块
支持控制台输出和文件输出，带日志轮转
"""
import logging
import sys
from pathlib import Path
from logging.handlers import RotatingFileHandler
from app.core.config import settings


def setup_logging():
    """配置日志系统"""
    
    # 创建日志目录
    log_dir = Path("logs")
    log_dir.mkdir(exist_ok=True)
    
    # 获取 root logger
    root_logger = logging.getLogger()
    root_logger.setLevel(getattr(logging, settings.log_level.upper()))
    
    # 清除现有 handlers
    root_logger.handlers.clear()
    
    # 控制台格式：精简，只留时间+级别+消息，便于实时观察流程
    console_formatter = logging.Formatter(
        "%(asctime)s  %(levelname)-5s  %(message)s",
        datefmt="%H:%M:%S"
    )
    # 文件格式：完整，含模块名，便于精准定位问题
    file_formatter = logging.Formatter(
        "%(asctime)s  %(name)s  %(levelname)-5s  %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S"
    )

    # 控制台 Handler
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(logging.INFO)
    console_handler.setFormatter(console_formatter)
    root_logger.addHandler(console_handler)

    # 文件 Handler - 所有日志
    all_file_handler = RotatingFileHandler(
        log_dir / "app.log",
        maxBytes=10 * 1024 * 1024,  # 10MB
        backupCount=5,
        encoding="utf-8"
    )
    all_file_handler.setLevel(logging.DEBUG)
    all_file_handler.setFormatter(file_formatter)
    root_logger.addHandler(all_file_handler)

    # 文件 Handler - 错误日志
    error_file_handler = RotatingFileHandler(
        log_dir / "error.log",
        maxBytes=10 * 1024 * 1024,  # 10MB
        backupCount=5,
        encoding="utf-8"
    )
    error_file_handler.setLevel(logging.ERROR)
    error_file_handler.setFormatter(file_formatter)
    root_logger.addHandler(error_file_handler)
    
    # 设置第三方库日志级别
    logging.getLogger("uvicorn.access").setLevel(logging.WARNING)
    logging.getLogger("sqlalchemy.engine").setLevel(logging.WARNING)
    
    logging.info("日志系统初始化完成")
    logging.info(f"日志级别: {settings.log_level.upper()}")
    logging.info(f"日志文件: {log_dir.absolute()}")
