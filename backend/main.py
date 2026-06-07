import logging
import os
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from api.v1.middleware.error_handler   import ErrorHandlerMiddleware
from api.v1.middleware.request_logger  import RequestLoggerMiddleware
from api.v1.router                     import api_router

# ── Logging ───────────────────────────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("gcms_lims")


# ── Lifespan: cria diretórios necessários na inicialização ────────────────────
@asynccontextmanager
async def lifespan(app: FastAPI):
    _create_runtime_dirs()
    logger.info("GC-MS LIMS API iniciada. Diretórios de runtime verificados.")
    yield
    logger.info("GC-MS LIMS API encerrada.")


def _create_runtime_dirs() -> None:
    """Garante que runs/, tmp/, config/ e spectral_libraries/ existam."""
    dirs = [
        Path(os.getenv("RUNS_DIR",          "./runs")),
        Path(os.getenv("TMP_DIR",           "./tmp")),
        Path(os.getenv("CONFIG_DIR",        "./config")),
        Path(os.getenv("SPECTRAL_LIB_DIR",  "./spectral_libraries")),
        Path(os.getenv("CONFIG_DIR",        "./config")) / "reaction_presets",
    ]
    for d in dirs:
        d.mkdir(parents=True, exist_ok=True)


# ── Aplicação FastAPI ─────────────────────────────────────────────────────────
app = FastAPI(
    title="GC-MS LIMS API",
    description=(
        "Plataforma local para análise quantitativa de dados GC-MS. "
        "Parse de mzXML, processamento de sinal TIC, identificação por "
        "RT/WDP e quantificação por IS/calibração (ICH Q2R1)."
    ),
    version="1.0.0",
    lifespan=lifespan,
    docs_url="/docs",
    redoc_url="/redoc",
)

# ── CORS ──────────────────────────────────────────────────────────────────────
_cors_origins_raw = os.getenv("CORS_ORIGINS", "http://localhost:5173")
_cors_origins = [o.strip() for o in _cors_origins_raw.split(",") if o.strip()]

app.add_middleware(
    CORSMiddleware,
    allow_origins=_cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── Middlewares customizados (ordem importa: último adicionado = primeiro executado) ──
app.add_middleware(RequestLoggerMiddleware)
app.add_middleware(ErrorHandlerMiddleware)

# ── Rotas ─────────────────────────────────────────────────────────────────────
app.include_router(api_router)


@app.get("/", tags=["Health"])
async def health_check():
    """Health check — confirma que a API está no ar."""
    return {"status": "ok", "service": "GC-MS LIMS API", "version": "1.0.0"}