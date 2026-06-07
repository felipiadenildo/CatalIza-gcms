import numpy as np


def rolling_min(tic: np.ndarray, window_pct: float = 5.0) -> np.ndarray:
    """
    Estima a baseline do TIC pelo método do mínimo deslizante.

    A janela desliza sobre o array e, para cada ponto, o valor da baseline
    é o mínimo dentro da janela centrada naquele ponto. Isso captura a
    linha de base real do cromatograma sem ser afetado pelos picos.

    Args:
        tic:        Array 1-D do TIC (pode ser raw ou corrected).
        window_pct: Percentual do número total de scans usado como largura
                    da janela. Mínimo garantido de 3 pontos.

    Returns:
        Array de mesma forma que `tic` com os valores de baseline estimados.
    """
    n = len(tic)
    if n == 0:
        return np.array([], dtype=np.float64)

    window = max(3, int(n * window_pct / 100.0))

    # Garante janela ímpar para centralização simétrica
    if window % 2 == 0:
        window += 1

    half = window // 2
    baseline = np.empty(n, dtype=np.float64)

    for i in range(n):
        left = max(0, i - half)
        right = min(n, i + half + 1)
        baseline[i] = np.min(tic[left:right])

    return baseline


def subtract(tic: np.ndarray, baseline: np.ndarray) -> np.ndarray:
    """
    Subtrai a baseline do TIC e clampeia em zero.

    Valores negativos resultantes (ruído abaixo da baseline) são
    forçados para 0.0 para evitar artefatos de integração.

    Args:
        tic:      Array do TIC original.
        baseline: Array de baseline com mesma forma que `tic`.

    Returns:
        Array corrigido: max(tic - baseline, 0).
    """
    if len(tic) == 0:
        return np.array([], dtype=np.float64)

    corrected = np.subtract(tic, baseline, dtype=np.float64)
    return np.maximum(corrected, 0.0)