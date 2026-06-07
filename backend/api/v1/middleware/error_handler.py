import logging
import traceback

from fastapi import Request
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware

logger = logging.getLogger("gcms_lims.error_handler")


# Mapeamento de tipo de exceção → código de erro semântico
_EXCEPTION_CODE_MAP: dict[type[Exception], str] = {}


def _register(exc_type: type[Exception], code: str) -> None:
    _EXCEPTION_CODE_MAP[exc_type] = code


# Registra os tipos conhecidos após imports
try:
    from pydantic import ValidationError
    _register(ValidationError, "VALIDATION_ERROR")
except ImportError:
    pass


class ErrorHandlerMiddleware(BaseHTTPMiddleware):
    """
    Middleware global de tratamento de exceções.

    Converte qualquer exceção não tratada em uma resposta JSON padronizada:
        {
            "detail": "mensagem legível",
            "code":   "CÓDIGO_SEMÂNTICO"
        }

    Códigos semânticos:
        PARSE_ERROR       — falha no parse do arquivo mzXML
        PIPELINE_ERROR    — erro interno no pipeline analítico
        NOT_FOUND         — recurso não encontrado
        VALIDATION_ERROR  — dados de entrada inválidos (Pydantic)
        INTERNAL_ERROR    — erro genérico não classificado
    """

    async def dispatch(self, request: Request, call_next):
        try:
            return await call_next(request)

        except ValueError as exc:
            msg = str(exc)
            code = "PARSE_ERROR" if "mzxml" in msg.lower() or "mzXML" in msg else "VALIDATION_ERROR"
            logger.warning("ValueError [%s]: %s", code, msg)
            return JSONResponse(
                status_code=422,
                content={"detail": msg, "code": code},
            )

        except FileNotFoundError as exc:
            logger.warning("NOT_FOUND: %s", exc)
            return JSONResponse(
                status_code=404,
                content={"detail": str(exc), "code": "NOT_FOUND"},
            )

        except Exception as exc:
            # Determina código pelo tipo registrado
            code = "INTERNAL_ERROR"
            for exc_type, mapped_code in _EXCEPTION_CODE_MAP.items():
                if isinstance(exc, exc_type):
                    code = mapped_code
                    break

            # Exceções do pipeline recebem PIPELINE_ERROR
            module = type(exc).__module__ or ""
            if "pipeline" in module:
                code = "PIPELINE_ERROR"

            logger.error(
                "Unhandled exception [%s]: %s\n%s",
                code,
                exc,
                traceback.format_exc(),
            )
            return JSONResponse(
                status_code=500,
                content={"detail": "Erro interno do servidor.", "code": code},
            )


def register_pipeline_error(exc: Exception) -> JSONResponse:
    """
    Helper para rotas que querem retornar PIPELINE_ERROR manualmente
    sem lançar exceção (ex: falha suave no pipeline).
    """
    logger.error("PIPELINE_ERROR: %s", exc)
    return JSONResponse(
        status_code=500,
        content={"detail": str(exc), "code": "PIPELINE_ERROR"},
    )