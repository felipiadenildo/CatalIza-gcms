import re


def norm_name(s: str) -> str:
    """
    Normaliza nomes de compostos para matching interno.
    Remove prefixos estereoquímicos, converte para lowercase,
    substitui caracteres não-alfanuméricos por underscore.

    Exemplos:
        "trans-Stilbene"  → "stilbene"
        "(E)-2-hexenal"   → "2_hexenal"
        "cis-4-methylcyclohexanol" → "4_methylcyclohexanol"
    """
    if not isinstance(s, str):
        return ""

    # Remove prefixos estereoquímicos comuns
    prefixes = r"^(?:trans|cis|e|z|r|s|d|l|dl|rac|meso|n|sec|tert|iso|neo)-"
    cleaned = re.sub(prefixes, "", s.strip().lower())

    # Remove parênteses com estereodescritores: (E)-, (Z)-, (R)-, (S)-, (±)-
    cleaned = re.sub(r"^\([a-zα-ω±\+\-,]+\)-", "", cleaned)

    # Substitui qualquer caractere não-alfanumérico (exceto dígitos e letras) por underscore
    cleaned = re.sub(r"[^a-z0-9]+", "_", cleaned)

    # Remove underscores nas extremidades
    cleaned = cleaned.strip("_")

    return cleaned


def safe_div(a: float, b: float, fallback: float = 0.0) -> float:
    """
    Divisão segura: retorna `fallback` se b == 0 ou b é NaN.

    Exemplos:
        safe_div(10.0, 2.0)       → 5.0
        safe_div(10.0, 0.0)       → 0.0
        safe_div(10.0, 0.0, -1.0) → -1.0
    """
    if b == 0 or b != b:  # b != b detecta NaN sem importar math
        return fallback
    return a / b


def round_sig(x: float, sig: int = 4) -> float:
    """
    Arredonda `x` para `sig` algarismos significativos.

    Exemplos:
        round_sig(0.001234567) → 0.001235
        round_sig(12345.678)   → 12350.0
        round_sig(0.0)         → 0.0
    """
    if x == 0 or x != x:  # cobre zero e NaN
        return 0.0
    import math
    magnitude = math.floor(math.log10(abs(x)))
    factor = 10 ** (sig - 1 - magnitude)
    return round(x * factor) / factor