import pandas as pd

from core.utils import safe_div


def conversion(
    df: pd.DataFrame,
    config: dict,
) -> tuple[float, float]:
    """
    Calcula a conversão do substrato.

        consumed_mM = c_initial_mM - c_substrate_flask_mM
        conversion% = consumed_mM / c_initial_mM × 100

    O substrato é identificado pela coluna role == "substrate" com keep=True.
    Se múltiplos picos forem substrato, usa o de maior c_flask_mM.
    Se nenhum pico de substrato for encontrado, usa c_initial como consumido
    (conversão = 100% — caso de consumo total).

    Args:
        df:     DataFrame com colunas role, keep, c_flask_mM.
        config: ReactionConfig como dict com chave c_initial_mM.

    Returns:
        Tupla (consumed_mM, conversion_pct).
        Ambos retornam 0.0 se c_initial_mM == 0.
    """
    c_initial = float(config.get("c_initial_mM", 0.0))

    if c_initial <= 0.0:
        return 0.0, 0.0

    substrate_rows = df[(df["role"] == "substrate") & (df["keep"] == True)]

    if substrate_rows.empty:
        # Substrato não detectado → consumo total
        return c_initial, 100.0

    c_substrate = float(substrate_rows["c_flask_mM"].max())
    consumed = max(c_initial - c_substrate, 0.0)
    conv_pct = safe_div(consumed, c_initial, fallback=0.0) * 100.0

    return round(consumed, 6), round(min(conv_pct, 100.0), 4)


def yield_pct(c_product: float, c_max: float) -> float:
    """
    Calcula o yield do produto principal.

        yield% = c_product_flask / c_max_product × 100

    Args:
        c_product: Concentração do produto principal no frasco (mM).
        c_max:     Concentração máxima teórica do produto (mM).
                   Tipicamente igual a c_initial_mM × stoichiometry.

    Returns:
        yield% como float. Retorna 0.0 se c_max == 0.
        Clampado em [0, 100].
    """
    result = safe_div(c_product, c_max, fallback=0.0) * 100.0
    return round(min(max(result, 0.0), 100.0), 4)


def mass_balance(
    df: pd.DataFrame,
    consumed_mM: float,
) -> tuple[float, float]:
    """
    Calcula o balanço de massa e o carbono não contabilizado.

        MB% = Σ(c_flask_i / stoichiometry_i) / consumed_mM × 100
        missing_carbon% = max(100 - MB%, 0)

    Inclui apenas picos com:
      - keep == True
      - role in ("product", "byproduct", "substrate")
      - c_flask_mM > 0

    O IS é excluído do balanço (não é produto da reação).

    Args:
        df:          DataFrame com colunas role, keep, c_flask_mM, stoichiometry.
        consumed_mM: Moles consumidos do substrato (saída de conversion()).

    Returns:
        Tupla (mass_balance_pct, missing_carbon_pct).
        Retorna (0.0, 100.0) se consumed_mM == 0.
    """
    if consumed_mM <= 0.0:
        return 0.0, 100.0

    roles_include = {"product", "byproduct", "substrate"}
    active = df[
        (df["keep"] == True)
        & (df["role"].isin(roles_include))
        & (df["c_flask_mM"] > 0)
    ]

    if active.empty:
        return 0.0, 100.0

    total_equiv = 0.0
    for _, row in active.iterrows():
        c_flask      = float(row["c_flask_mM"])
        stoich       = float(row.get("stoichiometry", 1.0))
        stoich       = stoich if stoich > 0 else 1.0
        total_equiv += c_flask / stoich

    mb_pct = safe_div(total_equiv, consumed_mM, fallback=0.0) * 100.0
    mb_pct = round(mb_pct, 4)
    missing = round(max(100.0 - mb_pct, 0.0), 4)

    return mb_pct, missing


def selectivities(
    df: pd.DataFrame,
    consumed_mM: float,
) -> dict[str, float]:
    """
    Calcula a seletividade de cada produto/subproduto.

        sel_i% = c_flask_i / (consumed_mM × stoichiometry_i) × 100

    Inclui apenas picos com:
      - keep == True
      - role in ("product", "byproduct")
      - c_flask_mM > 0
      - compound_name não vazio

    Args:
        df:          DataFrame com colunas compound_name, role, keep,
                     c_flask_mM, stoichiometry.
        consumed_mM: Moles consumidos do substrato.

    Returns:
        Dict {compound_name: selectivity_pct}.
        Dict vazio se consumed_mM == 0 ou sem produtos.
    """
    if consumed_mM <= 0.0:
        return {}

    roles_include = {"product", "byproduct"}
    active = df[
        (df["keep"] == True)
        & (df["role"].isin(roles_include))
        & (df["c_flask_mM"] > 0)
        & (df["compound_name"].astype(str).str.strip() != "")
    ]

    result: dict[str, float] = {}

    for _, row in active.iterrows():
        name    = str(row["compound_name"]).strip()
        c_flask = float(row["c_flask_mM"])
        stoich  = float(row.get("stoichiometry", 1.0))
        stoich  = stoich if stoich > 0 else 1.0

        sel = safe_div(c_flask, consumed_mM * stoich, fallback=0.0) * 100.0
        sel = round(min(max(sel, 0.0), 100.0), 4)

        # Se nome duplicado (mesmo composto, roles diferentes), soma
        result[name] = result.get(name, 0.0) + sel

    return result


