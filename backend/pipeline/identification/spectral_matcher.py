from pathlib import Path

import numpy as np


# Número de bins do fingerprint Jaccard (cobre m/z 0–1199)
N_BINS = 1200

# Thresholds de confiança para score WDP
_WDP_HIGH   = 0.85
_WDP_MEDIUM = 0.60
_WDP_LOW    = 0.40

# Número máximo de candidatos após pré-filtro Jaccard
_TOPK = 200


class SpectralMatcher:
    """
    Identificação de compostos por spectral matching (WDP score).

    Referência:
        Stein & Scott, J. Am. Soc. Mass Spectrom. 5:859–866, 1994.
        WDP = [Σ(wQ × wR)]² / [ΣwQ² × ΣwR²]
        onde w(m/z, I) = mz^0.5 × I^0.5

    O matcher usa um pré-filtro por similaridade de Jaccard sobre
    fingerprints binários de N_BINS para reduzir o espaço de busca
    antes de calcular o WDP completo.

    Carregamento:
        O arquivo .msp é indexado na inicialização. Se o arquivo não
        existir, o matcher opera em modo degradado (retorna NONE).

    Uso:
        matcher = SpectralMatcher(Path("spectral_libraries/nist.msp"), settings)
        name, score, confidence = matcher.match(mz_list, int_list)
    """

    def __init__(self, msp_path: Path, settings: dict | None = None) -> None:
        self._path = msp_path
        self._settings = settings or {}
        self._library: list[dict] = []
        self._fingerprints: np.ndarray = np.array([], dtype=np.uint8)
        self._ready = False

        cfg = self._settings.get("identification", self._settings)
        self._wdp_high   = float(cfg.get("wdp_threshold_high",   _WDP_HIGH))
        self._wdp_medium = float(cfg.get("wdp_threshold_medium", _WDP_MEDIUM))
        self._wdp_low    = float(cfg.get("wdp_threshold_low",    _WDP_LOW))
        self._topk       = int(cfg.get("spectral_topk",          _TOPK))

        if msp_path.exists() and msp_path.stat().st_size > 0:
            self._load_msp(msp_path)

    # ── Carregamento e indexação ──────────────────────────────────────────────

    def _load_msp(self, path: Path) -> None:
        """
        Faz o parse do arquivo .msp e indexa os fingerprints Jaccard.

        Formato .msp esperado (padrão NIST):
            Name: trans-Stilbene
            MW: 180
            Num Peaks: 5
            77 999; 103 241; 115 108; 178 51; 180 715
            (linha em branco separa entradas)
        """
        entries: list[dict] = []

        try:
            text = path.read_text(encoding="utf-8", errors="replace")
        except OSError:
            return

        blocks = text.strip().split("\n\n")

        for block in blocks:
            entry = self._parse_msp_block(block)
            if entry is not None:
                entries.append(entry)

        if not entries:
            return

        self._library = entries

        # Constrói matriz de fingerprints (N_entries × N_BINS) — uint8 binário
        fp_matrix = np.zeros((len(entries), N_BINS), dtype=np.uint8)
        for i, entry in enumerate(entries):
            for mz_int in entry["mz_ints"]:
                if 0 <= mz_int < N_BINS:
                    fp_matrix[i, mz_int] = 1

        self._fingerprints = fp_matrix
        self._ready = True

    def _parse_msp_block(self, block: str) -> dict | None:
        """
        Faz o parse de um bloco .msp em um dicionário com:
          name     — string
          mw       — int
          mz_arr   — np.ndarray float32
          int_arr  — np.ndarray float32 (normalizadas 0-999)
          mz_ints  — list[int] (para fingerprint Jaccard)
          weights  — np.ndarray float64 (w = mz^0.5 × I^0.5, pré-computado)
        """
        lines = [l.strip() for l in block.strip().splitlines() if l.strip()]
        if not lines:
            return None

        meta: dict = {"name": "", "mw": 0}
        peaks_lines: list[str] = []
        in_peaks = False
        num_peaks = 0

        for line in lines:
            lower = line.lower()
            if lower.startswith("name:"):
                meta["name"] = line.split(":", 1)[1].strip()
            elif lower.startswith("mw:"):
                try:
                    meta["mw"] = int(line.split(":", 1)[1].strip())
                except ValueError:
                    pass
            elif lower.startswith("num peaks:") or lower.startswith("numpeaks:"):
                try:
                    num_peaks = int(line.split(":", 1)[1].strip())
                    in_peaks = True
                except ValueError:
                    pass
            elif in_peaks:
                peaks_lines.append(line)

        if not meta["name"] or not peaks_lines:
            return None

        mz_list: list[float] = []
        int_list: list[float] = []

        for pline in peaks_lines:
            # Suporta separadores: espaço, tab, ponto-e-vírgula
            tokens = pline.replace(";", " ").replace("\t", " ").split()
            i = 0
            while i + 1 < len(tokens):
                try:
                    mz_val  = float(tokens[i])
                    int_val = float(tokens[i + 1])
                    mz_list.append(mz_val)
                    int_list.append(int_val)
                    i += 2
                except ValueError:
                    i += 1

        if not mz_list:
            return None

        mz_arr  = np.array(mz_list,  dtype=np.float32)
        int_arr = np.array(int_list, dtype=np.float32)

        # Normaliza intensidades para 0-999
        max_int = float(np.max(int_arr))
        if max_int > 0:
            int_arr = (int_arr / max_int * 999.0).astype(np.float32)

        mz_ints = [int(round(m)) for m in mz_arr]

        # Pré-computa pesos WDP: w = mz^0.5 × I^0.5
        weights = (mz_arr.astype(np.float64) ** 0.5) * (int_arr.astype(np.float64) ** 0.5)

        return {
            "name":     meta["name"],
            "mw":       meta["mw"],
            "mz_arr":   mz_arr,
            "int_arr":  int_arr,
            "mz_ints":  mz_ints,
            "weights":  weights,
        }

    # ── Interface pública ─────────────────────────────────────────────────────

    def match(
        self,
        mz_list: list[float] | np.ndarray,
        int_list: list[float] | np.ndarray,
    ) -> tuple[str | None, float, str]:
        """
        Identifica o composto mais provável pelo score WDP.

        Etapas:
          1. Constrói fingerprint Jaccard da query.
          2. Pré-filtro: seleciona top-K candidatos por similaridade Jaccard.
          3. Calcula WDP completo para cada candidato.
          4. Retorna o melhor match com score e confiança.

        Args:
            mz_list:  Lista ou array de m/z do espectro query.
            int_list: Lista ou array de intensidades correspondentes.

        Returns:
            Tupla (name, score, confidence):
              name       — nome do composto ou None.
              score      — WDP score em [0.0, 1.0].
              confidence — "HIGH" | "MEDIUM" | "LOW" | "NONE".
        """
        if not self._ready or len(self._library) == 0:
            return None, 0.0, "NONE"

        mz_arr  = np.asarray(mz_list,  dtype=np.float32)
        int_arr = np.asarray(int_list, dtype=np.float32)

        if len(mz_arr) == 0:
            return None, 0.0, "NONE"

        # Normaliza query
        max_int = float(np.max(int_arr))
        if max_int > 0:
            int_arr = (int_arr / max_int * 999.0).astype(np.float32)

        # Fingerprint da query
        query_fp = np.zeros(N_BINS, dtype=np.uint8)
        for mz_val in mz_arr:
            idx = int(round(float(mz_val)))
            if 0 <= idx < N_BINS:
                query_fp[idx] = 1

        # ── Pré-filtro Jaccard ────────────────────────────────────────────────
        # Jaccard = |A ∩ B| / |A ∪ B|  (operações vetorizadas sobre a matriz)
        query_sum = float(np.sum(query_fp))
        if query_sum == 0:
            return None, 0.0, "NONE"

        intersections = self._fingerprints.dot(query_fp).astype(np.float32)
        lib_sums      = np.sum(self._fingerprints, axis=1).astype(np.float32)
        unions        = lib_sums + query_sum - intersections
        jaccard_scores = np.where(unions > 0, intersections / unions, 0.0)

        topk = min(self._topk, len(self._library))
        topk_indices = np.argpartition(jaccard_scores, -topk)[-topk:]

        # ── WDP score completo ────────────────────────────────────────────────
        query_weights = (
            mz_arr.astype(np.float64) ** 0.5
        ) * (
            int_arr.astype(np.float64) ** 0.5
        )
        sum_wq2 = float(np.sum(query_weights ** 2))
        if sum_wq2 == 0:
            return None, 0.0, "NONE"

        best_name:  str | None = None
        best_score: float      = 0.0

        for lib_idx in topk_indices:
            entry = self._library[lib_idx]
            wdp   = self._wdp_score(
                mz_arr, query_weights, sum_wq2,
                entry["mz_arr"], entry["weights"],
            )
            if wdp > best_score:
                best_score = wdp
                best_name  = entry["name"]

        if best_score < self._wdp_low or best_name is None:
            return None, 0.0, "NONE"

        confidence = self._wdp_to_confidence(best_score)
        return best_name, round(best_score, 4), confidence

    # ── Cálculo WDP ───────────────────────────────────────────────────────────

    def _wdp_score(
        self,
        mz_q:      np.ndarray,
        w_q:       np.ndarray,
        sum_wq2:   float,
        mz_r:      np.ndarray,
        w_r:       np.ndarray,
    ) -> float:
        """
        Calcula o WDP score entre query (Q) e referência (R).

            WDP = [Σ(wQ × wR)]² / [ΣwQ² × ΣwR²]

        Apenas pares de m/z com Δm/z <= 0.5 Da são considerados matches.
        """
        sum_wr2 = float(np.sum(w_r ** 2))
        if sum_wr2 == 0:
            return 0.0

        # Para cada m/z da query, busca o m/z mais próximo na referência
        # com tolerância de 0.5 Da (unit resolution)
        cross_sum = 0.0

        mz_r_int = np.round(mz_r).astype(np.int32)
        mz_q_int = np.round(mz_q).astype(np.int32)

        # Mapeia referência para dict {mz_int: weight} para lookup O(1)
        ref_map: dict[int, float] = {}
        for i, mz_int in enumerate(mz_r_int):
            key = int(mz_int)
            if key not in ref_map or w_r[i] > ref_map[key]:
                ref_map[key] = float(w_r[i])

        for i, mz_int in enumerate(mz_q_int):
            key = int(mz_int)
            if key in ref_map:
                cross_sum += float(w_q[i]) * ref_map[key]

        if cross_sum == 0:
            return 0.0

        wdp = (cross_sum ** 2) / (sum_wq2 * sum_wr2)
        return float(min(wdp, 1.0))

    def _wdp_to_confidence(self, score: float) -> str:
        """Converte WDP score para nível de confiança."""
        if score >= self._wdp_high:
            return "HIGH"
        if score >= self._wdp_medium:
            return "MEDIUM"
        if score >= self._wdp_low:
            return "LOW"
        return "NONE"

    # ── Utilitários ───────────────────────────────────────────────────────────

    @property
    def is_ready(self) -> bool:
        """True se a biblioteca foi carregada com sucesso."""
        return self._ready

    @property
    def library_size(self) -> int:
        """Número de entradas na biblioteca espectral."""
        return len(self._library)