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
  { to: "/",         label: "Single Run", icon: FlaskConical },
  { to: "/batch",    label: "Batch",      icon: Layers       },
  { to: "/history",  label: "History",    icon: History      },
  { to: "/settings", label: "Settings",   icon: Settings     },
];

export default function Sidebar() {
  const { sidebarCollapsed, toggleSidebar } = useUIStore();

  return (
    <aside
      className={clsx(
        "flex flex-col shrink-0 h-full bg-[#161b22] border-r border-[#30363d]",
        "transition-all duration-200 ease-in-out",
        sidebarCollapsed ? "w-14" : "w-48"
      )}
    >
      {/* Logo */}
      <div className="flex items-center h-12 px-3 border-b border-[#30363d] shrink-0">
        <FlaskConical className="text-[#58a6ff] shrink-0" size={20} />
        {!sidebarCollapsed && (
          <span className="ml-2 font-semibold text-[#e6edf3] text-sm truncate">
            CatalIza
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
                "flex items-center gap-3 px-2 py-2 rounded-md text-sm",
                "transition-colors duration-100",
                isActive
                  ? "bg-[#21262d] text-[#58a6ff] border-l-2 border-[#58a6ff]"
                  : "text-[#8b949e] hover:bg-[#21262d] hover:text-[#e6edf3]"
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
        className="flex items-center justify-center h-10 border-t border-[#30363d]
                   text-[#8b949e] hover:text-[#e6edf3] hover:bg-[#21262d]
                   transition-colors duration-100"
        title={sidebarCollapsed ? "Expandir sidebar" : "Colapsar sidebar"}
      >
        {sidebarCollapsed ? <ChevronRight size={16} /> : <ChevronLeft size={16} />}
      </button>
    </aside>
  );
}