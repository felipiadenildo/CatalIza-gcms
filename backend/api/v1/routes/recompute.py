import pandas as pd
from fastapi import APIRouter

from api.v1.schemas import (
    PeakRow,
    QuantSummaryOut,
    RecomputeRequest,
    RecomputeResponse,
)
from pipeline.quantification.quantifier import run as quantifier_run

router = APIRouter()


@router.post("/recompute", response_model=RecomputeResponse)
async def recompute(body: RecomputeRequest):
    """
    POST /api/v1/recompute

    Recalcula concentrações e métricas a partir de picos editados pelo usuário.

    Não reprocessa o sinal — recebe o DataFrame de picos já editado
    (bounds, roles, RRF, etc.) e reexecuta apenas o quantifier.

    Etapas:
      1. Reconstrói o DataFrame de peaks a partir de body.peaks
      2. Aplica calibration_override do config
      3. Executa quantifier.run(df, config, sigma_baseline)
      4. Retorna peaks atualizados + QuantSummaryOut

    Body: RecomputeRequest { peaks, config, sigma_baseline }
    Response 200: RecomputeResponse { peaks, quant }
    """
    df = _peaks_to_dataframe(body.peaks)
    config_dict = body.config.model_dump()

    df_updated, quant_result = quantifier_run(
        df,
        config_dict,
        sigma_baseline=body.sigma_baseline,
    )

    peaks_out = _dataframe_to_peak_rows(df_updated, body.peaks)

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

    return RecomputeResponse(peaks=peaks_out, quant=quant_out)


# ── Helpers de conversão ──────────────────────────────────────────────────────

def _peaks_to_dataframe(peaks: list[PeakRow]) -> pd.DataFrame:
    """
    Converte lista de PeakRow Pydantic em DataFrame pandas.
    Garante tipos corretos para o quantifier.
    """
    rows = [p.model_dump() for p in peaks]
    df = pd.DataFrame(rows)

    if df.empty:
        return df

    bool_cols  = ["keep", "use_calibration"]
    float_cols = [
        "rt_min", "rt_left", "rt_right", "area", "area_pct",
        "rrf", "calib_slope", "calib_intercept", "stoichiometry",
        "match_score", "area_ratio", "c_vial_mM", "c_flask_mM",
        "lod_mM", "loq_mM", "selectivity_pct",
    ]
    int_cols   = ["peak_id", "spectrum_idx"]

    for col in bool_cols:
        if col in df.columns:
            df[col] = df[col].astype(bool)

    for col in float_cols:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce").fillna(0.0)

    for col in int_cols:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce").fillna(0).astype(int)

    return df


def _dataframe_to_peak_rows(
    df: pd.DataFrame,
    original_peaks: list[PeakRow],
) -> list[PeakRow]:
    """
    Reconstrói a lista de PeakRow a partir do DataFrame atualizado.

    Preserva campos não calculados (compound_name, cas, id_method, etc.)
    do original caso o DataFrame não os tenha atualizado.
    """
    original_map = {p.peak_id: p for p in original_peaks}
    result: list[PeakRow] = []

    for _, row in df.iterrows():
        peak_id  = int(row.get("peak_id", 0))
        original = original_map.get(peak_id)

        result.append(PeakRow(
            peak_id=peak_id,
            keep=bool(row.get("keep", True)),
            rt_min=float(row.get("rt_min", 0.0)),
            rt_left=float(row.get("rt_left", 0.0)),
            rt_right=float(row.get("rt_right", 0.0)),
            area=float(row.get("area", 0.0)),
            area_pct=float(row.get("area_pct", 0.0)),
            compound_name=str(row.get("compound_name", "")),
            canonical_name=str(row.get("canonical_name", "")),
            cas=str(row.get("cas", getattr(original, "cas", ""))),
            role=str(row.get("role", "unknown")),
            rrf=float(row.get("rrf", 1.0)),
            calib_slope=float(row.get("calib_slope", 0.0)),
            calib_intercept=float(row.get("calib_intercept", 0.0)),
            use_calibration=bool(row.get("use_calibration", False)),
            stoichiometry=float(row.get("stoichiometry", 1.0)),
            match_score=float(row.get("match_score", 0.0)),
            match_confidence=str(row.get("match_confidence", getattr(original, "match_confidence", "NONE"))),
            id_method=str(row.get("id_method", getattr(original, "id_method", "unassigned"))),
            spectrum_idx=int(row.get("spectrum_idx", getattr(original, "spectrum_idx", -1))),
            area_ratio=float(row.get("area_ratio", 0.0)),
            c_vial_mM=float(row.get("c_vial_mM", 0.0)),
            c_flask_mM=float(row.get("c_flask_mM", 0.0)),
            lod_mM=float(row.get("lod_mM", 0.0)),
            loq_mM=float(row.get("loq_mM", 0.0)),
            selectivity_pct=float(row.get("selectivity_pct", 0.0)),
        ))

    return result