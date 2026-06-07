import logging
import time

from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware

logger = logging.getLogger("gcms_lims.request_logger")


class RequestLoggerMiddleware(BaseHTTPMiddleware):
    """
    Middleware de log de requisições HTTP (dev mode).

    Loga uma linha por requisição no formato:
        [METHOD] /path/completo → STATUS_CODE  (XXX.Xms)

    Ativo apenas quando o log level for DEBUG ou INFO.
    Em produção (WARNING+), as linhas não são emitidas.
    """

    async def dispatch(self, request: Request, call_next):
        start = time.perf_counter()

        response = await call_next(request)

        elapsed_ms = (time.perf_counter() - start) * 1000
        logger.info(
            "[%s] %s → %s  (%.1fms)",
            request.method,
            request.url.path,
            response.status_code,
            elapsed_ms,
        )

        return response