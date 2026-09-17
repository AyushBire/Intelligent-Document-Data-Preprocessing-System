import { useQuery } from "@tanstack/react-query";
import { getStats, listDocuments } from "../api/documents";
import { FileText, Tag, TrendingUp, Clock } from "lucide-react";
import StatusBadge from "../components/StatusBadge";

function isToday(iso: string) {
  const d = new Date(iso);
  const now = new Date();
  return (
    d.getFullYear() === now.getFullYear() &&
    d.getMonth() === now.getMonth() &&
    d.getDate() === now.getDate()
  );
}

function timeAgo(iso: string) {
  const diffMs = Date.now() - new Date(iso).getTime();
  const mins = Math.round(diffMs / 60000);
  if (mins < 1) return "just now";
  if (mins < 60) return `${mins}m ago`;
  const hours = Math.round(mins / 60);
  if (hours < 24) return `${hours}h ago`;
  const days = Math.round(hours / 24);
  return `${days}d ago`;
}

export default function DashboardPage() {
  // refetchInterval keeps this page feeling "live" even if a document
  // finishes processing while the user is sitting here idle (rather than
  // only refreshing on navigation).
  const { data: stats, dataUpdatedAt } = useQuery({
    queryKey: ["stats"],
    queryFn: getStats,
    refetchInterval: 15000,
  });

  const { data: recentDocs = [] } = useQuery({
    queryKey: ["documents", "recent"],
    // Reuses the same list endpoint the Database page uses — no new API
    // needed. Ordered newest-first by the backend already.
    queryFn: () => listDocuments({ limit: 50 }),
    refetchInterval: 15000,
  });

  const uploadedToday = recentDocs.filter((d) => isToday(d.created_at)).length;
  const topType = stats?.by_type?.[0]?.document_type?.replace(/_/g, " ") ?? "—";

  const cards = [
    {
      label: "Total documents",
      value: stats?.total ?? "—",
      icon: FileText,
      color: "text-indigo-400",
      bg: "bg-indigo-500/10",
    },
    {
      label: "Document types",
      value: stats?.by_type?.length ?? "—",
      icon: Tag,
      color: "text-violet-400",
      bg: "bg-violet-500/10",
    },
    {
      label: "Most common type",
      value: topType,
      icon: TrendingUp,
      color: "text-emerald-400",
      bg: "bg-emerald-500/10",
      capitalize: true,
    },
    {
      label: "Uploaded today",
      value: uploadedToday,
      icon: Clock,
      color: "text-amber-400",
      bg: "bg-amber-500/10",
    },
  ];

  return (
    <main className="p-8 max-w-4xl mx-auto space-y-8">
      <div>
        <h1 className="text-2xl font-bold text-white tracking-tight">Dashboard</h1>
        <p className="text-slate-400 text-sm mt-1">Overview of your document processing activity</p>
      </div>

      {/* Screen-reader-only live announcement so assistive tech hears
          updates without needing to re-visit the page. Visually the
          numbers below update in place. */}
      <p className="sr-only" role="status" aria-live="polite">
        {stats ? `${stats.total} total documents. ${uploadedToday} uploaded today.` : "Loading stats"}
      </p>

      <section aria-label="Summary statistics" className="grid grid-cols-2 lg:grid-cols-4 gap-4">
        {cards.map(({ label, value, icon: Icon, color, bg, capitalize }) => (
          <div
            key={label}
            className="bg-[#141726] border border-[#2e3250] rounded-xl p-5 space-y-3"
          >
            <div className={`w-9 h-9 rounded-lg ${bg} flex items-center justify-center`}>
              <Icon size={16} className={color} aria-hidden="true" />
            </div>
            <div>
              <p
                className={`text-2xl font-bold text-white leading-none tabular-nums ${
                  capitalize ? "capitalize text-lg" : ""
                }`}
              >
                {value}
              </p>
              <p className="text-slate-500 text-xs mt-1">{label}</p>
            </div>
          </div>
        ))}
      </section>

      <div className="grid md:grid-cols-2 gap-6">
        {/* Type breakdown */}
        <section
          aria-labelledby="by-type-heading"
          className="bg-[#141726] border border-[#2e3250] rounded-xl p-6"
        >
          <h2 id="by-type-heading" className="text-sm font-semibold text-white mb-4 flex items-center gap-2">
            <Tag size={14} className="text-slate-500" aria-hidden="true" /> By document type
          </h2>
          {!stats?.by_type || stats.by_type.length === 0 ? (
            <p className="text-slate-500 text-sm">No documents processed yet.</p>
          ) : (
            <div className="space-y-4">
              {stats.by_type.map(({ document_type, count }) => {
                const pct = stats.total > 0 ? Math.round((count / stats.total) * 100) : 0;
                return (
                  <div key={document_type}>
                    <div className="flex justify-between text-sm mb-1.5">
                      <span className="text-slate-300 capitalize">
                        {document_type.replace(/_/g, " ")}
                      </span>
                      <span className="text-slate-500 text-xs tabular-nums">
                        {count} · {pct}%
                      </span>
                    </div>
                    <div
                      className="h-1.5 bg-[#242840] rounded-full overflow-hidden"
                      role="progressbar"
                      aria-valuenow={pct}
                      aria-valuemin={0}
                      aria-valuemax={100}
                      aria-label={`${document_type.replace(/_/g, " ")}: ${pct}%`}
                    >
                      <div
                        className="h-full bg-gradient-to-r from-indigo-500 to-violet-500 rounded-full"
                        style={{ width: `${pct}%` }}
                      />
                    </div>
                  </div>
                );
              })}
            </div>
          )}
        </section>

        {/* Recent activity */}
        <section
          aria-labelledby="recent-heading"
          className="bg-[#141726] border border-[#2e3250] rounded-xl p-6"
        >
          <h2 id="recent-heading" className="text-sm font-semibold text-white mb-4 flex items-center gap-2">
            <Clock size={14} className="text-slate-500" aria-hidden="true" /> Recent uploads
          </h2>
          {recentDocs.length === 0 ? (
            <p className="text-slate-500 text-sm">
              Nothing here yet — process a document to see it appear.
            </p>
          ) : (
            <ul role="list" className="space-y-3">
              {recentDocs.slice(0, 5).map((doc) => (
                <li key={doc.id} className="flex items-center justify-between gap-3">
                  <div className="min-w-0">
                    <p className="text-slate-200 text-sm truncate">{doc.filename}</p>
                    <p className="text-slate-600 text-xs mt-0.5">{timeAgo(doc.created_at)}</p>
                  </div>
                  <StatusBadge value={doc.document_type} />
                </li>
              ))}
            </ul>
          )}
        </section>
      </div>

      {dataUpdatedAt > 0 && (
        <p className="text-slate-700 text-xs text-center">
          Last updated {new Date(dataUpdatedAt).toLocaleTimeString()}
        </p>
      )}
    </main>
  );
}