import numpy as np

from core.types import ProcResult
from pipeline.signal import baseline as baseline_mod
from pipeline.signal import smoother as smoother_mod
from pipeline.signal import integrator as integrator_mod
from pipeline.peaks import detector as detector_mod


def process(
    rt: np.ndarray,
    tic: np.ndarray,
    settings: dict,
) -> ProcResult:
    """
    Orquestra o pipeline completo de processamento de sinal.

    Etapas executadas em ordem:
      1. Estimativa e subtração de baseline (rolling_min + subtract)
      2. Suavização do sinal corrigido (Savitzky-Golay)
      3. Detecção de picos com todos os filtros configuráveis
      4. Cálculo dos bounds de integração (método configurável)
      5. Integração das áreas (Simpson ou trapézio)
      6. Filtro de área mínima
      7. Cálculo do sigma_noise (para LOD/LOQ ICH Q2R1)

    Args:
        rt:       Array float64 de tempos de retenção em minutos (N,).
        tic:      Array float64 do TIC bruto (N,).
        settings: Dicionário de configurações — aceita tanto o dict completo
                  (com chave "signal") quanto o sub-dict "signal" diretamente.
                  Chaves usadas (com defaults seguros se ausentes):
                    baseline_window_pct   (float, default 5.0)
                    savgol_window         (int,   default 7)
                    savgol_poly           (int,   default 2)
                    min_prominence_pct    (float, default 5.0)
                    min_width_scans       (int,   default 3)
                    min_height_abs        (float, default 0.0)
                    min_distance_scans    (int,   default 1)
                    integration_method    (str,   default "simpson")
                    boundary_method       (str,   default "half_width")
                    min_area_pct          (float, default 3.0)

    Returns:
        ProcResult completo com todos os arrays preenchidos.
        Se nenhum pico for detectado, retorna empty_result(rt, tic).
    """
    # Aceita settings completo ou sub-dict "signal"
    sig = settings.get("signal", settings)

    baseline_window_pct  = float(sig.get("baseline_window_pct",  5.0))
    savgol_window        = int(sig.get("savgol_window",          7))
    savgol_poly          = int(sig.get("savgol_poly",            2))
    min_prominence_pct   = float(sig.get("min_prominence_pct",   5.0))
    min_width_scans      = int(sig.get("min_width_scans",        3))
    min_height_abs       = float(sig.get("min_height_abs",       0.0))
    min_distance_scans   = int(sig.get("min_distance_scans",     1))
    integration_method   = str(sig.get("integration_method",     "simpson"))
    boundary_method      = str(sig.get("boundary_method",        "half_width"))
    min_area_pct         = float(sig.get("min_area_pct",         3.0))

    # ── 1. Baseline ───────────────────────────────────────────────────────────
    tic_baseline  = baseline_mod.rolling_min(tic, window_pct=baseline_window_pct)
    tic_corrected = baseline_mod.subtract(tic, tic_baseline)

    # ── 2. Suavização ─────────────────────────────────────────────────────────
    tic_smooth = smoother_mod.savgol(tic_corrected, window=savgol_window, poly=savgol_poly)

    # ── 3. Detecção de picos ──────────────────────────────────────────────────
    peak_indices, properties = detector_mod.find(
        tic_smooth,
        min_prominence_pct=min_prominence_pct,
        min_width_scans=min_width_scans,
        min_height_abs=min_height_abs,
        min_distance_scans=min_distance_scans,
    )

    if len(peak_indices) == 0:
        return empty_result(rt, tic)

    # ── 4. Bounds de integração ───────────────────────────────────────────────
    left_idxs, right_idxs = detector_mod.compute_bounds(
        tic_smooth,
        peak_indices,
        properties,
        method=boundary_method,
    )

    # ── 5. Integração de áreas ────────────────────────────────────────────────
    areas = integrator_mod.compute_all(
        tic_smooth,
        rt,
        left_idxs,
        right_idxs,
        method=integration_method,
    )

    # ── 6. Filtro de área mínima ──────────────────────────────────────────────
    peak_indices, areas, left_idxs, right_idxs = detector_mod.filter_by_area(
        peak_indices,
        areas,
        left_idxs,
        right_idxs,
        min_area_pct=min_area_pct,
    )

    if len(peak_indices) == 0:
        return empty_result(rt, tic)

    # ── 7. Sigma do ruído (LOD/LOQ) ───────────────────────────────────────────
    sigma = integrator_mod.sigma_noise(tic_smooth)

    # ── Extrai propriedades filtradas ─────────────────────────────────────────
    # Re-filtra o properties dict para manter alinhamento com peak_indices filtrados
    # (filter_by_area retorna um mask implícito — recalculamos as props dos sobreviventes)
    peak_heights     = tic_smooth[peak_indices].astype(np.float64)
    peak_rts         = rt[peak_indices].astype(np.float64)
    peak_widths_min  = _compute_widths_in_minutes(rt, left_idxs, right_idxs)

    prom_arr, _, _ = __import__(
        "scipy.signal", fromlist=["peak_prominences"]
    ).peak_prominences(tic_smooth.astype(np.float64), peak_indices)

    return ProcResult(
        tic_raw=tic.astype(np.float64),
        tic_baseline=tic_baseline.astype(np.float64),
        tic_corrected=tic_corrected.astype(np.float64),
        tic_smooth=tic_smooth.astype(np.float64),
        peak_indices=peak_indices.astype(np.int64),
        peak_areas=areas.astype(np.float64),
        peak_rts=peak_rts,
        peak_left_idx=left_idxs.astype(np.int64),
        peak_right_idx=right_idxs.astype(np.int64),
        peak_heights=peak_heights,
        peak_prominences=prom_arr.astype(np.float64),
        peak_widths_min=peak_widths_min,
        sigma_baseline=sigma,
        rt_ref=rt,
    )


