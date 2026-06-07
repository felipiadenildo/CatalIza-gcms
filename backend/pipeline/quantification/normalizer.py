import pandas as pd


def get_IS_row(df: pd.DataFrame) -> tuple[pd.Series | None, str]:
    """
    Localiza a linha do Padrão Interno (IS) no DataFrame de picos.

    Critérios de seleção (em ordem de prioridade):
      1. role == "IS" AND keep == True
      2. Se múltiplos candidatos → seleciona o de maior área
      3. Se nenhum candidato → retorna (None, mensagem de erro FATAL)

    Args:
        df: DataFrame de picos com colunas role, keep, area.

    Returns:
        Tupla (is_row, status_msg) onde:
          is_row     — pd.Series da linha do IS ou None.
          status_msg — "OK" se encontrado, "FATAL: ..." se não encontrado.
    """
    if df.empty:
        return None, "FATAL: DataFrame de picos está vazio."

    required_cols = {"role", "keep", "area"}
    missing = required_cols - set(df.columns)
    if missing:
        return None, f"FATAL: Colunas ausentes no DataFrame: {missing}"

    candidates = df[(df["role"] == "IS") & (df["keep"] == True)]

    if candidates.empty:
        return None, (
            "FATAL: Nenhum pico com role='IS' e keep=True encontrado. "
            "Defina o padrão interno na tabela de picos."
        )

    if len(candidates) == 1:
        return candidates.iloc[0], "OK"

    # Múltiplos IS — usa o de maior área
    best_idx = candidates["area"].idxmax()
    return df.loc[best_idx], "OK"


def compute_area_ratios(df: pd.DataFrame, area_IS: float) -> pd.DataFrame:
    """
    Calcula o ratio de área de cada pico em relação ao IS.

        area_ratio = area_pico / area_IS

    Picos com keep=False recebem area_ratio = 0.0.
    Se area_IS == 0, todos os ratios são 0.0.

    Args:
        df:      DataFrame de picos com coluna area.
        area_IS: Área do pico IS (float).

    Returns:
        DataFrame com coluna area_ratio adicionada/atualizada (cópia).
    """
    result = df.copy()

    if area_IS <= 0.0:
        result["area_ratio"] = 0.0
        return result

    keep_mask = result.get("keep", pd.Series([True] * len(result), index=result.index))

    result["area_ratio"] = result["area"].where(keep_mask, 0.0) / area_IS

    return result