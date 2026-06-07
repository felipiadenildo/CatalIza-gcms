import { create } from "zustand";
import { persist } from "zustand/middleware";
import type { TabId } from "@/types/ui";

interface UIState {
  activeTab:        TabId;
  sidebarCollapsed: boolean;
  theme:            "dark" | "light";
}

interface UIActions {
  setTab:           (tab: TabId) => void;
  toggleSidebar:    () => void;
  setTheme:         (theme: "dark" | "light") => void;
}

type UIStore = UIState & UIActions;

export const useUIStore = create<UIStore>()(
  persist(
    (set) => ({
      // ── Estado inicial ──────────────────────────────────────────────────────
      activeTab:        "single-run",
      sidebarCollapsed: false,
      theme:            "dark",

      // ── Actions ─────────────────────────────────────────────────────────────
      setTab:        (activeTab) => set({ activeTab }),
      toggleSidebar: () =>
        set((state) => ({ sidebarCollapsed: !state.sidebarCollapsed })),
      setTheme:      (theme) => set({ theme }),
    }),
    {
      name: "cataliza-ui-store", // chave no localStorage
      partializer: (state) => ({
        sidebarCollapsed: state.sidebarCollapsed,
        theme:            state.theme,
      }),
    } as Parameters<typeof persist>[1]
  )
);