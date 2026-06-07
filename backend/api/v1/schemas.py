from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field


# ─────────────────────────────────────────────────────────────────────────────
# MODELOS DE ENTRADA
# ─────────────────────────────────────────────────────────────────────────────


class ProcessingSettings(BaseModel):
    baseline_window_pct: float = Field(default=5.0,  ge=0.1,  le=50.0)
    savgol_window:       int   = Field(default=7,    ge=3,    le=101)
    savgol_poly:         int   = Field(default=2,    ge=1,    le=5)
    min_prominence_pct:  float = Field(default=5.0,  ge=0.0,  le=100.0)
    min_width_scans:     int   = Field(default=3,    ge=1)
    min_area_pct:        float = Field(default=3.0,  ge=0.0,  le=100.0)
    min_height_abs:      float = Field(default=0.0,  ge=0.0)
    min_distance_scans:  int   = Field(default=1,    ge=1)
    integration_method:  Literal["simpson", "trapezoid"]                    = "simpson"
    boundary_method:     Literal["half_width", "valley", "tangent_skim"]    = "half_width"


class ReactionConfig(BaseModel):
    sample_name:          str                  = ""
    substrate:            str                  = ""
    main_product:         str                  = ""
    c_initial_mM:         float                = Field(default=0.0, ge=0.0)
    c_max_product_mM:     float                = Field(default=0.0, ge=0.0)
    c_is_vial_mM:         float                = Field(default=0.0, ge=0.0)
    dilution_factor:      float                = Field(default=1.0, ge=0.0)
    stoichiometry:        dict[str, float]     = Field(default_factory=lambda: {"default": 1.0})
    substrate_aliases:    list[str]            = Field(default_factory=list)
    mass_balance_limits:  dict[str, float]     = Field(default_factory=lambda: {"low": 50.0, "high": 110.0})
    calibration_override: dict[str, dict]      = Field(default_factory=dict)


class PeakRow(BaseModel):
    peak_id:          int
    keep:             bool   = True
    rt_min:           float
    rt_left:          float
    rt_right:         float
    area:             float
    area_pct:         float
    compound_name:    str    = ""
    canonical_name:   str    = ""
    cas:              str    = ""
    role:             str    = "unknown"
    rrf:              float  = Field(default=1.0, ge=0.0)
    calib_slope:      float  = 0.0
    calib_intercept:  float  = 0.0
    use_calibration:  bool   = False
    stoichiometry:    float  = Field(default=1.0, ge=0.0)
    match_score:      float  = Field(default=0.0, ge=0.0, le=1.0)
    match_confidence: str    = "NONE"
    id_method:        str    = "unassigned"
    spectrum_idx:     int    = -1
    # Campos calculados — preenchidos pelo quantifier
    area_ratio:       float  = 0.0
    c_vial_mM:        float  = 0.0
    c_flask_mM:       float  = 0.0
    lod_mM:           float  = 0.0
    loq_mM:           float  = 0.0
    selectivity_pct:  float  = 0.0


class RecomputeRequest(BaseModel):
    peaks:          list[PeakRow]
    config:         ReactionConfig
    sigma_baseline: float = Field(default=0.0, ge=0.0)


class RunSaveRequest(BaseModel):
    peaks:     list[PeakRow]
    quant:     "QuantSummaryOut"
    config:    ReactionConfig
    file_name: str
    notes:     str = ""


# ─────────────────────────────────────────────────────────────────────────────
# MODELOS DE SAÍDA
# ─────────────────────────────────────────────────────────────────────────────


class PeakMeta(BaseModel):
    peak_id:   int
    label:     str
    apex_idx:  int
    left_idx:  int
    right_idx: int
    rt_apex:   float
    rt_left:   float
    rt_right:  float
    area:      float


class TICData(BaseModel):
    rt:           list[float]
    tic_raw:      list[float]
    tic_smooth:   list[float]
    tic_baseline: list[float]
    peaks:        list[PeakMeta]


class QuantSummaryOut(BaseModel):
    conversion_pct:     float
    yield_pct:          float
    mass_balance_pct:   float
    missing_carbon_pct: float
    consumed_mM:        float
    is_area:            float
    selectivities:      dict[str, float]    = Field(default_factory=dict)
    area_percent:       dict[str, float]    = Field(default_factory=dict)
    warnings:           list[str]           = Field(default_factory=list)
    status_quality:     str
    c_initial_used:     float
    c_max_used:         float


class AnalyzeResponse(BaseModel):
    job_id:           str | None            = None
    status:           Literal["done", "processing", "error"]
    tic:              TICData | None        = None
    peaks:            list[PeakRow] | None  = None
    quant:            QuantSummaryOut | None = None
    sigma_baseline:   float                 = 0.0
    suggested_config: ReactionConfig | None = None


class RecomputeResponse(BaseModel):
    peaks: list[PeakRow]
    quant: QuantSummaryOut


class JobStatusResponse(BaseModel):
    status: Literal["processing", "done", "error"]
    result: AnalyzeResponse | None = None
    error:  str | None             = None


class MethodsListResponse(BaseModel):
    presets: dict[str, ReactionConfig] = Field(default_factory=dict)


class RunSummary(BaseModel):
    run_id:             str
    sample_name:        str
    file_name:          str
    created_at:         str
    conversion_pct:     float
    yield_pct:          float
    mass_balance_pct:   float
    missing_carbon_pct: float
    status_quality:     str
    notes:              str = ""


class HistoryListResponse(BaseModel):
    runs: list[RunSummary] = Field(default_factory=list)


class SaveRunResponse(BaseModel):
    run_id: str


class AppSettings(BaseModel):
    signal:         dict    = Field(default_factory=dict)
    identification: dict    = Field(default_factory=dict)
    quantification: dict    = Field(default_factory=dict)
    jobs:           dict    = Field(default_factory=dict)
    ui:             dict    = Field(default_factory=dict)


# Resolve forward reference de RunSaveRequest → QuantSummaryOut
RunSaveRequest.model_rebuild()