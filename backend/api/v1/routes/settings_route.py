import os
from pathlib import Path

from fastapi import APIRouter

from api.v1.schemas import AppSettings
from core.settings import load, merge_defaults, save

router = APIRouter()


def _settings_path() -> Path:
    config_dir = Path(os.getenv("CONFIG_DIR", "./config"))
    config_dir.mkdir(parents=True, exist_ok=True)
    return config_dir / "app_settings.json"


@router.get("/settings", response_model=AppSettings)
async def get_settings():
    """GET /api/v1/settings — retorna as configurações atuais da aplicação."""
    loaded  = load(_settings_path())
    merged  = merge_defaults(loaded)
    return AppSettings(**merged)


@router.put("/settings", response_model=AppSettings)
async def update_settings(body: AppSettings):
    """
    PUT /api/v1/settings — salva e faz merge com os defaults.

    Apenas os campos enviados no body são persistidos.
    Campos ausentes mantêm os valores default.
    """
    incoming = {k: v for k, v in body.model_dump().items() if v}
    merged   = merge_defaults(incoming)
    save(merged, _settings_path())
    return AppSettings(**merged)