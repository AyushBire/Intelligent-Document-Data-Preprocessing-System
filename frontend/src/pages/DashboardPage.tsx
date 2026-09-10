// ✅ DashboardPage — no Sidebar import, no layout wrapper, just page content.
import { useQuery } from "@tanstack/react-query";
import { getStats } from "../api/documents";
import { FileText, Upload, Tag, TrendingUp } from "lucide-react";

export default function DashboardPage() {
  const { data: stats } = useQuery({ queryKey: ["stats"], queryFn: getStats });

  const cards = [
    { label: "Total Documents", value: stats?.total ?? "—",            icon: FileText,   color: "text-indigo-400", bg: "bg-indigo-500/10" },
    { label: "Document Types",  value: stats?.by_type?.length ?? "—",  icon: Tag,        color: "text-violet-400", bg: "bg-violet-500/10" },
    { label: "Top Type",        value: stats?.by_type?.[0]?.document_type?.replace(/_/g," ") ?? "—", icon: TrendingUp, color: "text-emerald-400", bg: "bg-emerald-500/10" },
    { label: "Uploaded Today",  value: 7,                              icon: Upload,     color: "text-amber-400",  bg: "bg-amber-500/10"  },
  ];

  return (
    <div className="p-8 max-w-4xl mx-auto space-y-8">
      {/* Header */}
      <div>
        <h1 className="text-2xl font-bold text-white tracking-tight">Dashboard</h1>
        <p className="text-slate-400 text-sm mt-1">Overview of your document processing activity</p>
      </div>

      {/* Stat cards */}
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
        {cards.map(({ label, value, icon: Icon, color, bg }) => (
          <div key={label} className="bg-[#1a1d2e] border border-[#2e3250] rounded-xl p-5 space-y-3">
            <div className={`w-9 h-9 rounded-lg ${bg} flex items-center justify-center`}>
              <Icon size={16} className={color} />
            </div>
            <div>
              <p className="text-2xl font-bold text-white leading-none">{value}</p>
              <p className="text-slate-500 text-xs mt-1">{label}</p>
            </div>
          </div>
        ))}
      </div>

      {/* Type breakdown */}
      {stats?.by_type && stats.by_type.length > 0 && (
        <div className="bg-[#1a1d2e] border border-[#2e3250] rounded-xl p-6">
          <p className="text-sm font-semibold text-white mb-4 flex items-center gap-2">
            <Tag size={14} className="text-slate-500" /> By Document Type
          </p>
          <div className="space-y-4">
            {stats.by_type.map(({ document_type, count }: { document_type: string; count: number }) => {
              const pct = stats.total > 0 ? Math.round((count / stats.total) * 100) : 0;
              return (
                <div key={document_type}>
                  <div className="flex justify-between text-sm mb-1.5">
                    <span className="text-slate-300 capitalize">{document_type.replace(/_/g, " ")}</span>
                    <span className="text-slate-500 text-xs">{count} · {pct}%</span>
                  </div>
                  <div className="h-1.5 bg-[#242840] rounded-full overflow-hidden">
                    <div
                      className="h-full bg-gradient-to-r from-indigo-500 to-violet-500 rounded-full"
                      style={{ width: `${pct}%` }}
                    />
                  </div>
                </div>
              );
            })}
          </div>
        </div>
      )}
    </div>
  );
}