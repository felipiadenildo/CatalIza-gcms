import io
import json
import uuid
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd


# Colunas fixas do CSV de histórico consolidado (ICH Q2R1)
_HISTORY_FIXED_COLS = [
    "run_id",
    "sample_name",
    "file_name",
    "created_at",
    "conversion_pct",
    "yield_pct",
    "mass_balance_pct",
    "missing_carbon_pct",
    "status_quality",
]


def save_run(data: dict, runs_dir: Path) -> str:
    """
    Persiste um run como arquivo JSON em runs/{uuid}.json.

    Estrutura do JSON salvo:
        run_id      — UUID v4 gerado aqui
        created_at  — ISO 8601 UTC
        file_name   — nome do arquivo .mzXML original
        config      — ReactionConfig como dict
        quant       — QuantResult / QuantSummaryOut como dict
        peaks       — lista de PeakRow como list[dict]

    Args:
        data:     Dict com chaves file_name, config, quant, peaks.
                  Opcionalmente pode conter notes (str).
        runs_dir: Path do diretório de persistência (criado se ausente).

    Returns:
        run_id (string UUID) do run salvo.

    Raises:
        OSError: se não for possível escrever no diretório.
    """
    runs_dir.mkdir(parents=True, exist_ok=True)

    run_id = str(uuid.uuid4())
    created_at = datetime.now(timezone.utc).isoformat()

    payload = {
        "run_id":     run_id,
        "created_at": created_at,
        "file_name":  str(data.get("file_name", "")),
        "notes":      str(data.get("notes", "")),
        "config":     data.get("config", {}),
        "quant":      data.get("quant", {}),
        "peaks":      data.get("peaks", []),
    }

    output_path = runs_dir / f"{run_id}.json"
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2, ensure_ascii=False, default=_json_serializer)

    return run_id


def load_all_runs(runs_dir: Path) -> list[dict]:
    """
    Carrega todos os arquivos JSON do diretório de runs.

    Silencia arquivos corrompidos (JSON inválido) — apenas loga o nome.
    Retorna lista vazia se o diretório não existir.

    Returns:
        Lista de dicts, um por run, ordenada por created_at descendente
        (mais recente primeiro).
    """
    if not runs_dir.exists():
        return []

    runs: list[dict] = []

    for json_file in sorted(runs_dir.glob("*.json")):
        try:
            with open(json_file, "r", encoding="utf-8") as f:
                data = json.load(f)
            runs.append(data)
        except (json.JSONDecodeError, OSError, KeyError):
            # Arquivo corrompido — ignora silenciosamente
            continue

    # Ordena por created_at desc (mais recente primeiro)
    runs.sort(
        key=lambda r: r.get("created_at", ""),
        reverse=True,
    )

    return runs


def runs_to_dataframe(runs: list[dict]) -> pd.DataFrame:
    """
    Converte lista de runs em DataFrame para visualização na view History.

    Colunas geradas:
        run_id, sample_name, file_name, created_at,
        conversion_pct, yield_pct, mass_balance_pct,
        missing_carbon_pct, status_quality, notes

    Args:
        runs: Lista de dicts (saída de load_all_runs).

    Returns:
        DataFrame com uma linha por run.
        DataFrame vazio (com schema) se runs for lista vazia.
    """
    if not runs:
        return pd.DataFrame(columns=_HISTORY_FIXED_COLS + ["notes"])

    rows: list[dict] = []

    for run in runs:
        quant  = run.get("quant",  {})
        config = run.get("config", {})

        rows.append({
            "run_id":             run.get("run_id", ""),
            "sample_name":        config.get("sample_name", ""),
            "file_name":          run.get("file_name", ""),
            "created_at":         run.get("created_at", ""),
            "conversion_pct":     quant.get("conversion_pct",    0.0),
            "yield_pct":          quant.get("yield_pct",          0.0),
            "mass_balance_pct":   quant.get("mass_balance_pct",   0.0),
            "missing_carbon_pct": quant.get("missing_carbon_pct", 0.0),
            "status_quality":     quant.get("status_quality",     ""),
            "notes":              run.get("notes", ""),
        })

    return pd.DataFrame(rows)


