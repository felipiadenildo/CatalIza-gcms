export type TabId = "single-run" | "batch" | "history" | "settings";

export type CardKey = "conversion" | "yield" | "mass_balance" | "selectivity";

export type StatusChip = "OK" | "WARNING" | "FATAL" | "IDLE";

export type RunStatus =
  | "idle"
  | "uploading"
  | "processing"
  | "done"
  | "error";

export type MatchConfidence = "HIGH" | "MEDIUM" | "LOW" | "NONE";

export type PeakRole =
  | "IS"
  | "substrate"
  | "product"
  | "byproduct"
  | "ignore"
  | "unknown";

export type IntegrationMethod = "simpson" | "trapezoid";

export type BoundaryMethod = "half_width" | "valley" | "tangent_skim";

export interface ToastMessage {
  id: string;
  type: "success" | "warning" | "error" | "info";
  message: string;
}