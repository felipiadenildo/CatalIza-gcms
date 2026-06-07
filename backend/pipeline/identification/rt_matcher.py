import numpy as np

from pipeline.identification.library_manager import LibraryManager


def match(
    rt_val: float,
    mz_arr: np.ndarray,
    int_arr: np.ndarray,
    library: LibraryManager,
) -> tuple[str | None, float, str]:
    """
    Tenta identificar um composto pelo tempo de retenção e íons diagnóstico.

    Estratégia em três níveis (score decrescente):
      1.0 — RT dentro da tolerância + base peak m/z + todos os qualifier ions
      0.7 — RT dentro da tolerância + base peak m/z (sem qualifiers)
      0.4 — Apenas RT dentro da tolerância (sem validação espectral)

    Args:
        rt_val:  Tempo de retenção do ápice do pico em minutos.
        mz_arr:  Array float32 de m/z do scan mais próximo ao ápice.
        int_arr: Array float32 de intensidades correspondentes.
        library: Instância de LibraryManager já carregada.

    Returns:
        Tupla (compound_name, score, confidence) onde:
          compound_name — nome do composto ou None se sem match.
          score         — float em [0.0, 1.0].
          confidence    — "HIGH" | "MEDIUM" | "LOW" | "NONE".

        Se múltiplos candidatos existirem na janela de RT,
        retorna o de maior score. Em empate, o de menor |Δrt|.
    """
    candidates = library.rt_candidates(rt_val)

    if not candidates:
        return None, 0.0, "NONE"

    # Pré-computa o base peak m/z do scan (m/z com maior intensidade)
    observed_base_mz: float | None = None
    observed_mz_set: set[int] = set()

    if len(mz_arr) > 0 and len(int_arr) > 0:
        base_idx = int(np.argmax(int_arr))
        observed_base_mz = float(mz_arr[base_idx])
        # Arredonda m/z para inteiros para comparação com qualifier ions
        observed_mz_set = {int(round(float(m))) for m in mz_arr}

    best_name: str | None = None
    best_score: float = 0.0
    best_delta_rt: float = float("inf")

    for candidate in candidates:
        name        = str(candidate.get("compound_name", ""))
        rt_expected = float(candidate.get("rt_expected", 0.0))
        base_mz_lib = float(candidate.get("mz_base_peak", 0.0))
        qual_str    = str(candidate.get("qualifier_ions", "")).strip()

        delta_rt = abs(rt_val - rt_expected)
        score    = 0.4  # nível mínimo: só RT

        # Valida base peak
        base_match = False
        if observed_base_mz is not None and base_mz_lib > 0.0:
            base_match = abs(observed_base_mz - base_mz_lib) <= 0.5

        if base_match:
            score = 0.7

            # Valida qualifier ions
            if qual_str:
                qualifier_ions = _parse_qualifier_ions(qual_str)
                if qualifier_ions:
                    matched_quals = sum(
                        1 for q in qualifier_ions if q in observed_mz_set
                    )
                    if matched_quals == len(qualifier_ions):
                        score = 1.0

        # Prefere score maior; em empate, menor delta_rt
        if score > best_score or (score == best_score and delta_rt < best_delta_rt):
            best_score    = score
            best_name     = name
            best_delta_rt = delta_rt

    if best_score == 0.0 or best_name is None:
        return None, 0.0, "NONE"

    confidence = _score_to_confidence(best_score)
    return best_name, best_score, confidence


def _parse_qualifier_ions(qual_str: str) -> list[int]:
    """
    Converte a string de qualifier ions em lista de inteiros.

    Formato esperado no CSV: "77,105,131" ou "77, 105, 131"
    Ignora valores não-numéricos silenciosamente.
    """
    ions: list[int] = []
    for token in qual_str.split(","):
        token = token.strip()
        try:
            ions.append(int(round(float(token))))
        except ValueError:
            continue
    return ions


def _score_to_confidence(score: float) -> str:
    """
    Converte score numérico para nível de confiança textual.

      1.0        → "HIGH"   (RT + base peak + qualifiers)
      0.7        → "MEDIUM" (RT + base peak)
      0.4        → "LOW"    (só RT)
      < 0.4      → "NONE"
    """
    if score >= 1.0:
        return "HIGH"
    if score >= 0.7:
        return "MEDIUM"
    if score >= 0.4:
        return "LOW"
    return "NONE"