import json
from pathlib import Path

from fastapi import APIRouter, HTTPException
import os

from api.v1.schemas import MethodsListResponse, ReactionConfig

router = APIRouter()


def _presets_dir() -> Path:
    config_dir = Path(os.getenv("CONFIG_DIR", "./config"))
    d = config_dir / "reaction_presets"
    d.mkdir(parents=True, exist_ok=True)
    return d


@router.get("/methods", response_model=MethodsListResponse)
async def list_methods():
    """GET /api/v1/methods — lista todos os presets de reação."""
    presets: dict[str, ReactionConfig] = {}
    d = _presets_dir()

    for f in sorted(d.glob("*.json")):
        name = f.stem
        try:
            with open(f, "r", encoding="utf-8") as fh:
                data = json.load(fh)
            presets[name] = ReactionConfig(**data)
        except Exception:
            continue

    return MethodsListResponse(presets=presets)


@router.post("/methods/{name}", status_code=201)
async def save_method(name: str, config: ReactionConfig):
    """POST /api/v1/methods/{name} — salva ou sobrescreve um preset."""
    if not name or "/" in name or "\\" in name:
        raise HTTPException(status_code=422, detail="Nome de preset inválido.")

    target = _presets_dir() / f"{name}.json"
    with open(target, "w", encoding="utf-8") as f:
        json.dump(config.model_dump(), f, indent=2, ensure_ascii=False)

    return {"saved": name}


@router.delete("/methods/{name}", status_code=200)
async def delete_method(name: str):
    """DELETE /api/v1/methods/{name} — remove um preset."""
    target = _presets_dir() / f"{name}.json"

    if not target.exists():
        raise HTTPException(
            status_code=404,
            detail=f"Preset '{name}' não encontrado.",
        )

    target.unlink()
    return {"deleted": name}