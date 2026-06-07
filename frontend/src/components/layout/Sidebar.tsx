import { NavLink } from "react-router-dom";
import {
  FlaskConical,
  Layers,
  History,
  Settings,
  ChevronLeft,
  ChevronRight,
} from "lucide-react";
import { useUIStore } from "@/store/uiStore";
import { clsx } from "clsx";

const NAV_ITEMS = [
  { to: "/",         label: "Single Run",      icon: FlaskConical },
  { to: "/batch",    label: "Sequence (Batch)", icon: Layers       },
  { to: "/history",  label: "History",          icon: History      },
  { to: "/settings", label: "Settings",         icon: Settings     },
];

export default function Sidebar() {
  const { sidebarCollapsed, toggleSidebar } = useUIStore();

  return (
    <aside
      className={clsx(
        "flex flex-col shrink-0 h-full bg-white border-r border-slate-200",
        "transition-all duration-200 ease-in-out",
        sidebarCollapsed ? "w-14" : "w-52"
      )}
    >
      {/* Logo */}
      <div className="flex items-center h-14 px-4 border-b border-slate-200 shrink-0">
        <span className="text-2xl">🧪</span>
        {!sidebarCollapsed && (
          <span className="ml-2 text-lg font-black text-slate-800 tracking-tight">
            GC-MS <span className="text-blue-600 font-light">LIMS</span>
          </span>
        )}
      </div>

      {/* Nav items */}
      <nav className="flex flex-col gap-1 p-2 flex-1">
        {NAV_ITEMS.map(({ to, label, icon: Icon }) => (
          <NavLink
            key={to}
            to={to}
            end={to === "/"}
            className={({ isActive }) =>
              clsx(
                "flex items-center gap-3 px-3 py-2 rounded-lg text-sm font-semibold",
                "transition-colors duration-100",
                isActive
                  ? "bg-blue-600 text-white shadow-sm"
                  : "text-slate-600 hover:bg-slate-100 hover:text-slate-800"
              )
            }
          >
            <Icon size={16} className="shrink-0" />
            {!sidebarCollapsed && (
              <span className="truncate">{label}</span>
            )}
          </NavLink>
        ))}
      </nav>

      {/* Collapse toggle */}
      <button
        onClick={toggleSidebar}
        className="flex items-center justify-center h-10 border-t border-slate-200
                   text-slate-400 hover:text-slate-600 hover:bg-slate-50
                   transition-colors duration-100"
        title={sidebarCollapsed ? "Expandir" : "Colapsar"}
      >
        {sidebarCollapsed ? <ChevronRight size={16} /> : <ChevronLeft size={16} />}
      </button>
    </aside>
  );
}