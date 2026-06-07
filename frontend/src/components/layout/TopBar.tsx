import { useRunStore }    from "@/store/runStore";
import { clsx }           from "clsx";
import type { RunStatus } from "@/types/ui";

const STATUS_CONFIG: Record<RunStatus, { label: string; color: string }> = {
  idle:       { label: "IDLE",       color: "bg-slate-100 text-slate-500"      },
  uploading:  { label: "UPLOADING",  color: "bg-blue-100 text-blue-700"        },
  processing: { label: "PROCESSING", color: "bg-amber-100 text-amber-700"      },
  done:       { label: "DONE",       color: "bg-green-100 text-green-700"      },
  error:      { label: "ERROR",      color: "bg-red-100 text-red-700"          },
};

export default function TopBar() {
  const { status, uploadProgress, fileName } = useRunStore();
  const cfg = STATUS_CONFIG[status];

  const label =
    status === "uploading" ? `UPLOADING ${uploadProgress}%` : cfg.label;

  return (
    <header className="flex items-center justify-between h-12 px-5
                        bg-white border-b border-slate-200 shrink-0">

      {/* Arquivo ativo */}
      <span className="text-sm font-mono bg-slate-100 text-slate-600 px-3 py-1 rounded">
        {fileName ? `File: ${fileName}` : "Nenhum arquivo carregado"}
      </span>

      {/* Badge de status */}
      <span
        className={clsx(
          "px-2 py-0.5 rounded text-xs font-mono font-bold tracking-wide",
          cfg.color
        )}
      >
        {label}
      </span>
    </header>
  );
}