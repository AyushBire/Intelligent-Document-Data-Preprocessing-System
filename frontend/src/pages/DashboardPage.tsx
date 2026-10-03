import { useQuery } from "@tanstack/react-query";
import { Link } from "react-router-dom";
import {
  ArrowRight,
  ArrowUpRight,
  FileText,
  Layers,
  ScanLine,
  Sun,
} from "lucide-react";
import { getStats, listDocuments } from "../api/documents";
import { EmptyState, ErrorState, Loading, PageHeader } from "../components/ui";
import { dateLabel } from "../lib/utils";
import { readActiveJob, useJob } from "../hooks/useJob";

/** Display real metrics and recent documents. @returns Dashboard. @throws None. */
export default function DashboardPage() {
  const stats = useQuery({
    queryKey: ["stats"],
    queryFn: getStats,
    refetchInterval: 15000,
  });
  const recent = useQuery({
    queryKey: ["documents", "recent"],
    queryFn: () => listDocuments({ limit: 5 }),
    refetchInterval: 15000,
  });
  const active = readActiveJob();
  const job = useJob(active?.job_id);
  const metrics = [
    {
      title: "Total documents",
      value: stats.data?.total,
      icon: FileText,
      caption: "In your document library",
    },
    {
      title: "Uploaded today",
      value: stats.data?.today,
      icon: Sun,
      caption: "Current UTC calendar day",
    },
    {
      title: "Document types",
      value: stats.data?.by_type.length,
      icon: Layers,
      caption: "Automatically classified",
    },
  ];
  return (
    <>
      <PageHeader
        title="Your document workspace"
        subtitle="Turn everyday documents into organized, actionable information."
        actions={
          <Link className="button" to="/extract">
            <ScanLine size={17} />
            New extraction
          </Link>
        }
      />
      <section className="hero-card">
        <div>
          <span className="pill">OCR + AI EXTRACTION</span>
          <h2>
            Less manual entry.
            <br />
            <span>More meaningful work.</span>
          </h2>
          <p>
            Upload a document, extract its key information,
            <br className="desktop-only" /> and review the results in one
            focused workspace.
          </p>
          <Link className="button" to="/extract">
            Extract a document <ArrowRight size={17} />
          </Link>
          <span className="hero-hint">JPG, PNG, BMP & TIFF · Up to 20 MB</span>
        </div>
        <div className="hero-art" aria-hidden="true">
          <div className="document-art">
            <span className="art-logo">
              <FileText size={22} />
              DOCUMENT
            </span>
            <div className="art-line long" />
            <div className="art-line" />
            <div className="art-line short" />
            <div className="art-table">
              {Array.from({ length: 6 }, (_, i) => (
                <span key={i} />
              ))}
            </div>
            <div className="art-line" />
            <div className="art-line short" />
            <span className="scan-line" />
          </div>
          <div className="art-result">
            <span className="green-dot" />
            Structured & ready<small>From document to data</small>
          </div>
        </div>
      </section>
      {job.data && ["pending", "processing"].includes(job.data.status) && (
        <Link to="/extract" className="active-job">
          <ScanLine size={18} />
          Extraction in progress: {active?.filename}
          <span>{job.data.progress}% →</span>
        </Link>
      )}
      {stats.isError ? (
        <ErrorState error={stats.error} retry={() => void stats.refetch()} />
      ) : stats.isPending ? (
        <Loading />
      ) : (
        <section className="stats-grid">
          {metrics.map(({ title, value, icon: Icon, caption }) => (
            <article className="stat-card" key={title}>
              <div>
                <span>{title}</span>
                <Icon size={19} />
              </div>
              <strong>{value}</strong>
              <small>{caption}</small>
            </article>
          ))}
        </section>
      )}
      <section className="dashboard-grid">
        <article className="panel">
          <div className="panel-heading">
            <div>
              <h2>Recent documents</h2>
              <p>Your latest extractions, ready to review.</p>
            </div>
            <Link className="text-link" to="/documents">
              View all <ArrowUpRight size={16} />
            </Link>
          </div>
          {recent.isPending ? (
            <Loading />
          ) : recent.isError ? (
            <ErrorState
              error={recent.error}
              retry={() => void recent.refetch()}
            />
          ) : recent.data.length === 0 ? (
            <EmptyState title="Your first document starts here">
              <p>Extract a document to build your library.</p>
              <Link to="/extract" className="button">
                Get started
              </Link>
            </EmptyState>
          ) : (
            <div className="recent-list">
              {recent.data.map((doc) => (
                <Link
                  to={`/documents/${doc.id}`}
                  key={doc.id}
                  className="recent-row"
                >
                  <span className="file-icon">
                    <FileText size={20} />
                  </span>
                  <div>
                    <strong>{doc.filename}</strong>
                    <small>{dateLabel(doc.created_at)}</small>
                  </div>
                  <span className="badge">
                    {doc.document_type.replaceAll("_", " ")}
                  </span>
                  <ArrowUpRight size={16} />
                </Link>
              ))}
            </div>
          )}
        </article>
        <article className="panel">
          <div className="panel-heading">
            <div>
              <h2>Document breakdown</h2>
              <p>A view of your library by type.</p>
            </div>
          </div>
          {stats.data?.by_type.length ? (
            <div className="distribution">
              {stats.data.by_type.slice(0, 6).map((type) => (
                <div key={type.document_type}>
                  <div>
                    <span>{type.document_type.replaceAll("_", " ")}</span>
                    <strong>{type.count}</strong>
                  </div>
                  <div className="track">
                    <span
                      style={{
                        width: `${(type.count / stats.data.total) * 100}%`,
                      }}
                    />
                  </div>
                </div>
              ))}
            </div>
          ) : (
            <EmptyState title="No document types yet">
              <p>Your distribution appears after extraction.</p>
            </EmptyState>
          )}
        </article>
      </section>
    </>
  );
}
