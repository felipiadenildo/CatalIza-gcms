import { useCallback, useState } from "react";
import { analyze, pollJob } from "@/api/endpoints";
import { useRunStore } from "@/store/runStore";
import type { ReactionConfig, ProcessingSettings } from "@/types/api";

const POLL_INTERVAL_MS = 1500;

export function useAnalyze() {
  const [error, setError] = useState<string | null>(null);

  const {
    status,
    setStatus,
    setJobId,
    setUploadProgress,
    setResult,
    config,
  } = useRunStore();

  const isLoading = status === "uploading" || status === "processing";

  const run = useCallback(
    async (
      file: File,
      overrideConfig?: ReactionConfig,
      settings?: Partial<ProcessingSettings>
    ) => {
      setError(null);
      setStatus("uploading");
      setUploadProgress(0);

      const activeConfig = overrideConfig ?? config;

      try {
        // ── 1. POST /analyze com progresso de upload ──────────────────────────
        const response = await analyze(
          file,
          activeConfig,
          settings,
          (pct) => setUploadProgress(pct)
        );

        // ── 2. Resposta síncrona (arquivo <= 10MB) ────────────────────────────
        if (response.status === "done") {
          if (response.tic && response.peaks && response.quant) {
            setResult(
              response.tic,
              response.peaks,
              response.quant,
              response.sigma_baseline,
              file.name
            );
          }
          return response;
        }

        // ── 3. Resposta assíncrona — inicia polling ───────────────────────────
        if (response.status === "processing" && response.job_id) {
          setStatus("processing");
          setJobId(response.job_id);

          const result = await _pollUntilDone(response.job_id);

          if (result.status === "done" && result.result) {
            const r = result.result;
            if (r.tic && r.peaks && r.quant) {
              setResult(
                r.tic,
                r.peaks,
                r.quant,
                r.sigma_baseline,
                file.name
              );
            }
            return r;
          }

          throw new Error(result.error ?? "Job falhou sem mensagem de erro.");
        }

        throw new Error("Resposta inesperada do servidor.");
      } catch (err: unknown) {
        const msg =
          (err as { normalizedMessage?: string })?.normalizedMessage ??
          (err instanceof Error ? err.message : "Erro desconhecido.");
        setError(msg);
        setStatus("error");
        throw err;
      }
    },
    [config, setStatus, setJobId, setUploadProgress, setResult]
  );

  return { analyze: run, isLoading, error };
}

// ── Polling helper ────────────────────────────────────────────────────────────

async function _pollUntilDone(jobId: string) {
  return new Promise<Awaited<ReturnType<typeof pollJob>>>((resolve, reject) => {
    const interval = setInterval(async () => {
      try {
        const status = await pollJob(jobId);

        if (status.status === "done" || status.status === "error") {
          clearInterval(interval);
          resolve(status);
        }
      } catch (err) {
        clearInterval(interval);
        reject(err);
      }
    }, POLL_INTERVAL_MS);
  });
}