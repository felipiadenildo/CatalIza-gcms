import numpy as np
from scipy.ndimage import gaussian_filter1d
from scipy.signal import savgol_filter


def savgol(tic: np.ndarray, window: int = 7, poly: int = 2) -> np.ndarray:
    """
    Suaviza o TIC com o filtro Savitzky-Golay.

    O filtro ajusta um polinômio local de grau `poly` a uma janela deslizante
    de `window` pontos, preservando a forma dos picos melhor que uma média
    móvel simples.

    Garantias aplicadas automaticamente:
      - window deve ser ímpar (incrementado em 1 se par)
      - window deve ser > poly + 1 (aumentado se necessário)
      - window não pode exceder len(tic) (truncado se necessário)
      - resultado clampado em >= 0

    Args:
        tic:    Array 1-D do TIC corrigido pela baseline.
        window: Número de pontos da janela (deve ser ímpar).
        poly:   Grau do polinômio de ajuste.

    Returns:
        Array suavizado de mesma forma que `tic`, sem valores negativos.
    """
    n = len(tic)
    if n == 0:
        return np.array([], dtype=np.float64)

    # Garante janela ímpar
    if window % 2 == 0:
        window += 1

    # Garante window > poly + 1
    min_window = poly + 2
    if min_window % 2 == 0:
        min_window += 1
    window = max(window, min_window)

    # Janela não pode exceder o tamanho do array
    if window > n:
        window = n if n % 2 != 0 else n - 1
        window = max(window, min_window)

    # Se ainda assim não for possível aplicar (array muito pequeno), retorna cópia
    if window > n or window <= poly:
        return np.maximum(tic.astype(np.float64), 0.0)

    smoothed = savgol_filter(tic.astype(np.float64), window_length=window, polyorder=poly)
    return np.maximum(smoothed, 0.0)


def gaussian(tic: np.ndarray, sigma: float = 1.0) -> np.ndarray:
    """
    Suaviza o TIC com um filtro Gaussiano.

    Alternativa ao Savitzky-Golay para cromatogramas com picos muito estreitos
    ou altamente sobrepostos, onde o SG pode introduzir artefatos.

    Args:
        tic:   Array 1-D do TIC corrigido pela baseline.
        sigma: Desvio-padrão da gaussiana em número de pontos.
               Valores maiores = suavização mais agressiva.

    Returns:
        Array suavizado de mesma forma que `tic`, sem valores negativos.
    """
    if len(tic) == 0:
        return np.array([], dtype=np.float64)

    smoothed = gaussian_filter1d(tic.astype(np.float64), sigma=sigma)
    return np.maximum(smoothed, 0.0)