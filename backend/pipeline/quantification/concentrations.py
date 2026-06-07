import numpy as np
import pandas as pd

from core.utils import safe_div


def apply_overrides(df: pd.DataFrame, config: dict) -> pd.DataFrame:
    """
    Aplica calibration_override do config sobre o DataFrame de picos.

    calibration_override é um dict do ReactionConfig com formato:
        {
            "canonical_name_do_composto": {
                "calib_slope": 1234.5,
                "calib_intercept": -0.5,
                "use_calibration": true,
                "rrf": 1.0
            },
            ...
        }

    Apenas os campos presentes no override são atualizados.
    Compostos não listados no override não são modificados.

    Args:
        df:     DataFrame de picos com colunas canonical_name,
                calib_slope, calib_intercept, use_calibration, rrf.
        config: ReactionConfig como dict.

    Returns:
        DataFrame com overrides aplicados (cópia).
    """
    result = df.copy()
    overrides: dict = config.get("calibration_override", {})

    if not overrides:
        return result

    for idx, row in result.iterrows():
        canonical = str(row.get("canonical_name", "")).strip()
        if canonical not in overrides:
            continue

        patch = overrides[canonical]

        if "calib_slope" in patch:
            result.at[idx, "calib_slope"] = float(patch["calib_slope"])
        if "calib_intercept" in patch:
            result.at[idx, "calib_intercept"] = float(patch["calib_intercept"])
        if "use_calibration" in patch:
            result.at[idx, "use_calibration"] = bool(patch["use_calibration"])
        if "rrf" in patch:
            result.at[idx, "rrf"] = float(patch["rrf"])

    return result


def compute(
    df: pd.DataFrame,
    config: dict,
    sigma_baseline: float,
    area_IS: float,
) -> pd.DataFrame:
    """
    Calcula concentrações e limites de detecção/quantificação para cada pico.

    Dois modos de quantificação por composto (selecionado por use_calibration):

    Por curva de calibração (use_calibration=True):
        c_vial = (area_ratio - calib_intercept) / calib_slope
        LOD    = 3.3 × σ_AR / calib_slope × c_IS × dilution
        LOQ    = 10.0 × σ_AR / calib_slope × c_IS × dilution

    Por RRF — Relative Response Factor (use_calibration=False):
        c_vial = (area_ratio / rrf) × c_is_vial_mM
        LOD    = 3.3 × σ_AR / (rrf × area_IS) × c_is_vial_mM × dilution
        LOQ    = 10.0 × σ_AR / (rrf × area_IS) × c_is_vial_mM × dilution

    Conversão vial → frasco:
        c_flask = c_vial × dilution_factor

    Referência: ICH Q2R1 — Validation of Analytical Procedures.

    Args:
        df:             DataFrame com area_ratio, rrf, calib_slope,
                        calib_intercept, use_calibration, keep.
        config:         ReactionConfig como dict.
        sigma_baseline: σ do ruído (saída de integrator.sigma_noise).
        area_IS:        Área do IS (float) — para cálculo de σ_AR.

    Returns:
        DataFrame com colunas c_vial_mM, c_flask_mM, lod_mM, loq_mM
        adicionadas/atualizadas (cópia).
    """
    result = df.copy()

    c_is_vial_mM   = float(config.get("c_is_vial_mM",   0.0))
    dilution_factor = float(config.get("dilution_factor", 1.0))

    # σ do area_ratio = σ_baseline / area_IS (propagação de incerteza)
    sigma_AR = safe_div(sigma_baseline, area_IS, fallback=0.0)

    c_vial_list:  list[float] = []
    c_flask_list: list[float] = []
    lod_list:     list[float] = []
    loq_list:     list[float] = []

    for _, row in result.iterrows():
        keep             = bool(row.get("keep", True))
        use_calibration  = bool(row.get("use_calibration", False))
        area_ratio       = float(row.get("area_ratio", 0.0))
        rrf              = float(row.get("rrf", 1.0))
        calib_slope      = float(row.get("calib_slope", 0.0))
        calib_intercept  = float(row.get("calib_intercept", 0.0))

        if not keep or area_ratio == 0.0:
            c_vial_list.append(0.0)
            c_flask_list.append(0.0)
            lod_list.append(0.0)
            loq_list.append(0.0)
            continue

        if use_calibration and calib_slope != 0.0:
            # ── Modo calibração ───────────────────────────────────────────────
            c_vial = safe_div(
                area_ratio - calib_intercept,
                calib_slope,
                fallback=0.0,
            )
            c_vial = max(c_vial, 0.0)

            lod_factor = 3.3
            loq_factor = 10.0

            lod = lod_factor * safe_div(sigma_AR, calib_slope, 0.0) * c_is_vial_mM * dilution_factor
            loq = loq_factor * safe_div(sigma_AR, calib_slope, 0.0) * c_is_vial_mM * dilution_factor

        else:
            # ── Modo RRF ──────────────────────────────────────────────────────
            c_vial = safe_div(area_ratio, rrf, fallback=0.0) * c_is_vial_mM
            c_vial = max(c_vial, 0.0)

            # LOD/LOQ via RRF: σ_AR / (rrf × area_IS) × c_IS × dilution
            rrf_x_area_IS = rrf * area_IS if area_IS > 0 else 0.0
            lod = 3.3  * safe_div(sigma_baseline, rrf_x_area_IS, 0.0) * c_is_vial_mM * dilution_factor
            loq = 10.0 * safe_div(sigma_baseline, rrf_x_area_IS, 0.0) * c_is_vial_mM * dilution_factor

        c_flask = c_vial * dilution_factor

        c_vial_list.append(round(c_vial,  6))
        c_flask_list.append(round(c_flask, 6))
        lod_list.append(round(max(lod, 0.0), 6))
        loq_list.append(round(max(loq, 0.0), 6))

    result["c_vial_mM"]  = c_vial_list
    result["c_flask_mM"] = c_flask_list
    result["lod_mM"]     = lod_list
    result["loq_mM"]     = loq_list

    return result