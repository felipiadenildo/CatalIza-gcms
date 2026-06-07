// Espelha exatamente os schemas Pydantic do backend

export interface ProcessingSettings {
  baseline_window_pct: number;
  savgol_window: number;
  savgol_poly: number;
  min_prominence_pct: number;
  min_width_scans: number;
  min_area_pct: number;
  min_height_abs: number;
  min_distance_scans: number;
  integration_method: "simpson" | "trapezoid";
  boundary_method: "half_width" | "valley" | "tangent_skim";
}

export interface ReactionConfig {
  sample_name: string;
  substrate: string;
  main_product: string;
  c_initial_mM: number;
  c_max_product_mM: number;
  c_is_vial_mM: number;
  dilution_factor: number;
  stoichiometry: Record<string, number>;
  substrate_aliases: string[];
  mass_balance_limits: { low: number; high: number };
  calibration_override: Record<string, Record<string, unknown>>;
}

export interface PeakRow {
  peak_id: number;
  keep: boolean;
  rt_min: number;
  rt_left: number;
  rt_right: number;
  area: number;
  area_pct: number;
  compound_name: string;
  canonical_name: string;
  cas: string;
  role: string;
  rrf: number;
  calib_slope: number;
  calib_intercept: number;
  use_calibration: boolean;
  stoichiometry: number;
  match_score: number;
  match_confidence: string;
  id_method: string;
  spectrum_idx: number;
  area_ratio: number;
  c_vial_mM: number;
  c_flask_mM: number;
  lod_mM: number;
  loq_mM: number;
  selectivity_pct: number;
}

export interface PeakMeta {
  peak_id: number;
  label: string;
  apex_idx: number;
  left_idx: number;
  right_idx: number;
  rt_apex: number;
  rt_left: number;
  rt_right: number;
  area: number;
}

export interface TICData {
  rt: number[];
  tic_raw: number[];
  tic_smooth: number[];
  tic_baseline: number[];
  peaks: PeakMeta[];
}

export interface QuantSummaryOut {
  conversion_pct: number;
  yield_pct: number;
  mass_balance_pct: number;
  missing_carbon_pct: number;
  consumed_mM: number;
  is_area: number;
  selectivities: Record<string, number>;
  area_percent: Record<string, number>;
  warnings: string[];
  status_quality: string;
  c_initial_used: number;
  c_max_used: number;
}

export interface AnalyzeResponse {
  job_id: string | null;
  status: "done" | "processing" | "error";
  tic: TICData | null;
  peaks: PeakRow[] | null;
  quant: QuantSummaryOut | null;
  sigma_baseline: number;
  suggested_config: ReactionConfig | null;
}

export interface RecomputeRequest {
  peaks: PeakRow[];
  config: ReactionConfig;
  sigma_baseline: number;
}

export interface RecomputeResponse {
  peaks: PeakRow[];
  quant: QuantSummaryOut;
}

export interface JobStatusResponse {
  status: "processing" | "done" | "error";
  result: AnalyzeResponse | null;
  error: string | null;
}

export interface RunSaveRequest {
  peaks: PeakRow[];
  quant: QuantSummaryOut;
  config: ReactionConfig;
  file_name: string;
  notes: string;
}

export interface RunSummary {
  run_id: string;
  sample_name: string;
  file_name: string;
  created_at: string;
  conversion_pct: number;
  yield_pct: number;
  mass_balance_pct: number;
  missing_carbon_pct: number;
  status_quality: string;
  notes: string;
}

export interface AppSettings {
  signal: Partial<ProcessingSettings>;
  identification: Record<string, unknown>;
  quantification: Record<string, unknown>;
  jobs: Record<string, unknown>;
  ui: Record<string, unknown>;
}

export const DEFAULT_REACTION_CONFIG: ReactionConfig = {
  sample_name: "",
  substrate: "",
  main_product: "",
  c_initial_mM: 0,
  c_max_product_mM: 0,
  c_is_vial_mM: 0,
  dilution_factor: 1,
  stoichiometry: { default: 1.0 },
  substrate_aliases: [],
  mass_balance_limits: { low: 50, high: 110 },
  calibration_override: {},
};

export const DEFAULT_PROCESSING_SETTINGS: ProcessingSettings = {
  baseline_window_pct: 5.0,
  savgol_window: 7,
  savgol_poly: 2,
  min_prominence_pct: 5.0,
  min_width_scans: 3,
  min_area_pct: 3.0,
  min_height_abs: 0.0,
  min_distance_scans: 1,
  integration_method: "simpson",
  boundary_method: "half_width",
};