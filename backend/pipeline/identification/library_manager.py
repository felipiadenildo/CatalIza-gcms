from pathlib import Path

import pandas as pd

from core.utils import norm_name


# Colunas obrigatórias no compound_library.csv
_REQUIRED_COLS = {"compound_name", "rt_expected"}

# Colunas opcionais com seus defaults
_OPTIONAL_DEFAULTS: dict = {
    "cas": "",
    "role": "unknown",
    "rrf": 1.0,
    "calib_slope": 0.0,
    "calib_intercept": 0.0,
    "use_calibration": False,
    "stoichiometry": 1.0,
    "mz_base_peak": 0.0,
    "qualifier_ions": "",   # string separada por vírgula: "77,105,131"
    "rt_tolerance": 0.05,   # minutos — tolerância individual por composto
}


class LibraryManager:
    """
    Gerencia a biblioteca de compostos carregada do compound_library.csv.

    O CSV deve ter pelo menos as colunas:
      compound_name  — nome do composto (string)
      rt_expected    — tempo de retenção esperado em minutos (float)

    Colunas opcionais (ver _OPTIONAL_DEFAULTS acima).

    Uso:
        lib = LibraryManager(Path("config/compound_library.csv"))
        candidates = lib.rt_candidates(3.01)
        row = lib.lookup_by_name("trans-Stilbene")
    """

    def __init__(self, csv_path: Path) -> None:
        self._path = csv_path
        self._df: pd.DataFrame = self._load(csv_path)
        self._norm_index: dict[str, int] = self._build_norm_index()

    # ── Carregamento ──────────────────────────────────────────────────────────

    def _load(self, path: Path) -> pd.DataFrame:
        """
        Carrega o CSV e valida colunas obrigatórias.
        Preenche colunas opcionais ausentes com defaults.
        Retorna DataFrame vazio (mas com schema correto) se o arquivo
        não existir ou estiver vazio.
        """
        if not path.exists() or path.stat().st_size == 0:
            return self._empty_df()

        try:
            df = pd.read_csv(path, dtype=str)
        except Exception:
            return self._empty_df()

        # Valida colunas obrigatórias
        missing = _REQUIRED_COLS - set(df.columns)
        if missing:
            raise ValueError(
                f"compound_library.csv está faltando colunas obrigatórias: {missing}"
            )

        # Preenche colunas opcionais ausentes com defaults
        for col, default in _OPTIONAL_DEFAULTS.items():
            if col not in df.columns:
                df[col] = default

        # Conversões de tipo
        df["rt_expected"]      = pd.to_numeric(df["rt_expected"],      errors="coerce").fillna(0.0)
        df["rrf"]              = pd.to_numeric(df["rrf"],              errors="coerce").fillna(1.0)
        df["calib_slope"]      = pd.to_numeric(df["calib_slope"],      errors="coerce").fillna(0.0)
        df["calib_intercept"]  = pd.to_numeric(df["calib_intercept"],  errors="coerce").fillna(0.0)
        df["stoichiometry"]    = pd.to_numeric(df["stoichiometry"],    errors="coerce").fillna(1.0)
        df["mz_base_peak"]     = pd.to_numeric(df["mz_base_peak"],     errors="coerce").fillna(0.0)
        df["rt_tolerance"]     = pd.to_numeric(df["rt_tolerance"],     errors="coerce").fillna(0.05)
        df["use_calibration"]  = df["use_calibration"].map(
            lambda v: str(v).lower() in ("true", "1", "yes")
        )

        df["compound_name"] = df["compound_name"].fillna("").astype(str)
        df["cas"]           = df["cas"].fillna("").astype(str)
        df["role"]          = df["role"].fillna("unknown").astype(str)
        df["qualifier_ions"]= df["qualifier_ions"].fillna("").astype(str)

        # Adiciona coluna de nome normalizado para lookup rápido
        df["canonical_name"] = df["compound_name"].apply(norm_name)

        df = df.reset_index(drop=True)
        return df

    def _empty_df(self) -> pd.DataFrame:
        cols = list(_REQUIRED_COLS) + list(_OPTIONAL_DEFAULTS.keys()) + ["canonical_name"]
        return pd.DataFrame(columns=cols)

    def _build_norm_index(self) -> dict[str, int]:
        """Mapa canonical_name → índice de linha para lookup O(1)."""
        return {
            row["canonical_name"]: idx
            for idx, row in self._df.iterrows()
            if row["canonical_name"]
        }

    # ── Consultas ─────────────────────────────────────────────────────────────

    def rt_candidates(self, rt_val: float) -> list[dict]:
        """
        Retorna compostos cujo |rt_expected - rt_val| <= rt_tolerance.

        Usa a tolerância individual por composto (coluna rt_tolerance),
        com fallback para 0.05 min se não definida.

        Returns:
            Lista de dicts com todas as colunas do CSV para cada candidato.
            Lista vazia se nenhum composto estiver dentro da janela.
        """
        if self._df.empty:
            return []

        mask = (self._df["rt_expected"] - rt_val).abs() <= self._df["rt_tolerance"]
        return self._df[mask].to_dict(orient="records")

    def lookup_by_name(self, raw_name: str) -> dict | None:
        """
        Busca um composto pelo nome normalizado (fuzzy via norm_name).

        Normaliza `raw_name` com norm_name() e tenta match exato no índice.
        Retorna o dict da linha correspondente ou None se não encontrado.
        """
        canonical = norm_name(raw_name)
        idx = self._norm_index.get(canonical)
        if idx is None:
            return None
        return self._df.loc[idx].to_dict()

    def get_role(self, canonical_name: str) -> str:
        """Retorna o role do composto ou 'unknown' se não encontrado."""
        row = self.lookup_by_name(canonical_name)
        return row["role"] if row else "unknown"

    def get_rrf(self, canonical_name: str) -> float:
        """Retorna o RRF do composto ou 1.0 se não encontrado."""
        row = self.lookup_by_name(canonical_name)
        return float(row["rrf"]) if row else 1.0

    def get_calib(self, canonical_name: str) -> tuple[float, float, bool]:
        """
        Retorna (calib_slope, calib_intercept, use_calibration) do composto.
        Defaults: (0.0, 0.0, False) se não encontrado.
        """
        row = self.lookup_by_name(canonical_name)
        if not row:
            return 0.0, 0.0, False
        return (
            float(row["calib_slope"]),
            float(row["calib_intercept"]),
            bool(row["use_calibration"]),
        )

    def auto_assign_roles(
        self,
        df_peaks: pd.DataFrame,
        config: dict,
    ) -> pd.DataFrame:
        """
        Heurística automática de atribuição de roles para picos identificados.

        Regras aplicadas em ordem (NÃO sobrescreve roles já definidos pelo usuário):
          1. Se canonical_name está na library → usa role da library
          2. Se canonical_name == norm_name(substrate) → role = "substrate"
          3. Se canonical_name == norm_name(main_product) → role = "product"
          4. Se c_is_vial_mM == 0 e nenhum IS definido → pico de maior área
             sem role atribuído recebe role = "IS"
          5. Demais sem role → role = "byproduct"

        Args:
            df_peaks: DataFrame com colunas canonical_name, role, area, keep.
            config:   ReactionConfig como dict com chaves substrate,
                      main_product, c_is_vial_mM.

        Returns:
            DataFrame com coluna role atualizada (in-place safe — retorna cópia).
        """
        df = df_peaks.copy()

        substrate_norm   = norm_name(config.get("substrate", ""))
        main_product_norm = norm_name(config.get("main_product", ""))
        c_is_vial        = float(config.get("c_is_vial_mM", 0.0))

        for idx, row in df.iterrows():
            # Não sobrescreve roles já definidos pelo usuário
            current_role = str(row.get("role", "unknown")).strip().lower()
            if current_role not in ("unknown", "unassigned", ""):
                continue

            canonical = str(row.get("canonical_name", "")).strip()

            # Regra 1: library
            lib_row = self.lookup_by_name(canonical)
            if lib_row and lib_row["role"] not in ("unknown", ""):
                df.at[idx, "role"] = lib_row["role"]
                continue

            # Regra 2: substrate
            if canonical and canonical == substrate_norm:
                df.at[idx, "role"] = "substrate"
                continue

            # Regra 3: main_product
            if canonical and canonical == main_product_norm:
                df.at[idx, "role"] = "product"
                continue

        # Regra 4: IS automático se c_is_vial == 0 e nenhum IS definido
        has_is = (df["role"] == "IS").any()
        if not has_is and c_is_vial == 0.0:
            active = df[df.get("keep", pd.Series([True] * len(df), index=df.index))]
            no_role_mask = df["role"].isin(["unknown", "unassigned", ""])
            if no_role_mask.any():
                candidates = df[no_role_mask]
                if not candidates.empty and "area" in candidates.columns:
                    largest_idx = candidates["area"].idxmax()
                    df.at[largest_idx, "role"] = "IS"

        # Regra 5: byproduct para os restantes sem role
        still_unknown = df["role"].isin(["unknown", "unassigned", ""])
        df.loc[still_unknown, "role"] = "byproduct"

        return df