import base64
import bisect
import struct
import zlib
from typing import Any

import numpy as np

from core.types import RawData, ScanDict


# ─── Namespaces conhecidos do formato mzXML ───────────────────────────────────
_MZXML_NAMESPACES = [
    "http://sashimi.sourceforge.net/schema_revision/mzXML_3.2",
    "http://sashimi.sourceforge.net/schema_revision/mzXML_3.1",
    "http://sashimi.sourceforge.net/schema_revision/mzXML_3.0",
    "http://sashimi.sourceforge.net/schema_revision/mzXML_2.1",
    "",  # sem namespace (fallback)
]


def _detect_namespace(root: Any) -> str:
    """
    Detecta o namespace XML do elemento raiz do mzXML.
    Retorna a string do namespace (com chaves) ou string vazia.
    """
    tag: str = root.tag
    if tag.startswith("{"):
        return tag.split("}")[0] + "}"
    return ""


def _decode_peaks(scan_el: Any, ns: str) -> tuple[np.ndarray, np.ndarray]:
    """
    Decodifica o elemento <peaks> de um scan mzXML.

    O formato padrão é:
      - Base64 encoded
      - Compressão zlib (opcional — detectada automaticamente)
      - Precision 32 ou 64 bits (network byte order — big-endian)
      - Intercalado: [mz0, int0, mz1, int1, ...]

    Retorna (mz_array, intensity_array) como float32.
    """
    peaks_el = scan_el.find(f"{ns}peaks")

    if peaks_el is None or not peaks_el.text:
        return np.array([], dtype=np.float32), np.array([], dtype=np.float32)

    precision = int(peaks_el.get("precision", "32"))
    compression = peaks_el.get("compressionType", "none").lower()
    byte_order_attr = peaks_el.get("byteOrder", "network")

    raw_bytes = base64.b64decode(peaks_el.text.strip())

    if compression in ("zlib", "zlib compression"):
        raw_bytes = zlib.decompress(raw_bytes)

    # Byte order: "network" = big-endian no padrão mzXML
    endian = ">" if byte_order_attr in ("network", "big") else "<"

    if precision == 64:
        fmt_char = "d"
        item_size = 8
    else:
        fmt_char = "f"
        item_size = 4

    n_values = len(raw_bytes) // item_size
    if n_values == 0:
        return np.array([], dtype=np.float32), np.array([], dtype=np.float32)

    fmt = f"{endian}{n_values}{fmt_char}"
    values = np.array(struct.unpack(fmt, raw_bytes), dtype=np.float64)

    # Intercalado: índices pares = m/z, ímpares = intensidade
    mz = values[0::2].astype(np.float32)
    intensity = values[1::2].astype(np.float32)

    return mz, intensity


def parse_mzxml(file_bytes: bytes) -> RawData:
    """
    Faz o parse completo de um arquivo .mzXML em memória.

    Suporta:
    - Detecção automática de namespace
    - Compressão zlib e sem compressão
    - Precision 32 e 64 bits
    - Scans MS1 e MS2 (filtra apenas MS1 para o TIC)

    Retorna RawData com:
      rt    — array de tempos de retenção em minutos (float64)
      tic   — array de TIC total por scan (float64)
      scans — lista de ScanDict com rt, mz[], intensity[]

    Lança ValueError se o arquivo não for um mzXML válido.
    """
    try:
        import xml.etree.ElementTree as ET
        root = ET.fromstring(file_bytes)
    except ET.ParseError as exc:
        raise ValueError(f"Arquivo mzXML inválido ou corrompido: {exc}") from exc

    ns = _detect_namespace(root)

    rt_list: list[float] = []
    tic_list: list[float] = []
    scans: list[ScanDict] = []

    # Itera sobre todos os elementos <scan> — pode ser aninhado (MS2 dentro de MS1)
    for scan_el in root.iter(f"{ns}scan"):
        ms_level = int(scan_el.get("msLevel", "1"))
        if ms_level != 1:
            continue  # ignora MS2/MS3 para o TIC

        # Tempo de retenção: atributo retentionTime em formato PT{N}S (ISO 8601)
        rt_raw = scan_el.get("retentionTime", "PT0S")
        rt_min = _parse_retention_time(rt_raw)

        # TIC do atributo totIonCurrent (mais rápido que somar intensity[])
        tic_val = float(scan_el.get("totIonCurrent", "0") or "0")

        mz_arr, int_arr = _decode_peaks(scan_el, ns)

        # Se totIonCurrent não estiver no atributo, calcula pela soma
        if tic_val == 0.0 and len(int_arr) > 0:
            tic_val = float(np.sum(int_arr))

        rt_list.append(rt_min)
        tic_list.append(tic_val)
        scans.append(ScanDict(rt=rt_min, mz=mz_arr, intensity=int_arr))

    if not rt_list:
        raise ValueError(
            "Nenhum scan MS1 encontrado no arquivo mzXML. "
            "Verifique se o arquivo contém dados de cromatograma."
        )

    rt_array = np.array(rt_list, dtype=np.float64)
    tic_array = np.array(tic_list, dtype=np.float64)

    return RawData(rt=rt_array, tic=tic_array, scans=scans)


def _parse_retention_time(rt_str: str) -> float:
    """
    Converte o atributo retentionTime do mzXML para minutos.

    Formatos suportados:
      - "PT180.5S"  → ISO 8601 duration em segundos → 3.008 min
      - "PT3.5M"    → minutos direto               → 3.5 min
      - "180.5"     → segundos como float           → 3.008 min
      - "3.5"       → assume segundos               → 0.058 min
    """
    rt_str = rt_str.strip()

    if rt_str.startswith("PT"):
        inner = rt_str[2:]
        if inner.endswith("S"):
            return float(inner[:-1]) / 60.0
        elif inner.endswith("M"):
            return float(inner[:-1])
        else:
            # fallback: tenta converter o número diretamente
            try:
                return float(inner) / 60.0
            except ValueError:
                return 0.0

    try:
        return float(rt_str) / 60.0
    except ValueError:
        return 0.0


def find_scan_at_rt(scans: list[ScanDict], rt_min: float) -> int:
    """
    Retorna o índice do scan mais próximo ao tempo de retenção `rt_min`.
    Usa busca binária sobre a lista ordenada de RTs.

    Complexidade: O(log N)
    """
    if not scans:
        return 0

    rt_values = [s["rt"] for s in scans]
    idx = bisect.bisect_left(rt_values, rt_min)

    if idx == 0:
        return 0
    if idx >= len(rt_values):
        return len(rt_values) - 1

    # Retorna o vizinho mais próximo
    before = rt_values[idx - 1]
    after = rt_values[idx]
    if abs(after - rt_min) < abs(before - rt_min):
        return idx
    return idx - 1