def empty_result(rt: np.ndarray, tic: np.ndarray) -> ProcResult:
    """
    Retorna um ProcResult válido com arrays de picos de tamanho 0.
    Usado quando nenhum pico é detectado ou passa nos filtros.
    Preserva os arrays de sinal completos para exibição no gráfico.
    """
    n = len(tic)
    empty_int   = np.array([], dtype=np.int64)
    empty_float = np.array([], dtype=np.float64)

    tic_f      = tic.astype(np.float64) if n > 0 else empty_float
    baseline   = baseline_mod.rolling_min(tic_f) if n > 0 else empty_float
    corrected  = baseline_mod.subtract(tic_f, baseline) if n > 0 else empty_float
    smooth     = smoother_mod.savgol(corrected) if n > 0 else empty_float

    return ProcResult(
        tic_raw=tic_f,
        tic_baseline=baseline,
        tic_corrected=corrected,
        tic_smooth=smooth,
        peak_indices=empty_int,
        peak_areas=empty_float,
        peak_rts=empty_float,
        peak_left_idx=empty_int,
        peak_right_idx=empty_int,
        peak_heights=empty_float,
        peak_prominences=empty_float,
        peak_widths_min=empty_float,
        sigma_baseline=0.0,
        rt_ref=rt,
    )


def _compute_widths_in_minutes(
    rt: np.ndarray,
    left_idxs: np.ndarray,
    right_idxs: np.ndarray,
) -> np.ndarray:
    """
    Calcula a largura de cada pico em minutos (rt[right] - rt[left]).
    Usado apenas para metadados — não afeta a integração.
    """
    if len(left_idxs) == 0:
        return np.array([], dtype=np.float64)

    widths = np.array(
        [
            float(rt[int(r)]) - float(rt[int(l)])
            for l, r in zip(left_idxs, right_idxs)
        ],
        dtype=np.float64,
    )
    return np.maximum(widths, 0.0)