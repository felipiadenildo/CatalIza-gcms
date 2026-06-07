import client from "./client";
import type {
  AnalyzeResponse,
  AppSettings,
  JobStatusResponse,
  ReactionConfig,
  RecomputeRequest,
  RecomputeResponse,
  RunSaveRequest,
  RunSummary,
  ProcessingSettings,
} from "@/types/api";

// ── Análise ───────────────────────────────────────────────────────────────────

export async function analyze(
  file: File,
  config: ReactionConfig,
  settings?: Partial<ProcessingSettings>,
  onUploadProgress?: (pct: number) => void
): Promise<AnalyzeResponse> {
  const fd = new FormData();
  fd.append("file", file);
  fd.append("config", JSON.stringify(config));
  if (settings) {
    fd.append("settings", JSON.stringify(settings));
  }

  const response = await client.post<AnalyzeResponse>("/analyze", fd, {
    headers: { "Content-Type": "multipart/form-data" },
    onUploadProgress: (evt) => {
      if (onUploadProgress && evt.total) {
        const pct = Math.round((evt.loaded / evt.total) * 100);
        onUploadProgress(pct);
      }
    },
  });

  return response.data;
}

export async function pollJob(jobId: string): Promise<JobStatusResponse> {
  const response = await client.get<JobStatusResponse>(`/jobs/${jobId}`);
  return response.data;
}

// ── Recompute ─────────────────────────────────────────────────────────────────

export async function recompute(
  req: RecomputeRequest
): Promise<RecomputeResponse> {
  const response = await client.post<RecomputeResponse>("/recompute", req);
  return response.data;
}

// ── Methods / Presets ─────────────────────────────────────────────────────────

export async function getMethods(): Promise<Record<string, ReactionConfig>> {
  const response = await client.get<{ presets: Record<string, ReactionConfig> }>(
    "/methods"
  );
  return response.data.presets;
}

export async function saveMethod(
  name: string,
  config: ReactionConfig
): Promise<void> {
  await client.post(`/methods/${encodeURIComponent(name)}`, config);
}

export async function deleteMethod(name: string): Promise<void> {
  await client.delete(`/methods/${encodeURIComponent(name)}`);
}

// ── Export CSV ────────────────────────────────────────────────────────────────

export async function exportCSV(req: {
  peaks: RecomputeRequest["peaks"];
  quant: RecomputeResponse["quant"];
  config: ReactionConfig;
  format: "ich_q2r1" | "full";
}): Promise<void> {
  const response = await client.post("/export/csv", req, {
    responseType: "blob",
  });

  const url = URL.createObjectURL(new Blob([response.data]));
  const a   = document.createElement("a");

  // Tenta extrair filename do header Content-Disposition
  const disposition: string =
    response.headers["content-disposition"] ?? "";
  const match = disposition.match(/filename="?([^";\n]+)"?/);
  a.download = match?.[1] ?? "gcms_results.csv";

  a.href = url;
  document.body.appendChild(a);
  a.click();
  document.body.removeChild(a);
  URL.revokeObjectURL(url);
}

// ── History ───────────────────────────────────────────────────────────────────

export async function getHistory(): Promise<RunSummary[]> {
  const response = await client.get<{ runs: RunSummary[] }>("/history");
  return response.data.runs;
}

export async function saveRun(req: RunSaveRequest): Promise<string> {
  const response = await client.post<{ run_id: string }>("/history", req);
  return response.data.run_id;
}

export async function exportHistoryCSV(ids: string[]): Promise<void> {
  const params = new URLSearchParams();
  ids.forEach((id) => params.append("ids[]", id));

  const response = await client.get(`/history/export?${params.toString()}`, {
    responseType: "blob",
  });

  const url = URL.createObjectURL(new Blob([response.data]));
  const a   = document.createElement("a");
  a.href    = url;
  a.download = "gcms_history_export.csv";
  document.body.appendChild(a);
  a.click();
  document.body.removeChild(a);
  URL.revokeObjectURL(url);
}

export async function deleteRun(runId: string): Promise<void> {
  await client.delete(`/history/${runId}`);
}

// ── Settings ──────────────────────────────────────────────────────────────────

export async function getSettings(): Promise<AppSettings> {
  const response = await client.get<AppSettings>("/settings");
  return response.data;
}

export async function saveSettings(settings: AppSettings): Promise<AppSettings> {
  const response = await client.put<AppSettings>("/settings", settings);
  return response.data;
}