def area_percent(df: pd.DataFrame) -> dict[str, float]:
    """
    Calcula o percentual de área de cada composto identificado.

        area_pct_i = area_i / Σarea_total × 100

    Inclui apenas picos com keep=True e compound_name não vazio.
    O IS é incluído (área bruta, sem correção por RRF).

    Args:
        df: DataFrame com colunas compound_name, keep, area.

    Returns:
        Dict {compound_name: area_pct}.
        Picos sem nome são agrupados em "unassigned".
    """
    active = df[df["keep"] == True]

    if active.empty:
        return {}

    total_area = float(active["area"].sum())
    if total_area <= 0.0:
        return {}

    result: dict[str, float] = {}

    for _, row in active.iterrows():
        name  = str(row.get("compound_name", "")).strip() or "unassigned"
        area  = float(row.get("area", 0.0))
        pct   = safe_div(area, total_area, fallback=0.0) * 100.0

        result[name] = result.get(name, 0.0) + round(pct, 4)

    return result


def validate(results: dict, config: dict) -> list[str]:
    """
    Gera lista de warnings e erros de validação dos resultados quantitativos.

    Verificações realizadas:
      - Conversão negativa ou > 100%
      - Yield > 100%
      - Balanço de massa fora da janela aceitável (low/high do config)
      - c_initial_mM == 0 (impossível calcular conversão)
      - c_max_product_mM == 0 (impossível calcular yield)
      - Nenhum IS definido (FATAL)
      - Picos abaixo do LOD

    Args:
        results: Dict com chaves conversion_pct, yield_pct,
                 mass_balance_pct, is_area, c_initial_used,
                 c_max_used, warnings (lista existente).
        config:  ReactionConfig como dict.

    Returns:
        Lista de strings de warning/erro. Lista vazia = tudo OK.
        Prefixo "FATAL:" indica erro crítico que invalida os resultados.
        Prefixo "WARNING:" indica anomalia que merece atenção.
    """
    warnings: list[str] = list(results.get("warnings", []))

    conv_pct  = float(results.get("conversion_pct",    0.0))
    yield_val = float(results.get("yield_pct",         0.0))
    mb_pct    = float(results.get("mass_balance_pct",  0.0))
    is_area   = float(results.get("is_area",           0.0))
    c_initial = float(results.get("c_initial_used",    0.0))
    c_max     = float(results.get("c_max_used",        0.0))

    mb_low  = float(config.get("mass_balance_limits", {}).get("low",  50.0))
    mb_high = float(config.get("mass_balance_limits", {}).get("high", 110.0))

    # ── Verificações FATAL ────────────────────────────────────────────────────
    if is_area <= 0.0:
        warnings.append(
            "FATAL: Padrão interno (IS) não encontrado ou área zero. "
            "Quantificação impossível."
        )

    # ── Verificações WARNING ──────────────────────────────────────────────────
    if c_initial <= 0.0:
        warnings.append(
            "WARNING: c_initial_mM não definido. "
            "Conversão não pode ser calculada."
        )

    if c_max <= 0.0:
        warnings.append(
            "WARNING: c_max_product_mM não definido. "
            "Yield não pode ser calculado."
        )

    if conv_pct < 0.0:
        warnings.append(
            f"WARNING: Conversão negativa ({conv_pct:.2f}%). "
            "Verifique c_initial_mM e a identificação do substrato."
        )

    if conv_pct > 100.0:
        warnings.append(
            f"WARNING: Conversão > 100% ({conv_pct:.2f}%). "
            "Verifique calibração ou RRF do substrato."
        )

    if yield_val > 100.0:
        warnings.append(
            f"WARNING: Yield > 100% ({yield_val:.2f}%). "
            "Verifique c_max_product_mM ou calibração do produto."
        )

    if c_initial > 0.0 and mb_pct < mb_low:
        warnings.append(
            f"WARNING: Balanço de massa baixo ({mb_pct:.1f}% < {mb_low:.0f}%). "
            "Possível perda de material, decomposição ou pico não identificado."
        )

    if c_initial > 0.0 and mb_pct > mb_high:
        warnings.append(
            f"WARNING: Balanço de massa alto ({mb_pct:.1f}% > {mb_high:.0f}%). "
            "Verifique RRF, calibração ou presença de impurezas no IS."
        )

    return warnings


# ── Hooks futuros (assinatura pronta, implementação pendente) ─────────────────

def enantiomeric_excess(c_r: float, c_s: float) -> float:
    """ee% = |c_R - c_S| / (c_R + c_S) × 100"""
    total = c_r + c_s
    return safe_div(abs(c_r - c_s), total, fallback=0.0) * 100.0


def turnover_number(c_product: float, c_catalyst: float) -> float:
    """TON = c_product / c_catalyst"""
    return safe_div(c_product, c_catalyst, fallback=0.0)


def turnover_frequency(ton: float, time_hours: float) -> float:
    """TOF = TON / time_hours"""
    return safe_div(ton, time_hours, fallback=0.0)


def diastereomeric_ratio(c_a: float, c_b: float) -> float:
    """dr = c_a / c_b (o maior sobre o menor, sempre >= 1)"""
    if c_a <= 0.0 and c_b <= 0.0:
        return 0.0
    major = max(c_a, c_b)
    minor = min(c_a, c_b)
    return safe_div(major, minor, fallback=0.0)