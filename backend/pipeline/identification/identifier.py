import numpy as np
import pandas as pd

from core.types import ProcResult, ScanDict
from core.utils import norm_name
from pipeline.identification.library_manager import LibraryManager
from pipeline.identification.rt_matcher import match as rt_match
from pipeline.identification.spectral_matcher import SpectralMatcher


# Score mínimo do RT matcher para não acionar o fallback WDP
_RT_SCORE_THRESHOLD = 0.7


def identify(
    proc: ProcResult,
    scans: list[ScanDict],
    matcher: SpectralMatcher,
    library: LibraryManager,
    config: dict,
) -> pd.DataFrame:
    """
    Identifica compostos para cada pico detectado no ProcResult.

    Para cada pico:
      1. Extrai o espectro MS do scan mais próximo ao ápice (find_scan_at_rt).
      2. Tenta rt_matcher.match (primário).
      3. Se score < _RT_SCORE_THRESHOLD → tenta spectral_matcher.match (fallback).
      4. Define id_method: "RT" | "WDP" | "unassigned".
      5. Propaga rrf, calib_slope, calib_intercept, stoichiometry da library.
      6. Chama library.auto_assign_roles com o config da reação.

    Args:
        proc:    ProcResult completo do processor.
        scans:   Lista de ScanDict do RawData (ordem original do arquivo).
        matcher: SpectralMatcher já inicializado (pode estar em modo degradado).
        library: LibraryManager já carregado.
        config:  ReactionConfig como dict.

    Returns:
        DataFrame com uma linha por pico detectado e as colunas:
          peak_id, keep, rt_min, rt_left, rt_right,
          area, area_pct, compound_name, canonical_name,
          cas, role, rrf, calib_slope, calib_intercept,
          use_calibration, stoichiometry, match_score,
          match_confidence, id_method, spectrum_idx,
          area_ratio, c_vial_mM, c_flask_mM,
          lod_mM, loq_mM, selectivity_pct
        (campos calculados inicializados em 0.0 — preenchidos pelo quantifier)
    """
    n_peaks = len(proc["peak_indices"])

    if n_peaks == 0:
        return _empty_dataframe()

    rt_ref       = proc["rt_ref"]
    peak_indices = proc["peak_indices"]
    peak_areas   = proc["peak_areas"]
    left_idxs    = proc["peak_left_idx"]
    right_idxs   = proc["peak_right_idx"]

    total_area = float(np.sum(peak_areas))

    rows: list[dict] = []

    for i in range(n_peaks):
        apex_idx  = int(peak_indices[i])
        left_idx  = int(left_idxs[i])
        right_idx = int(right_idxs[i])
        area      = float(peak_areas[i])
        area_pct  = (area / total_area * 100.0) if total_area > 0 else 0.0

        rt_apex  = float(rt_ref[apex_idx])
        rt_left  = float(rt_ref[left_idx])
        rt_right = float(rt_ref[right_idx])

        # ── 1. Extrai espectro do scan mais próximo ao ápice ──────────────────
        scan_idx = _find_scan_at_rt(scans, rt_apex)
        mz_arr   = np.array([], dtype=np.float32)
        int_arr  = np.array([], dtype=np.float32)

        if 0 <= scan_idx < len(scans):
            mz_arr  = scans[scan_idx]["mz"]
            int_arr = scans[scan_idx]["intensity"]

        # ── 2. RT matching (primário) ─────────────────────────────────────────
        rt_name, rt_score, rt_conf = rt_match(rt_apex, mz_arr, int_arr, library)

        compound_name   = rt_name or ""
        match_score     = rt_score
        match_confidence = rt_conf
        id_method       = "RT" if rt_name else "unassigned"

        # ── 3. Fallback WDP se RT score insuficiente ──────────────────────────
        if rt_score < _RT_SCORE_THRESHOLD and matcher.is_ready and len(mz_arr) > 0:
            wdp_name, wdp_score, wdp_conf = matcher.match(mz_arr, int_arr)
            if wdp_score > rt_score:
                compound_name    = wdp_name or ""
                match_score      = wdp_score
                match_confidence = wdp_conf
                id_method        = "WDP" if wdp_name else "unassigned"

        # ── 4. Canonical name ─────────────────────────────────────────────────
        canonical_name = norm_name(compound_name) if compound_name else ""

        # ── 5. Propaga metadados da library ───────────────────────────────────
        cas             = ""
        role            = "unknown"
        rrf             = 1.0
        calib_slope     = 0.0
        calib_intercept = 0.0
        use_calibration = False
        stoichiometry   = 1.0

        if canonical_name:
            lib_row = library.lookup_by_name(canonical_name)
            if lib_row:
                cas             = str(lib_row.get("cas", ""))
                role            = str(lib_row.get("role", "unknown"))
                rrf             = float(lib_row.get("rrf", 1.0))
                calib_slope     = float(lib_row.get("calib_slope", 0.0))
                calib_intercept = float(lib_row.get("calib_intercept", 0.0))
                use_calibration = bool(lib_row.get("use_calibration", False))
                stoichiometry   = float(lib_row.get("stoichiometry", 1.0))

        rows.append({
            "peak_id":          i + 1,
            "keep":             True,
            "rt_min":           round(rt_apex,  4),
            "rt_left":          round(rt_left,  4),
            "rt_right":         round(rt_right, 4),
            "area":             round(area, 2),
            "area_pct":         round(area_pct, 4),
            "compound_name":    compound_name,
            "canonical_name":   canonical_name,
            "cas":              cas,
            "role":             role,
            "rrf":              rrf,
            "calib_slope":      calib_slope,
            "calib_intercept":  calib_intercept,
            "use_calibration":  use_calibration,
            "stoichiometry":    stoichiometry,
            "match_score":      round(match_score, 4),
            "match_confidence": match_confidence,
            "id_method":        id_method,
            "spectrum_idx":     scan_idx,
            # Campos calculados — preenchidos pelo quantifier
            "area_ratio":       0.0,
            "c_vial_mM":        0.0,
            "c_flask_mM":       0.0,
            "lod_mM":           0.0,
            "loq_mM":           0.0,
            "selectivity_pct":  0.0,
        })

    df = pd.DataFrame(rows)

    # ── 6. Auto-assign roles ──────────────────────────────────────────────────
    df = library.auto_assign_roles(df, config)

    return df


def _find_scan_at_rt(scans: list[ScanDict], rt_min: float) -> int:
    """
    Retorna o índice do scan mais próximo a `rt_min` usando busca linear.
    Fallback seguro para listas pequenas sem overhead de bisect.
    """
    if not scans:
        return -1

    best_idx   = 0
    best_delta = abs(scans[0]["rt"] - rt_min)

    for i, scan in enumerate(scans):
        delta = abs(scan["rt"] - rt_min)
        if delta < best_delta:
            best_delta = delta
            best_idx   = i
        elif delta > best_delta:
            # Lista ordenada por RT — pode parar cedo
            break

    return best_idx


def _empty_dataframe() -> pd.DataFrame:
    """Retorna DataFrame vazio com o schema completo do identifier."""
    cols = [
        "peak_id", "keep", "rt_min", "rt_left", "rt_right",
        "area", "area_pct", "compound_name", "canonical_name",
        "cas", "role", "rrf", "calib_slope", "calib_intercept",
        "use_calibration", "stoichiometry", "match_score",
        "match_confidence", "id_method", "spectrum_idx",
        "area_ratio", "c_vial_mM", "c_flask_mM",
        "lod_mM", "loq_mM", "selectivity_pct",
    ]
    return pd.DataFrame(columns=cols)