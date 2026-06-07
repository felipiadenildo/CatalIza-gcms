import json
from pathlib import Path
from typing import Any


DEFAULT_SETTINGS: dict[str, Any] = {
    # ── Processamento de Sinal ────────────────────────────────────────────────
    "signal": {
        "baseline_window_pct": 5.0,      # % do total de scans para janela do mínimo deslizante
        "savgol_window": 7,               # pontos — deve ser ímpar
        "savgol_poly": 2,                 # grau do polinômio Savitzky-Golay
        "min_prominence_pct": 5.0,        # % da altura máxima do TIC
        "min_width_scans": 3,             # scans mínimos de largura a meia-altura
        "min_area_pct": 3.0,              # % da área total para aceitar pico
        "min_height_abs": 0.0,            # altura absoluta mínima (0 = desativado)
        "min_distance_scans": 1,          # distância mínima entre ápices (scans)
        "integration_method": "simpson",  # "simpson" | "trapezoid"
        "boundary_method": "half_width",  # "half_width" | "valley" | "tangent_skim"
    },
    # ── Identificação Espectral ───────────────────────────────────────────────
    "identification": {
        "rt_tolerance_min": 0.05,         # minutos — janela de RT matching
        "wdp_threshold_high": 0.85,       # score WDP para confiança HIGH
        "wdp_threshold_medium": 0.60,     # score WDP para confiança MEDIUM
        "wdp_threshold_low": 0.40,        # score WDP para confiança LOW
        "spectral_topk": 200,             # candidatos após pré-filtro Jaccard
        "use_rt_first": True,             # tenta RT matching antes do WDP
    },
    # ── Quantificação ─────────────────────────────────────────────────────────
    "quantification": {
        "lod_factor": 3.3,                # ICH Q2R1: LOD = 3.3 × σ / slope
        "loq_factor": 10.0,               # ICH Q2R1: LOQ = 10 × σ / slope
        "mass_balance_low": 50.0,         # % — abaixo disso: WARNING
        "mass_balance_high": 110.0,       # % — acima disso: WARNING
    },
    # ── Jobs assíncronos ──────────────────────────────────────────────────────
    "jobs": {
        "timeout_seconds": 300,
        "large_file_threshold_mb": 10,
        "job_ttl_minutes": 30,            # tempo em memória após conclusão
        "poll_interval_ms": 1500,         # frontend: intervalo de polling
    },
    # ── UI ────────────────────────────────────────────────────────────────────
    "ui": {
        "theme": "dark",
        "sidebar_collapsed": False,
        "default_chart_height": 420,
    },
}


def load(path: Path) -> dict[str, Any]:
    """
    Carrega settings de um arquivo JSON.
    Retorna dict vazio se o arquivo não existir ou estiver corrompido.
    """
    if not path.exists():
        return {}
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except (json.JSONDecodeError, OSError):
        return {}


def save(settings: dict[str, Any], path: Path) -> None:
    """
    Serializa `settings` para JSON em `path`.
    Cria os diretórios pai se necessário.
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(settings, f, indent=2, ensure_ascii=False)


def merge_defaults(loaded: dict[str, Any]) -> dict[str, Any]:
    """
    Merge profundo de `loaded` sobre DEFAULT_SETTINGS.
    Garante que chaves ausentes em `loaded` sejam preenchidas
    com os valores padrão — sem sobrescrever o que o usuário configurou.

    Regra: loaded tem prioridade sobre defaults em todos os níveis.
    """
    def _deep_merge(base: dict, override: dict) -> dict:
        result = base.copy()
        for key, value in override.items():
            if (
                key in result
                and isinstance(result[key], dict)
                and isinstance(value, dict)
            ):
                result[key] = _deep_merge(result[key], value)
            else:
                result[key] = value
        return result

    return _deep_merge(DEFAULT_SETTINGS, loaded)