def runs_to_csv_bytes(runs: list[dict]) -> bytes:
    """
    Gera o CSV consolidado de múltiplos runs para exportação (ICH Q2R1).

    Colunas fixas + colunas dinâmicas de seletividade:
        sel_{composto1}%
        sel_{composto2}%
        ...

    As colunas dinâmicas são determinadas pela união de todos os compostos
    presentes nos selectivities de todos os runs selecionados.

    Args:
        runs: Lista de dicts de runs (pode ser subconjunto do histórico).

    Returns:
        Conteúdo do CSV como bytes (UTF-8).
    """
    if not runs:
        return b""

    # Coleta todos os nomes de compostos com seletividade
    all_compounds: set[str] = set()
    for run in runs:
        sel = run.get("quant", {}).get("selectivities", {})
        all_compounds.update(sel.keys())

    sel_cols = sorted([f"sel_{c.replace(' ', '_')}%" for c in all_compounds])

    rows: list[dict] = []

    for run in runs:
        quant  = run.get("quant",  {})
        config = run.get("config", {})
        sel    = quant.get("selectivities", {})

        row: dict = {
            "run_id":             run.get("run_id", ""),
            "sample_name":        config.get("sample_name", ""),
            "file_name":          run.get("file_name", ""),
            "created_at":         run.get("created_at", ""),
            "conversion_pct":     quant.get("conversion_pct",    0.0),
            "yield_pct":          quant.get("yield_pct",          0.0),
            "mass_balance_pct":   quant.get("mass_balance_pct",   0.0),
            "missing_carbon_pct": quant.get("missing_carbon_pct", 0.0),
            "status_quality":     quant.get("status_quality",     ""),
        }

        # Colunas dinâmicas de seletividade
        for compound in all_compounds:
            col_name = f"sel_{compound.replace(' ', '_')}%"
            row[col_name] = sel.get(compound, 0.0)

        rows.append(row)

    df = pd.DataFrame(rows, columns=_HISTORY_FIXED_COLS + sel_cols)

    buffer = io.BytesIO()
    df.to_csv(buffer, index=False, encoding="utf-8")
    return buffer.getvalue()


def peaks_to_csv_bytes(df_peaks: pd.DataFrame) -> bytes:
    """
    Gera o CSV de picos de um run individual para exportação.

    Exporta todas as colunas do DataFrame de picos em ordem lógica.
    Colunas numéricas são arredondadas para 6 casas decimais.

    Args:
        df_peaks: DataFrame de picos (saída do quantifier).

    Returns:
        Conteúdo do CSV como bytes (UTF-8).
    """
    if df_peaks.empty:
        return b""

    # Ordem preferencial de colunas (colunas extras aparecem ao final)
    preferred_order = [
        "peak_id", "keep", "compound_name", "canonical_name", "cas",
        "role", "rt_min", "rt_left", "rt_right",
        "area", "area_pct", "area_ratio",
        "rrf", "calib_slope", "calib_intercept", "use_calibration",
        "stoichiometry", "match_score", "match_confidence", "id_method",
        "c_vial_mM", "c_flask_mM", "lod_mM", "loq_mM", "selectivity_pct",
    ]

    existing = [c for c in preferred_order if c in df_peaks.columns]
    extras   = [c for c in df_peaks.columns if c not in preferred_order]
    ordered_df = df_peaks[existing + extras].copy()

    # Arredonda colunas numéricas
    float_cols = ordered_df.select_dtypes(include=["float64", "float32"]).columns
    ordered_df[float_cols] = ordered_df[float_cols].round(6)

    buffer = io.BytesIO()
    ordered_df.to_csv(buffer, index=False, encoding="utf-8")
    return buffer.getvalue()


def delete_run(run_id: str, runs_dir: Path) -> bool:
    """
    Remove um run do disco pelo run_id.

    Args:
        run_id:   UUID do run a remover.
        runs_dir: Path do diretório de runs.

    Returns:
        True se o arquivo foi removido, False se não existia.
    """
    target = runs_dir / f"{run_id}.json"
    if target.exists():
        target.unlink()
        return True
    return False


# ── Helpers privados ──────────────────────────────────────────────────────────

def _json_serializer(obj: object) -> object:
    """
    Serializer customizado para json.dump.
    Converte tipos não-serializáveis nativamente:
      - numpy scalars → float/int Python
      - pandas NA/NaT → None
    """
    import numpy as np

    if isinstance(obj, (np.integer,)):
        return int(obj)
    if isinstance(obj, (np.floating,)):
        return float(obj)
    if isinstance(obj, np.ndarray):
        return obj.tolist()
    if pd.isna(obj):
        return None
    raise TypeError(f"Tipo não serializável: {type(obj)}")