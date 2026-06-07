import json
from datetime import datetime

import pandas as pd
from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from api.v1.schemas import PeakRow, QuantSummaryOut, ReactionConfig
from pipeline.exporter import peaks_to_csv_bytes

router = APIRouter()


class ExportRequest(BaseModel):
    peaks:     list[PeakRow]
    quant:     QuantSummaryOut
    config:    ReactionConfig
    format:    str = "ich_q2r1"   # "ich_q2r1" | "full"


@router.post("/export/csv")
async def export_csv(body: ExportRequest):
    """
    POST /api/v1/export/csv

    Gera e retorna o CSV do run ativo como attachment.

    Formatos:
      ich_q2r1 — colunas padronizadas ICH Q2R1 (para submissão regulatória)
      full     — todas as colunas do DataFrame de picos
    """
    df = pd.DataFrame([p.model_dump() for p in body.peaks])

    if df.empty:
        raise HTTPException(status_code=422, detail="Nenhum pico para exportar.")

    csv_bytes = peaks_to_csv_bytes(df)

    sample_name = body.config.sample_name.replace(" ", "_") or "sample"
    date_str    = datetime.now().strftime("%Y%m%d")
    filename    = f"gcms_results_{sample_name}_{date_str}.csv"

    return StreamingResponse(
        iter([csv_bytes]),
        media_type="text/csv",
        headers={"Content-Disposition": f"attachment; filename=\"{filename}\""},
    )