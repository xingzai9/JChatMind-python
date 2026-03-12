"""
请求/响应日志中间件
记录所有 API 请求和响应信息，方便问题排查
"""
import time
import logging
import uuid
from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.types import Message
import json

logger = logging.getLogger(__name__)


class LoggingMiddleware(BaseHTTPMiddleware):
    """记录所有请求和响应的中间件"""
    
    async def dispatch(self, request: Request, call_next):
        request_id = str(uuid.uuid4())[:6]
        start_time = time.time()

        method = request.method
        path = request.url.path
        client_host = request.client.host if request.client else "?"

        logger.info("[%s] → %s %s  %s", request_id, method, path, client_host)

        try:
            response = await call_next(request)

            elapsed = time.time() - start_time
            status_code = response.status_code

            if status_code >= 500:
                log_level = logging.ERROR
            elif status_code >= 400:
                log_level = logging.WARNING
            else:
                log_level = logging.INFO

            logger.log(log_level, "[%s] ← %d  %.3fs  %s %s",
                       request_id, status_code, elapsed, method, path)

            response.headers["X-Request-ID"] = request_id
            return response

        except Exception as e:
            elapsed = time.time() - start_time
            logger.error("[%s] ✗ %s %s  %.3fs  %s",
                         request_id, method, path, elapsed, e, exc_info=True)
            raise
