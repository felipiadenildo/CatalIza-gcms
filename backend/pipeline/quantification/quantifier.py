import pandas as pd

from core.types import QuantResult
from core.utils import safe_div
from pipeline.quantification import normalizer
from pipeline.quantification import concentrations as conc_mod
from pipeline.quantification import metrics as metrics_mod


def run(
    df: pd.DataFrame,
    config: dict,
    sigma_baseline: float = 0.0,
) -> tuple[pd.DataFrame, QuantResult]:
    """
    Pipeline completo de quantificação.

    Executa em ordem:
      1. apply_overrides          — aplica calibration_override do config
      2. get_IS_row               — localiza o IS (FATAL se ausente)
      3. compute_area_ratios      — area_ratio = area / area_IS
      4. concentrations.compute   — c_vial, c_flask, LOD, LOQ
      5. metrics.conversion       — consumed_mM, conversion_pct
      6. metrics.yield_pct        — yield_pct do produto principal
      7. metrics.mass_balance     — mass_balance_pct, missing_carbon_pct
      8. metrics.selectivities    — dict {compound: sel_pct}
      9. metrics.area_percent     — dict {compound: area_pct}
     10. metrics.validate         — lista de warnings

    Atualiza a coluna selectivity_pct no DataFrame para o produto principal.

    Args:
        df:             DataFrame de picos (saída do identifier).
        config:         ReactionConfig como dict.
        sigma_baseline: σ do ruído da baseline (saída de integrator.sigma_noise).

    Returns:
        Tupla (df_updated, QuantResult) onde:
          df_updated  — DataFrame com c_vial_mM, c_flask_mM, lod_mM,
                        loq_mM, area_ratio, selectivity_pct preenchidos.
          QuantResult — TypedDict com todas as métricas consolidadas.

        Se FATAL (sem IS), retorna (df original, QuantResult com status FATAL).
    """
    # ── 1. apply_overrides ────────────────────────────────────────────────────
    df = conc_mod.apply_overrides(df, config)

    # ── 2. get_IS_row ─────────────────────────────────────────────────────────
    is_row, is_status = normalizer.get_IS_row(df)

    if is_row is None:
        return df, _fatal_result(is_status)

    area_IS = float(is_row["area"])

    # ── 3. compute_area_ratios ────────────────────────────────────────────────
    df = normalizer.compute_area_ratios(df, area_IS)

    # ── 4. concentrations.compute ─────────────────────────────────────────────
    df = conc_mod.compute(df, config, sigma_baseline, area_IS)

    # ── 5. metrics.conversion ────────────────────────────────────────────────
    consumed_mM, conversion_pct = metrics_mod.conversion(df, config)

    # ── 6. metrics.yield_pct ─────────────────────────────────────────────────
    c_max = float(config.get("c_max_product_mM", 0.0))
    main_product = str(config.get("main_product", "")).strip()

    c_product = _get_product_concentration(df, main_product)
    y_pct = metrics_mod.yield_pct(c_product, c_max)

    # ── 7. metrics.mass_balance ───────────────────────────────────────────────
    mb_pct, missing_carbon_pct = metrics_mod.mass_balance(df, consumed_mM)

    # ── 8. metrics.selectivities ──────────────────────────────────────────────
    sel_dict = metrics_mod.selectivities(df, consumed_mM)

    # Propaga selectivity_pct para cada linha do DataFrame
    df["selectivity_pct"] = df.apply(
        lambda row: sel_dict.get(str(row.get("compound_name", "")), 0.0),
        axis=1,
    )

    # ── 9. metrics.area_percent ───────────────────────────────────────────────
    area_pct_dict = metrics_mod.area_percent(df)

    # ── 10. metrics.validate ──────────────────────────────────────────────────
    interim_results = {
        "conversion_pct":   conversion_pct,
        "yield_pct":        y_pct,
        "mass_balance_pct": mb_pct,
        "is_area":          area_IS,
        "c_initial_used":   float(config.get("c_initial_mM", 0.0)),
        "c_max_used":       c_max,
        "warnings":         [],
    }
    warnings = metrics_mod.validate(interim_results, config)

    # ── Status quality ────────────────────────────────────────────────────────
    status_quality = _derive_status(warnings)

    quant: QuantResult = QuantResult(
        is_area=round(area_IS, 2),
        consumed_mM=round(consumed_mM, 6),
        conversion_pct=round(conversion_pct, 4),
        yield_pct=round(y_pct, 4),
        mass_balance_pct=round(mb_pct, 4),
        missing_carbon_pct=round(missing_carbon_pct, 4),
        selectivities=sel_dict,
        area_percent=area_pct_dict,
        warnings=warnings,
        status_quality=status_quality,
        c_initial_used=float(config.get("c_initial_mM", 0.0)),
        c_max_used=c_max,
    )

    return df, quant


# ── Helpers privados ──────────────────────────────────────────────────────────

def _get_product_concentration(df: pd.DataFrame, main_product: str) -> float:
    """
    Retorna c_flask_mM do produto principal.

    Busca por:
      1. role == "product" AND keep == True AND compound_name == main_product
      2. role == "product" AND keep == True (maior c_flask_mM se múltiplos)
      3. 0.0 se nenhum produto encontrado
    """
    if df.empty:
        return 0.0

    products = df[(df["role"] == "product") & (df["keep"] == True)]

    if products.empty:
        return 0.0

    if main_product:
        exact = products[
            products["compound_name"].astype(str).str.strip() == main_product.strip()
        ]
        if not exact.empty:
            return float(exact["c_flask_mM"].max())

    return float(products["c_flask_mM"].max())


def _fatal_result(message: str) -> QuantResult:
    """Retorna um QuantResult vazio com status FATAL."""
    return QuantResult(
        is_area=0.0,
        consumed_mM=0.0,
        conversion_pct=0.0,
        yield_pct=0.0,
        mass_balance_pct=0.0,
        missing_carbon_pct=100.0,
        selectivities={},
        area_percent={},
        warnings=[message],
        status_quality=message,
        c_initial_used=0.0,
        c_max_used=0.0,
    )


def _derive_status(warnings: list[str]) -> str:
    """
    Deriva o status_quality a partir da lista de warnings.

      - Qualquer "FATAL:" → retorna a primeira mensagem FATAL
      - Qualquer "WARNING:" → "WARNING: ver lista de alertas"
      - Sem warnings → "OK"
    """
    for w in warnings:
        if w.startswith("FATAL:"):
            return w

    if any(w.startswith("WARNING:") for w in warnings):
        return f"WARNING: {len([w for w in warnings if w.startswith('WARNING:')])} alerta(s) — ver painel."

    return "OK"