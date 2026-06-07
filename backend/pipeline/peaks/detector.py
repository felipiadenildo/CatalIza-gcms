import numpy as np
from scipy.signal import find_peaks, peak_prominences, peak_widths


def find(
    tic_smooth: np.ndarray,
    min_prominence_pct: float = 5.0,
    min_width_scans: int = 3,
    min_height_abs: float = 0.0,
    min_distance_scans: int = 1,
) -> tuple[np.ndarray, dict]:
    """
    Detecta picos no TIC suavizado usando scipy.signal.find_peaks.

    A proeminência mínima é calculada como percentual da altura máxima
    do TIC, tornando o detector adaptativo ao sinal de cada arquivo.

    Args:
        tic_smooth:          Array do TIC suavizado (tic_smooth do ProcResult).
        min_prominence_pct:  % da altura máxima do TIC usada como proeminência
                             mínima para aceitar um pico.
        min_width_scans:     Largura mínima em número de scans (a meia-altura).
        min_height_abs:      Altura absoluta mínima. 0.0 = desativado.
        min_distance_scans:  Distância mínima entre dois ápices consecutivos.

    Returns:
        Tupla (peak_indices, properties_dict) onde:
          peak_indices    — array int64 com os índices dos ápices detectados.
          properties_dict — dicionário com prominences, widths, heights
                            (compatível com o retorno do scipy).
        Retorna (array vazio, {}) se nenhum pico for encontrado.
    """
    if len(tic_smooth) == 0:
        return np.array([], dtype=np.int64), {}

    max_height = float(np.max(tic_smooth))
    if max_height == 0.0:
        return np.array([], dtype=np.int64), {}

    min_prominence = max_height * min_prominence_pct / 100.0

    kwargs: dict = {
        "prominence": min_prominence,
        "width": min_width_scans,
        "distance": max(1, int(min_distance_scans)),
    }
    if min_height_abs > 0.0:
        kwargs["height"] = min_height_abs

    peak_indices, properties = find_peaks(tic_smooth.astype(np.float64), **kwargs)

    if len(peak_indices) == 0:
        return np.array([], dtype=np.int64), {}

    # Recalcula proeminências e larguras com maior precisão
    prominences, _, _ = peak_prominences(tic_smooth.astype(np.float64), peak_indices)
    widths, width_heights, left_ips, right_ips = peak_widths(
        tic_smooth.astype(np.float64), peak_indices, rel_height=0.5
    )

    properties["prominences"] = prominences
    properties["widths"] = widths
    properties["width_heights"] = width_heights
    properties["left_ips"] = left_ips
    properties["right_ips"] = right_ips

    if "peak_heights" not in properties:
        properties["peak_heights"] = tic_smooth[peak_indices].astype(np.float64)

    return peak_indices.astype(np.int64), properties


def compute_bounds(
    tic_smooth: np.ndarray,
    peak_indices: np.ndarray,
    properties: dict,
    method: str = "half_width",
) -> tuple[np.ndarray, np.ndarray]:
    """
    Calcula os bounds (esquerdo e direito) de integração de cada pico.

    Métodos disponíveis:
      "half_width"   — usa os pontos de interseção a 50% da altura do pico
                       calculados pelo scipy.signal.peak_widths. Padrão ASTM E1948.
      "valley"       — usa o vale entre picos adjacentes como bound.
                       Bound externo = início/fim do array.
      "tangent_skim" — ajusta uma exponencial decrescente nas caudas do pico
                       e usa o ponto onde a tangente encontra a baseline.
                       Referência: literatura de GC (exponential skim).

    Args:
        tic_smooth:    Array do TIC suavizado.
        peak_indices:  Array int64 com índices dos ápices (saída de `find`).
        properties:    Dicionário de propriedades (saída de `find`).
        method:        "half_width" | "valley" | "tangent_skim"

    Returns:
        Tupla (left_idxs, right_idxs) como arrays int64.
        Valores garantidamente dentro de [0, len(tic_smooth)-1].
    """
    n = len(tic_smooth)
    n_peaks = len(peak_indices)

    if n_peaks == 0:
        return np.array([], dtype=np.int64), np.array([], dtype=np.int64)

    if method == "half_width":
        return _bounds_half_width(tic_smooth, peak_indices, properties, n)

    if method == "valley":
        return _bounds_valley(tic_smooth, peak_indices, n)

    if method == "tangent_skim":
        return _bounds_tangent_skim(tic_smooth, peak_indices, n)

    # Fallback seguro
    return _bounds_half_width(tic_smooth, peak_indices, properties, n)


def _bounds_half_width(
    tic_smooth: np.ndarray,
    peak_indices: np.ndarray,
    properties: dict,
    n: int,
) -> tuple[np.ndarray, np.ndarray]:
    """Bounds pelo método half_width (left_ips / right_ips do scipy)."""
    left_ips = properties.get("left_ips", None)
    right_ips = properties.get("right_ips", None)

    if left_ips is None or right_ips is None:
        # Fallback: usa ±3 scans em torno do ápice
        left_idxs = np.maximum(peak_indices - 3, 0).astype(np.int64)
        right_idxs = np.minimum(peak_indices + 3, n - 1).astype(np.int64)
        return left_idxs, right_idxs

    left_idxs = np.clip(np.floor(left_ips).astype(np.int64), 0, n - 1)
    right_idxs = np.clip(np.ceil(right_ips).astype(np.int64), 0, n - 1)

    # Garante que left < apex < right
    for i, apex in enumerate(peak_indices):
        if left_idxs[i] >= apex:
            left_idxs[i] = max(0, int(apex) - 1)
        if right_idxs[i] <= apex:
            right_idxs[i] = min(n - 1, int(apex) + 1)

    return left_idxs, right_idxs


