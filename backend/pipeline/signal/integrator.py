import numpy as np
from scipy.integrate import simpson


def simpson_area(
    tic: np.ndarray,
    rt: np.ndarray,
    left_idx: int,
    right_idx: int,
) -> float:
    """
    Calcula a área de um pico pelo método de Simpson.

    Usa scipy.integrate.simpson sobre o segmento [left_idx, right_idx]
    do TIC suavizado, com o eixo x sendo o tempo de retenção em minutos.

    Args:
        tic:       Array do TIC suavizado (tic_smooth).
        rt:        Array de tempos de retenção em minutos.
        left_idx:  Índice do bound esquerdo do pico.
        right_idx: Índice do bound direito do pico (inclusivo).

    Returns:
        Área do pico (float). Retorna 0.0 se o segmento for inválido.
    """
    left_idx = int(left_idx)
    right_idx = int(right_idx)

    if left_idx < 0 or right_idx >= len(tic) or right_idx <= left_idx:
        return 0.0

    y = tic[left_idx : right_idx + 1].astype(np.float64)
    x = rt[left_idx : right_idx + 1].astype(np.float64)

    if len(y) < 2:
        return 0.0

    area = float(simpson(y=y, x=x))
    return max(area, 0.0)


def trapezoid_area(
    tic: np.ndarray,
    rt: np.ndarray,
    left_idx: int,
    right_idx: int,
) -> float:
    """
    Calcula a área de um pico pelo método do trapézio.

    Alternativa ao Simpson para picos com poucos pontos de amostragem
    ou formas irregulares onde o polinômio de Simpson pode oscilar.

    Args:
        tic:       Array do TIC suavizado (tic_smooth).
        rt:        Array de tempos de retenção em minutos.
        left_idx:  Índice do bound esquerdo do pico.
        right_idx: Índice do bound direito do pico (inclusivo).

    Returns:
        Área do pico (float). Retorna 0.0 se o segmento for inválido.
    """
    left_idx = int(left_idx)
    right_idx = int(right_idx)

    if left_idx < 0 or right_idx >= len(tic) or right_idx <= left_idx:
        return 0.0

    y = tic[left_idx : right_idx + 1].astype(np.float64)
    x = rt[left_idx : right_idx + 1].astype(np.float64)

    if len(y) < 2:
        return 0.0

    area = float(np.trapezoid(y=y, x=x))
    return max(area, 0.0)


def compute_all(
    tic: np.ndarray,
    rt: np.ndarray,
    left_idxs: np.ndarray,
    right_idxs: np.ndarray,
    method: str = "simpson",
) -> np.ndarray:
    """
    Calcula a área integrada de todos os picos detectados.

    Args:
        tic:        Array do TIC suavizado.
        rt:         Array de tempos de retenção em minutos.
        left_idxs:  Array int64 com os índices dos bounds esquerdos.
        right_idxs: Array int64 com os índices dos bounds direitos.
        method:     "simpson" (padrão) ou "trapezoid".

    Returns:
        Array float64 de áreas, um valor por pico.
        Tamanho igual a len(left_idxs).
    """
    if len(left_idxs) == 0:
        return np.array([], dtype=np.float64)

    integrate_fn = simpson_area if method == "simpson" else trapezoid_area

    areas = np.array(
        [
            integrate_fn(tic, rt, int(l), int(r))
            for l, r in zip(left_idxs, right_idxs)
        ],
        dtype=np.float64,
    )
    return areas


def sigma_noise(tic_smooth: np.ndarray, pct: float = 0.05) -> float:
    """
    Estima o desvio-padrão do ruído da baseline a partir dos primeiros
    `pct * N` pontos do TIC suavizado.

    Esses pontos correspondem ao início do cromatograma, antes do
    primeiro pico, onde o sinal é predominantemente ruído.
    Usado como σ_baseline para cálculo de LOD/LOQ (ICH Q2R1):
        LOD = 3.3 × σ / slope
        LOQ = 10.0 × σ / slope

    Args:
        tic_smooth: Array do TIC suavizado.
        pct:        Fração inicial do array usada (padrão: 5%).

    Returns:
        Desvio-padrão (float). Retorna 0.0 se não houver pontos suficientes.
    """
    n = len(tic_smooth)
    if n == 0:
        return 0.0

    n_points = max(1, int(n * pct))
    segment = tic_smooth[:n_points].astype(np.float64)

    if len(segment) < 2:
        return 0.0

    return float(np.std(segment, ddof=1))