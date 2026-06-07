import asyncio
import json
import uuid
from pathlib import Path

from fastapi import APIRouter, BackgroundTasks, File, Form, HTTPException, UploadFile
from fastapi.responses import JSONResponse

from api.v1.schemas import (
    AnalyzeResponse,
    ProcessingSettings,
    ReactionConfig,
    TICData,
    PeakMeta,
    PeakRow,
    QuantSummaryOut,
)
from core.settings import load as load_settings, merge_defaults
from pipeline.identification.library_manager import LibraryManager
from pipeline.identification.spectral_matcher import SpectralMatcher
from pipeline.identification.identifier import identify
from pipeline.peaks.processor import process
from pipeline.quantification.quantifier import run as quantifier_run
from pipeline.reader import parse_mzxml
from pipeline.smart_defaults import suggest_config_from_peaks

router = APIRouter()

# ── Limiar para processamento assíncrono ──────────────────────────────────────
_LARGE_FILE_BYTES = 10 * 1024 * 1024  # 10 MB

# ── Armazenamento em memória dos jobs assíncronos ─────────────────────────────
# job_id → {"status": str, "result": dict | None, "error": str | None}
_jobs: dict[str, dict] = {}


@router.post("/analyze", response_model=AnalyzeResponse)
async def analyze(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    config: str = Form(default="{}"),
    settings: str | None = Form(default=None),
):
    """
    POST /api/v1/analyze

    Recebe um arquivo .mzXML via multipart/form-data e executa o pipeline
    completo: reader → processor → identifier → quantifier.

    - Arquivo <= 10 MB: processamento síncrono → HTTP 200 + AnalyzeResponse
    - Arquivo >  10 MB: enfileira background task → HTTP 202 + {job_id, status}
    """
    # ── Valida extensão ───────────────────────────────────────────────────────
    filename = file.filename or ""
    if not filename.lower().endswith(".mzxml"):
        raise HTTPException(
            status_code=422,
            detail="Apenas arquivos .mzXML são aceitos.",
        )

    # ── Lê o arquivo em memória sem buffer intermediário ──────────────────────
    file_bytes = await file.read()

    # ── Parseia config e settings do Form ────────────────────────────────────
    try:
        config_dict: dict = json.loads(config)
    except json.JSONDecodeError:
        raise HTTPException(status_code=422, detail="Campo 'config' não é JSON válido.")

    settings_dict: dict = {}
    if settings:
        try:
            settings_dict = json.loads(settings)
        except json.JSONDecodeError:
            raise HTTPException(status_code=422, detail="Campo 'settings' não é JSON válido.")

    # ── Decide: síncrono ou assíncrono ────────────────────────────────────────
    if len(file_bytes) > _LARGE_FILE_BYTES:
        job_id = str(uuid.uuid4())
        _jobs[job_id] = {"status": "processing", "result": None, "error": None}

        background_tasks.add_task(
            _run_pipeline_background,
            job_id=job_id,
            file_bytes=file_bytes,
            file_name=filename,
            config_dict=config_dict,
            settings_dict=settings_dict,
        )

        return JSONResponse(
            status_code=202,
            content={"job_id": job_id, "status": "processing"},
        )

    # ── Processamento síncrono ────────────────────────────────────────────────
    result = await asyncio.get_event_loop().run_in_executor(
        None,
        _run_pipeline,
        file_bytes,
        filename,
        config_dict,
        settings_dict,
    )

    return result


@router.get("/analyze/jobs/{job_id}")
async def get_job_status(job_id: str):
    """
    GET /api/v1/analyze/jobs/{job_id}
    Redireciona para /jobs/{job_id} — mantido para compatibilidade.
    """
    if job_id not in _jobs:
        raise HTTPException(status_code=404, detail=f"Job '{job_id}' não encontrado.")
    return _jobs[job_id]


# ── Pipeline (executado em thread executor para não bloquear o event loop) ────

