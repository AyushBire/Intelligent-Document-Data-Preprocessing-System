import { NavLink } from "react-router-dom";
import { FileSearch, Database, LayoutDashboard } from "lucide-react";

const links = [
  { to: "/", icon: LayoutDashboard, label: "Dashboard" },
  { to: "/process", icon: FileSearch, label: "Process Document" },
  { to: "/database", icon: Database, label: "Database" },
];

// ✅ This is the ONE sidebar. Rendered only in App.tsx.
export default function Sidebar() {
  return (
    <aside className="w-56 min-h-screen bg-[#1a1d2e] border-r border-[#2e3250] flex flex-col">
      <div className="px-5 py-6 border-b border-[#2e3250]">
        <div className="flex items-center gap-2">
          <div className="w-7 h-7 rounded-lg bg-indigo-500 flex items-center justify-center">
            <FileSearch size={14} className="text-white" />
          </div>
          <span className="font-semibold text-white text-sm tracking-wide">IDPS</span>
        </div>
        <p className="text-[11px] text-slate-500 mt-1 ml-9">Document Processing</p>
      </div>

      <nav className="flex-1 px-3 py-4 space-y-1">
        {links.map(({ to, icon: Icon, label }) => (
          <NavLink
            key={to}
            to={to}
            end={to === "/"}
            className={({ isActive }: { isActive: boolean }) =>
              `flex items-center gap-3 px-3 py-2.5 rounded-lg text-sm transition-colors ${
                isActive
                  ? "bg-indigo-500/20 text-indigo-400 font-medium"
                  : "text-slate-400 hover:bg-[#242840] hover:text-slate-200"
              }`
            }
          >
            <Icon size={16} />
            {label}
          </NavLink>
        ))}
      </nav>

      <div className="px-5 py-4 border-t border-[#2e3250]">
        <p className="text-[11px] text-slate-600">v1.0.0</p>
      </div>
    </aside>
  );
}