from pathlib import Path

import pandas as pd

from core.utils import norm_name
from pipeline.exporter import load_all_runs
from pipeline.identification.library_manager import LibraryManager


def load_last_config(runs_dir: Path) -> dict | None:
    """
    Retorna o ReactionConfig do run mais recente persistido.

    Útil para pré-preencher o formulário de configuração quando o
    usuário carrega um novo arquivo — evita redigitar os mesmos
    parâmetros de reação para corridas de uma mesma campanha.

    Args:
        runs_dir: Path do diretório de runs (backend/runs/).

    Returns:
        Dict do ReactionConfig do run mais recente,
        ou None se não houver nenhum run salvo.
    """
    runs = load_all_runs(runs_dir)

    if not runs:
        return None

    # load_all_runs já retorna ordenado por created_at desc
    last_run = runs[0]
    config = last_run.get("config", None)

    if not config or not isinstance(config, dict):
        return None

    return config


def suggest_config_from_peaks(
    df_peaks: pd.DataFrame,
    library: LibraryManager,
    existing: dict,
) -> dict:
    """
    Sugere campos do ReactionConfig a partir dos picos identificados.

    Heurística aplicada (NÃO sobrescreve campos já preenchidos no `existing`):
      - substrate:     primeiro pico com role="substrate" identificado
      - main_product:  primeiro pico com role="product" de maior área
      - IS (informativo): compound_name do pico com role="IS"

    Para cada sugestão:
      - Usa compound_name do pico se disponível
      - Fallback para canonical_name se compound_name vazio

    Args:
        df_peaks: DataFrame de picos com colunas compound_name,
                  canonical_name, role, keep, area.
        library:  LibraryManager para enriquecer metadados se necessário.
        existing: ReactionConfig atual como dict (campos já preenchidos
                  pelo usuário não serão sobrescritos).

    Returns:
        Dict com o ReactionConfig sugerido (merge do existing +
        sugestões para campos vazios).
    """
    suggested = dict(existing)

    if df_peaks.empty:
        return suggested

    active = df_peaks[df_peaks.get("keep", pd.Series(
        [True] * len(df_peaks), index=df_peaks.index
    )) == True]

    # ── Substrato ─────────────────────────────────────────────────────────────
    if not suggested.get("substrate", "").strip():
        substrate_rows = active[active["role"] == "substrate"]
        if not substrate_rows.empty:
            name = _best_name(substrate_rows.iloc[0])
            if name:
                suggested["substrate"] = name

    # ── Produto principal ─────────────────────────────────────────────────────
    if not suggested.get("main_product", "").strip():
        product_rows = active[active["role"] == "product"]
        if not product_rows.empty:
            # Produto de maior área
            best_idx = product_rows["area"].idxmax()
            name = _best_name(active.loc[best_idx])
            if name:
                suggested["main_product"] = name

    # ── sample_name: mantém se já preenchido ──────────────────────────────────
    if not suggested.get("sample_name", "").strip():
        suggested["sample_name"] = ""

    # ── Garante que todos os campos obrigatórios existam com defaults ─────────
    defaults = {
        "sample_name":          "",
        "substrate":            "",
        "main_product":         "",
        "c_initial_mM":         0.0,
        "c_max_product_mM":     0.0,
        "c_is_vial_mM":         0.0,
        "dilution_factor":      1.0,
        "stoichiometry":        {"default": 1.0},
        "substrate_aliases":    [],
        "mass_balance_limits":  {"low": 50.0, "high": 110.0},
        "calibration_override": {},
    }

    for key, default_val in defaults.items():
        if key not in suggested:
            suggested[key] = default_val

    return suggested


def last_preset_name(settings: dict) -> str:
    """
    Retorna o nome do último preset usado, armazenado nos settings da aplicação.

    Args:
        settings: Dict de app_settings (saída de core.settings.load).

    Returns:
        Nome do preset (str) ou string vazia se não definido.
    """
    return str(settings.get("last_preset_name", ""))


# ── Helpers privados ──────────────────────────────────────────────────────────

def _best_name(row: pd.Series) -> str:
    """
    Retorna o melhor nome disponível para um pico:
      1. compound_name se não vazio
      2. canonical_name se não vazio
      3. string vazia
    """
    compound = str(row.get("compound_name", "")).strip()
    if compound:
        return compound

    canonical = str(row.get("canonical_name", "")).strip()
    if canonical:
        return canonical

    return ""