def _run_pipeline(
    file_bytes: bytes,
    file_name: str,
    config_dict: dict,
    settings_dict: dict,
) -> AnalyzeResponse:
    """
    Executa o pipeline completo de forma síncrona.
    Projetado para ser chamado via run_in_executor.
    """
    from core.settings import DEFAULT_SETTINGS
    from pathlib import Path
    import os

    # Merge settings com defaults
    merged_settings = merge_defaults(settings_dict) if settings_dict else DEFAULT_SETTINGS

    # Carrega library e spectral matcher
    config_dir  = Path(os.getenv("CONFIG_DIR",       "./config"))
    spec_lib_dir = Path(os.getenv("SPECTRAL_LIB_DIR", "./spectral_libraries"))

    library = LibraryManager(config_dir / "compound_library.csv")

    msp_files = list(spec_lib_dir.glob("*.msp"))
    matcher   = SpectralMatcher(
        msp_files[0] if msp_files else Path("nonexistent.msp"),
        merged_settings,
    )

    # 1. Parse mzXML
    raw_data = parse_mzxml(file_bytes)

    # 2. Processamento de sinal
    proc_result = process(raw_data["rt"], raw_data["tic"], merged_settings)

    # 3. Identificação
    df_peaks = identify(proc_result, raw_data["scans"], matcher, library, config_dict)

    # 4. Quantificação
    df_peaks, quant_result = quantifier_run(
        df_peaks,
        config_dict,
        sigma_baseline=proc_result["sigma_baseline"],
    )

    # 5. Sugestão de config
    suggested = suggest_config_from_peaks(df_peaks, library, config_dict)

    # ── Monta TICData ─────────────────────────────────────────────────────────
    rt_list    = proc_result["rt_ref"].tolist()
    peak_metas = _build_peak_metas(proc_result)

    tic_data = TICData(
        rt=rt_list,
        tic_raw=proc_result["tic_raw"].tolist(),
        tic_smooth=proc_result["tic_smooth"].tolist(),
        tic_baseline=proc_result["tic_baseline"].tolist(),
        peaks=peak_metas,
    )

    # ── Serializa peaks ───────────────────────────────────────────────────────
    peaks_out = _df_to_peak_rows(df_peaks)

    # ── Serializa QuantResult → QuantSummaryOut ───────────────────────────────
    quant_out = QuantSummaryOut(
        conversion_pct=quant_result["conversion_pct"],
        yield_pct=quant_result["yield_pct"],
        mass_balance_pct=quant_result["mass_balance_pct"],
        missing_carbon_pct=quant_result["missing_carbon_pct"],
        consumed_mM=quant_result["consumed_mM"],
        is_area=quant_result["is_area"],
        selectivities=quant_result["selectivities"],
        area_percent=quant_result["area_percent"],
        warnings=quant_result["warnings"],
        status_quality=quant_result["status_quality"],
        c_initial_used=quant_result["c_initial_used"],
        c_max_used=quant_result["c_max_used"],
    )

    return AnalyzeResponse(
        job_id=None,
        status="done",
        tic=tic_data,
        peaks=peaks_out,
        quant=quant_out,
        sigma_baseline=proc_result["sigma_baseline"],
        suggested_config=ReactionConfig(**suggested),
    )


async def _run_pipeline_background(
    job_id: str,
    file_bytes: bytes,
    file_name: str,
    config_dict: dict,
    settings_dict: dict,
) -> None:
    """Wrapper assíncrono para execução em background task."""
    try:
        loop = asyncio.get_event_loop()
        result = await loop.run_in_executor(
            None,
            _run_pipeline,
            file_bytes,
            file_name,
            config_dict,
            settings_dict,
        )
        _jobs[job_id] = {
            "status": "done",
            "result": result.model_dump(),
            "error":  None,
        }
    except Exception as exc:
        _jobs[job_id] = {
            "status": "error",
            "result": None,
            "error":  str(exc),
        }


# ── Helpers de serialização ───────────────────────────────────────────────────

def _build_peak_metas(proc_result) -> list[PeakMeta]:
    """Constrói a lista de PeakMeta a partir do ProcResult."""
    metas: list[PeakMeta] = []
    n = len(proc_result["peak_indices"])
    rt_ref = proc_result["rt_ref"]

    for i in range(n):
        apex_idx  = int(proc_result["peak_indices"][i])
        left_idx  = int(proc_result["peak_left_idx"][i])
        right_idx = int(proc_result["peak_right_idx"][i])

        metas.append(PeakMeta(
            peak_id=i + 1,
            label=f"P{i + 1}",
            apex_idx=apex_idx,
            left_idx=left_idx,
            right_idx=right_idx,
            rt_apex=round(float(rt_ref[apex_idx]),  4),
            rt_left=round(float(rt_ref[left_idx]),  4),
            rt_right=round(float(rt_ref[right_idx]), 4),
            area=round(float(proc_result["peak_areas"][i]), 2),
        ))

    return metas


def _df_to_peak_rows(df) -> list[PeakRow]:
    """Converte DataFrame de picos em lista de PeakRow Pydantic."""
    rows: list[PeakRow] = []

    for _, row in df.iterrows():
        rows.append(PeakRow(
            peak_id=int(row.get("peak_id", 0)),
            keep=bool(row.get("keep", True)),
            rt_min=float(row.get("rt_min", 0.0)),
            rt_left=float(row.get("rt_left", 0.0)),
            rt_right=float(row.get("rt_right", 0.0)),
            area=float(row.get("area", 0.0)),
            area_pct=float(row.get("area_pct", 0.0)),
            compound_name=str(row.get("compound_name", "")),
            canonical_name=str(row.get("canonical_name", "")),
            cas=str(row.get("cas", "")),
            role=str(row.get("role", "unknown")),
            rrf=float(row.get("rrf", 1.0)),
            calib_slope=float(row.get("calib_slope", 0.0)),
            calib_intercept=float(row.get("calib_intercept", 0.0)),
            use_calibration=bool(row.get("use_calibration", False)),
            stoichiometry=float(row.get("stoichiometry", 1.0)),
            match_score=float(row.get("match_score", 0.0)),
            match_confidence=str(row.get("match_confidence", "NONE")),
            id_method=str(row.get("id_method", "unassigned")),
            spectrum_idx=int(row.get("spectrum_idx", -1)),
            area_ratio=float(row.get("area_ratio", 0.0)),
            c_vial_mM=float(row.get("c_vial_mM", 0.0)),
            c_flask_mM=float(row.get("c_flask_mM", 0.0)),
            lod_mM=float(row.get("lod_mM", 0.0)),
            loq_mM=float(row.get("loq_mM", 0.0)),
            selectivity_pct=float(row.get("selectivity_pct", 0.0)),
        ))

    return rows


def get_jobs_store() -> dict[str, dict]:
    """Expõe o dict de jobs para a rota /jobs/{job_id}."""
    return _jobs