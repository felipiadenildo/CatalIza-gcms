from typing import TypedDict
import numpy as np


class ScanDict(TypedDict):
    """Um único scan MS: vetor de m/z e intensidades correspondentes."""
    rt: float
    mz: np.ndarray        # float32 — vetor de m/z
    intensity: np.ndarray # float32 — vetor de intensidades


class RawData(TypedDict):
    """Dados brutos extraídos do arquivo .mzXML pelo reader."""
    rt: np.ndarray    # (N,) float64 — tempos de retenção em minutos
    tic: np.ndarray   # (N,) float64 — TIC total (soma das intensidades por scan)
    scans: list[ScanDict]


class ProcResult(TypedDict):
    """Resultado completo do processamento de sinal pelo processor."""
    tic_raw:          np.ndarray   # TIC original (cópia do RawData.tic)
    tic_baseline:     np.ndarray   # baseline estimada pelo mínimo deslizante
    tic_corrected:    np.ndarray   # TIC - baseline (clampado em 0)
    tic_smooth:       np.ndarray   # TIC suavizado (Savitzky-Golay)
    peak_indices:     np.ndarray   # int64 — índices dos ápices no array rt
    peak_areas:       np.ndarray   # float64 — área integrada de cada pico
    peak_rts:         np.ndarray   # float64 — RT do ápice em minutos
    peak_left_idx:    np.ndarray   # int64 — índice do bound esquerdo
    peak_right_idx:   np.ndarray   # int64 — índice do bound direito
    peak_heights:     np.ndarray   # float64 — altura do ápice no TIC suavizado
    peak_prominences: np.ndarray   # float64 — proeminência calculada pelo scipy
    peak_widths_min:  np.ndarray   # float64 — largura a meia-altura em minutos
    sigma_baseline:   float        # desvio-padrão do ruído da baseline (para LOD/LOQ)
    rt_ref:           np.ndarray   # referência ao array rt do RawData (sem cópia)


class QuantResult(TypedDict):
    """Resultado quantitativo final calculado pelo quantifier."""
    is_area:            float
    consumed_mM:        float
    conversion_pct:     float
    yield_pct:          float
    mass_balance_pct:   float
    missing_carbon_pct: float
    selectivities:      dict[str, float]
    area_percent:       dict[str, float]
    warnings:           list[str]
    status_quality:     str   # "OK" | "WARNING: ..." | "FATAL: ..."
    c_initial_used:     float
    c_max_used:         float