def _bounds_valley(
    tic_smooth: np.ndarray,
    peak_indices: np.ndarray,
    n: int,
) -> tuple[np.ndarray, np.ndarray]:
    """
    Bounds pelo método valley: usa o mínimo entre picos adjacentes.
    O bound externo do primeiro/último pico vai até o início/fim do array.
    """
    n_peaks = len(peak_indices)
    left_idxs = np.zeros(n_peaks, dtype=np.int64)
    right_idxs = np.zeros(n_peaks, dtype=np.int64)

    for i, apex in enumerate(peak_indices):
        apex = int(apex)

        # Bound esquerdo: mínimo entre pico anterior e atual
        if i == 0:
            left_idxs[i] = 0
        else:
            prev_apex = int(peak_indices[i - 1])
            segment = tic_smooth[prev_apex : apex + 1]
            valley_offset = int(np.argmin(segment))
            left_idxs[i] = np.clip(prev_apex + valley_offset, 0, n - 1)

        # Bound direito: mínimo entre atual e próximo pico
        if i == n_peaks - 1:
            right_idxs[i] = n - 1
        else:
            next_apex = int(peak_indices[i + 1])
            segment = tic_smooth[apex : next_apex + 1]
            valley_offset = int(np.argmin(segment))
            right_idxs[i] = np.clip(apex + valley_offset, 0, n - 1)

    return left_idxs, right_idxs


def _bounds_tangent_skim(
    tic_smooth: np.ndarray,
    peak_indices: np.ndarray,
    n: int,
) -> tuple[np.ndarray, np.ndarray]:
    """
    Bounds pelo método tangent skim (exponential skim).

    Para cada cauda do pico, ajusta uma reta tangente e encontra
    o ponto onde ela intersecta a baseline (y=0).
    Referência: GC peak integration literature.
    """
    n_peaks = len(peak_indices)
    left_idxs = np.zeros(n_peaks, dtype=np.int64)
    right_idxs = np.zeros(n_peaks, dtype=np.int64)

    tic = tic_smooth.astype(np.float64)

    for i, apex in enumerate(peak_indices):
        apex = int(apex)
        apex_height = tic[apex]

        # ── Bound esquerdo ────────────────────────────────────────────────────
        # Busca o ponto na cauda esquerda onde a inclinação muda de sinal
        # (inflexão) e projeta a tangente até y=0
        search_left = 0 if i == 0 else int(peak_indices[i - 1])
        left_bound = search_left

        for j in range(apex - 1, search_left, -1):
            if tic[j] <= 0.0:
                left_bound = j
                break
            # Tangente: slope entre j e apex
            dx = apex - j
            if dx == 0:
                continue
            slope = (apex_height - tic[j]) / dx
            if slope > 0:
                # Projeta até baseline: x_intercept = j - tic[j]/slope
                intercept = j - (tic[j] / slope if slope != 0 else 0)
                left_bound = max(search_left, int(np.floor(intercept)))
                break

        left_idxs[i] = np.clip(left_bound, 0, apex - 1)

        # ── Bound direito ─────────────────────────────────────────────────────
        search_right = n - 1 if i == n_peaks - 1 else int(peak_indices[i + 1])
        right_bound = search_right

        for j in range(apex + 1, search_right):
            if tic[j] <= 0.0:
                right_bound = j
                break
            dx = j - apex
            if dx == 0:
                continue
            slope = (tic[j] - apex_height) / dx
            if slope > 0:
                # Projeta até baseline a partir do ápice
                intercept = apex + (apex_height / slope if slope != 0 else 0)
                right_bound = min(search_right, int(np.ceil(intercept)))
                break

        right_idxs[i] = np.clip(right_bound, apex + 1, n - 1)

    return left_idxs, right_idxs


def filter_by_area(
    peak_indices: np.ndarray,
    areas: np.ndarray,
    left_idxs: np.ndarray,
    right_idxs: np.ndarray,
    min_area_pct: float = 3.0,
) -> tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
    """
    Remove picos cuja área é menor que `min_area_pct` % da área total.

    Args:
        peak_indices:  Array dos índices dos ápices.
        areas:         Array de áreas correspondentes.
        left_idxs:     Array dos bounds esquerdos.
        right_idxs:    Array dos bounds direitos.
        min_area_pct:  Percentual mínimo da área total (padrão 3%).

    Returns:
        Tupla filtrada (peak_indices, areas, left_idxs, right_idxs).
        Se nenhum pico passar no filtro, retorna arrays vazios.
    """
    if len(areas) == 0:
        return (
            np.array([], dtype=np.int64),
            np.array([], dtype=np.float64),
            np.array([], dtype=np.int64),
            np.array([], dtype=np.int64),
        )

    total_area = float(np.sum(areas))
    if total_area == 0.0:
        return (
            np.array([], dtype=np.int64),
            np.array([], dtype=np.float64),
            np.array([], dtype=np.int64),
            np.array([], dtype=np.int64),
        )

    threshold = total_area * min_area_pct / 100.0
    mask = areas >= threshold

    return (
        peak_indices[mask].astype(np.int64),
        areas[mask].astype(np.float64),
        left_idxs[mask].astype(np.int64),
        right_idxs[mask].astype(np.int64),
    )