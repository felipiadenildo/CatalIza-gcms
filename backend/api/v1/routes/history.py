import os
from pathlib import Path
from typing import Annotated

from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import StreamingResponse

from api.v1.schemas import (
    HistoryListResponse,
    RunSaveRequest,
    RunSummary,
    SaveRunResponse,
)
from pipeline.exporter import (
    delete_run,
    load_all_runs,
    runs_to_csv_bytes,
    save_run,
)

router = APIRouter()


def _runs_dir() -> Path:
    d = Path(os.getenv("RUNS_DIR", "./runs"))
    d.mkdir(parents=True, exist_ok=True)
    return d


@router.get("/history", response_model=HistoryListResponse)
async def list_history():
    """GET /api/v1/history — lista todos os runs salvos."""
    runs = load_all_runs(_runs_dir())
    summaries: list[RunSummary] = []

    for run in runs:
        quant  = run.get("quant",  {})
        config = run.get("config", {})

        summaries.append(RunSummary(
            run_id=run.get("run_id", ""),
            sample_name=config.get("sample_name", ""),
            file_name=run.get("file_name", ""),
            created_at=run.get("created_at", ""),
            conversion_pct=float(quant.get("conversion_pct",    0.0)),
            yield_pct=float(quant.get("yield_pct",              0.0)),
            mass_balance_pct=float(quant.get("mass_balance_pct",0.0)),
            missing_carbon_pct=float(quant.get("missing_carbon_pct", 0.0)),
            status_quality=str(quant.get("status_quality", "")),
            notes=str(run.get("notes", "")),
        ))

    return HistoryListResponse(runs=summaries)


@router.post("/history", response_model=SaveRunResponse, status_code=201)
async def save_history(body: RunSaveRequest):
    """POST /api/v1/history — persiste um run no disco."""
    data = {
        "file_name": body.file_name,
        "notes":     body.notes,
        "config":    body.config.model_dump(),
        "quant":     body.quant.model_dump(),
        "peaks":     [p.model_dump() for p in body.peaks],
    }

    run_id = save_run(data, _runs_dir())
    return SaveRunResponse(run_id=run_id)


@router.get("/history/export")
async def export_history(
    ids: Annotated[list[str], Query(alias="ids[]")] = [],
):
    """
    GET /api/v1/history/export?ids[]=a&ids[]=b

    Exporta CSV consolidado dos runs selecionados (ICH Q2R1).
    Se ids[] vazio → exporta todos os runs.
    """
    all_runs = load_all_runs(_runs_dir())

    if ids:
        selected = [r for r in all_runs if r.get("run_id", "") in ids]
    else:
        selected = all_runs

    if not selected:
        raise HTTPException(status_code=404, detail="Nenhum run encontrado para exportar.")

    csv_bytes = runs_to_csv_bytes(selected)

    return StreamingResponse(
        iter([csv_bytes]),
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=\"gcms_history_export.csv\""},
    )


@router.delete("/history/{run_id}", status_code=200)
async def delete_history(run_id: str):
    """DELETE /api/v1/history/{run_id} — remove um run do disco."""
    removed = delete_run(run_id, _runs_dir())

    if not removed:
        raise HTTPException(
            status_code=404,
            detail=f"Run '{run_id}' não encontrado.",
        )

    return {"deleted": run_id}