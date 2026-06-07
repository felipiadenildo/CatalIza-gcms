import { useCallback, useState } from "react";
import { recompute } from "@/api/endpoints";
import { useRunStore } from "@/store/runStore";

export function useRecompute() {
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError]         = useState<string | null>(null);

  const { peaks, config, sigmaBaseline, setQuant } = useRunStore();

  const run = useCallback(async () => {
    if (peaks.length === 0) return;

    setIsLoading(true);
    setError(null);

    try {
      const response = await recompute({
        peaks,
        config,
        sigma_baseline: sigmaBaseline,
      });

      setQuant(response.quant, response.peaks);

      return response;
    } catch (err: unknown) {
      const msg =
        (err as { normalizedMessage?: string })?.normalizedMessage ??
        (err instanceof Error ? err.message : "Erro ao recalcular métricas.");
      setError(msg);
      throw err;
    } finally {
      setIsLoading(false);
    }
  }, [peaks, config, sigmaBaseline, setQuant]);

  return { recompute: run, isLoading, error };
}