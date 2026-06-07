import { useCallback, useState } from "react";
import { exportCSV, exportHistoryCSV, saveRun } from "@/api/endpoints";
import { useRunStore } from "@/store/runStore";

export function useExport() {
  const [isExporting, setIsExporting] = useState(false);
  const [error, setError]             = useState<string | null>(null);

  const { peaks, quant, config, fileName } = useRunStore();

  const exportRun = useCallback(
    async (format: "ich_q2r1" | "full" = "ich_q2r1") => {
      if (!quant || peaks.length === 0) return;

      setIsExporting(true);
      setError(null);

      try {
        await exportCSV({ peaks, quant, config, format });
      } catch (err: unknown) {
        const msg =
          (err as { normalizedMessage?: string })?.normalizedMessage ??
          (err instanceof Error ? err.message : "Erro ao exportar CSV.");
        setError(msg);
        throw err;
      } finally {
        setIsExporting(false);
      }
    },
    [peaks, quant, config]
  );

  const exportHistory = useCallback(async (ids: string[]) => {
    setIsExporting(true);
    setError(null);

    try {
      await exportHistoryCSV(ids);
    } catch (err: unknown) {
      const msg =
        (err as { normalizedMessage?: string })?.normalizedMessage ??
        (err instanceof Error ? err.message : "Erro ao exportar histórico.");
      setError(msg);
      throw err;
    } finally {
      setIsExporting(false);
    }
  }, []);

  const saveCurrentRun = useCallback(
    async (notes: string = "") => {
      if (!quant || peaks.length === 0) return null;

      setIsExporting(true);
      setError(null);

      try {
        const runId = await saveRun({
          peaks,
          quant,
          config,
          file_name: fileName,
          notes,
        });
        return runId;
      } catch (err: unknown) {
        const msg =
          (err as { normalizedMessage?: string })?.normalizedMessage ??
          (err instanceof Error ? err.message : "Erro ao salvar run.");
        setError(msg);
        throw err;
      } finally {
        setIsExporting(false);
      }
    },
    [peaks, quant, config, fileName]
  );

  return { exportRun, exportHistory, saveCurrentRun, isExporting, error };
}