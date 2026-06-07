import { create } from "zustand";
import type {
  TICData,
  PeakRow,
  QuantSummaryOut,
  ReactionConfig,
} from "@/types/api";
import type { CardKey, RunStatus } from "@/types/ui";
import { DEFAULT_REACTION_CONFIG } from "@/types/api";

interface RunState {
  // ── Status ──────────────────────────────────────────────────────────────────
  status: RunStatus;
  jobId: string | null;
  uploadProgress: number;

  // ── Dados do run ativo ───────────────────────────────────────────────────────
  raw: TICData | null;
  peaks: PeakRow[];
  quant: QuantSummaryOut | null;
  sigmaBaseline: number;

  // ── Configuração da reação ───────────────────────────────────────────────────
  config: ReactionConfig;

  // ── Estado de edição ─────────────────────────────────────────────────────────
  dirty: boolean;
  fileName: string;

  // ── UI do run ────────────────────────────────────────────────────────────────
  activeCard: CardKey | null;
  selectedPeakId: number | null;
}

interface RunActions {
  setStatus: (status: RunStatus) => void;
  setJobId: (jobId: string | null) => void;
  setUploadProgress: (pct: number) => void;

  setResult: (
    raw: TICData,
    peaks: PeakRow[],
    quant: QuantSummaryOut,
    sigma: number,
    fileName: string
  ) => void;

  updatePeakRow: (peakId: number, patch: Partial<PeakRow>) => void;
  updateBounds: (peakId: number, rtLeft: number, rtRight: number) => void;

  setQuant: (quant: QuantSummaryOut, peaks: PeakRow[]) => void;

  setConfig: (config: ReactionConfig) => void;
  patchConfig: (patch: Partial<ReactionConfig>) => void;

  setActiveCard: (card: CardKey | null) => void;
  setSelectedPeakId: (id: number | null) => void;

  clearRun: () => void;
}

type RunStore = RunState & RunActions;

export const useRunStore = create<RunStore>((set) => ({
  // ── Estado inicial ────────────────────────────────────────────────────────
  status:         "idle",
  jobId:          null,
  uploadProgress: 0,
  raw:            null,
  peaks:          [],
  quant:          null,
  sigmaBaseline:  0,
  config:         { ...DEFAULT_REACTION_CONFIG },
  dirty:          false,
  fileName:       "",
  activeCard:     null,
  selectedPeakId: null,

  // ── Actions ───────────────────────────────────────────────────────────────

  setStatus: (status) => set({ status }),

  setJobId: (jobId) => set({ jobId }),

  setUploadProgress: (uploadProgress) => set({ uploadProgress }),

  setResult: (raw, peaks, quant, sigma, fileName) =>
    set({
      raw,
      peaks,
      quant,
      sigmaBaseline:  sigma,
      fileName,
      status:         "done",
      dirty:          false,
      uploadProgress: 100,
      jobId:          null,
    }),

  updatePeakRow: (peakId, patch) =>
    set((state) => ({
      peaks: state.peaks.map((p) =>
        p.peak_id === peakId ? { ...p, ...patch } : p
      ),
      dirty: true,
    })),

  updateBounds: (peakId, rtLeft, rtRight) =>
    set((state) => ({
      peaks: state.peaks.map((p) =>
        p.peak_id === peakId
          ? { ...p, rt_left: rtLeft, rt_right: rtRight }
          : p
      ),
      dirty: true,
    })),

  setQuant: (quant, peaks) =>
    set({
      quant,
      peaks,
      dirty: false,
    }),

  setConfig: (config) => set({ config }),

  patchConfig: (patch) =>
    set((state) => ({
      config: { ...state.config, ...patch },
    })),

  setActiveCard: (activeCard) => set({ activeCard }),

  setSelectedPeakId: (selectedPeakId) => set({ selectedPeakId }),

  clearRun: () =>
    set((state) => ({
      status:         "idle",
      jobId:          null,
      uploadProgress: 0,
      raw:            null,
      peaks:          [],
      quant:          null,
      sigmaBaseline:  0,
      dirty:          false,
      fileName:       "",
      activeCard:     null,
      selectedPeakId: null,
      // Preserva config e preset para a próxima corrida
      config:         state.config,
    })),
}));