import { useCallback, useEffect, useRef, useState } from "react";
import { useNavigate } from "react-router-dom";
import { useQueryClient } from "@tanstack/react-query";
import {
  Upload,
  FileText,
  CheckCircle,
  ExternalLink,
  AlertCircle,
  Download,
  FileJson,
} from "lucide-react";
import type { JobStatus, DocumentResponse } from "../types";
import ProgressBar from "../components/ProgressBar";
import StatusBadge from "../components/StatusBadge";
import { uploadDocument, getJobStatus, getDocument } from "../api/documents";

type Stage = "idle" | "uploading" | "processing" | "done" | "error";

// ── Persisted job tracking ──────────────────────────────────────────────
// Keeps the in-flight job alive across route changes AND full page
// refreshes. Job state used to live only in this component's useState,
// which gets wiped the instant it unmounts (e.g. navigating to Dashboard
// mid-upload).
const STORAGE_KEY = "idps_active_job";

interface StoredJob {
  job_id: string;
  filename: string;
}

function saveActiveJob(job: StoredJob) {
  try {
    localStorage.setItem(STORAGE_KEY, JSON.stringify(job));
  } catch {
    // localStorage can fail (private browsing, quota) — non-fatal.
  }
}

function loadActiveJob(): StoredJob | null {
  try {
    const raw = localStorage.getItem(STORAGE_KEY);
    return raw ? (JSON.parse(raw) as StoredJob) : null;
  } catch {
    return null;
  }
}

function clearActiveJob() {
  try {
    localStorage.removeItem(STORAGE_KEY);
  } catch {
    // ignore
  }
}

function downloadBlob(content: string, filename: string, mime: string) {
  const blob = new Blob([content], { type: mime });
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = filename;
  document.body.appendChild(a);
  a.click();
  a.remove();
  URL.revokeObjectURL(url);
}

function baseName(filename: string) {
  return filename.replace(/\.[^./\\]+$/, "") || "document";
}

export default function ProcessPage() {
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const [stage, setStage] = useState<Stage>("idle");
  const [fileName, setFileName] = useState<string>("");
  const [dragOver, setDragOver] = useState(false);
  const [job, setJob] = useState<JobStatus | null>(null);
  const [documentDetail, setDocumentDetail] = useState<DocumentResponse | null>(null);
  const [error, setError] = useState("");
  const pollRef = useRef<ReturnType<typeof setInterval> | null>(null);
  const inputRef = useRef<HTMLInputElement>(null);

  const stopPolling = () => {
    if (pollRef.current) clearInterval(pollRef.current);
  };

  // Dashboard/Database show live document counts — refresh their cached
  // data as soon as a new document lands, so switching to those pages
  // never shows stale numbers.
  const refreshAppData = useCallback(() => {
    queryClient.invalidateQueries({ queryKey: ["stats"] });
    queryClient.invalidateQueries({ queryKey: ["documents"] });
    queryClient.invalidateQueries({ queryKey: ["types"] });
  }, [queryClient]);

  const finishJob = useCallback(
    async (finishedJob: JobStatus) => {
      refreshAppData();
      if (finishedJob.document_id != null) {
        try {
          const doc = await getDocument(finishedJob.document_id);
          setDocumentDetail(doc);
        } catch {
          // Non-fatal — the done panel still shows without download options.
        }
      }
    },
    [refreshAppData]
  );

  const pollJob = useCallback(
    (jobId: string) => {
      pollRef.current = setInterval(async () => {
        try {
          const status = await getJobStatus(jobId);
          setJob(status);
          if (status.status === "done") {
            stopPolling();
            clearActiveJob();
            setStage("done");
            await finishJob(status);
          } else if (status.status === "error") {
            stopPolling();
            clearActiveJob();
            setStage("error");
            setError(status.error ?? "Processing failed");
          }
        } catch {
          stopPolling();
          clearActiveJob();
          setStage("error");
          setError("Lost connection to server");
        }
      }, 1000);
    },
    [finishJob]
  );

  // ── Resume an in-flight job on mount ──────────────────────────────────
  useEffect(() => {
    const stored = loadActiveJob();
    if (!stored) return;

    let cancelled = false;

    (async () => {
      try {
        const status = await getJobStatus(stored.job_id);
        if (cancelled) return;

        setFileName(stored.filename);
        setJob(status);

        if (status.status === "done") {
          clearActiveJob();
          setStage("done");
          await finishJob(status);
        } else if (status.status === "error") {
          clearActiveJob();
          setStage("error");
          setError(status.error ?? "Processing failed");
        } else {
          setStage("processing");
          pollJob(stored.job_id);
        }
      } catch {
        // Job no longer exists server-side (in-memory job store, server
        // may have restarted) — nothing to resume.
        clearActiveJob();
      }
    })();

    return () => {
      cancelled = true;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const handleFile = useCallback(
    async (f: File) => {
      setFileName(f.name);
      setStage("uploading");
      setError("");
      setJob(null);
      setDocumentDetail(null);
      try {
        const res = await uploadDocument(f);
        setStage("processing");
        setJob({ job_id: res.job_id, status: "pending", stage: "", progress: 0 });
        saveActiveJob({ job_id: res.job_id, filename: f.name });
        pollJob(res.job_id);
      } catch (e: unknown) {
        setStage("error");
        setError(e instanceof Error ? e.message : "Upload failed");
      }
    },
    [pollJob]
  );

  const onDrop = useCallback(
    (e: React.DragEvent) => {
      e.preventDefault();
      setDragOver(false);
      const f = e.dataTransfer.files[0];
      if (f) handleFile(f);
    },
    [handleFile]
  );

  const reset = () => {
    stopPolling();
    clearActiveJob();
    setStage("idle");
    setFileName("");
    setJob(null);
    setDocumentDetail(null);
    setError("");
  };

  const handleDownloadJson = () => {
    if (!documentDetail) return;
    downloadBlob(
      JSON.stringify(documentDetail.structured_data, null, 2),
      `${baseName(documentDetail.filename)}_extracted.json`,
      "application/json"
    );
  };

  const handleDownloadReport = () => {
    if (!documentDetail || !documentDetail.report) return;
    downloadBlob(
      documentDetail.report,
      `${baseName(documentDetail.filename)}_report.txt`,
      "text/plain"
    );
  };

  useEffect(() => () => stopPolling(), []);

  return (
    <div className="p-8 max-w-2xl mx-auto space-y-6">
      <div>
        <h1 className="text-2xl font-bold text-white tracking-tight">Process Document</h1>
        <p className="text-slate-400 text-sm mt-1">
          Upload a document to extract and analyze its content
        </p>
      </div>

      {/* ── Idle: Upload Zone ── */}
      {stage === "idle" && (
        <div
          onDrop={onDrop}
          onDragOver={(e) => {
            e.preventDefault();
            setDragOver(true);
          }}
          onDragLeave={() => setDragOver(false)}
          onClick={() => inputRef.current?.click()}
          role="button"
          tabIndex={0}
          aria-label="Upload a document. Drop a file here or activate to browse."
          onKeyDown={(e) => {
            if (e.key === "Enter" || e.key === " ") {
              e.preventDefault();
              inputRef.current?.click();
            }
          }}
          className={`
            relative border-2 border-dashed rounded-2xl p-16 text-center cursor-pointer
            transition-colors duration-200
            focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-indigo-400 focus-visible:ring-offset-2 focus-visible:ring-offset-[#0b0d14]
            ${
              dragOver
                ? "border-indigo-400 bg-indigo-500/10"
                : "border-[#2e3250] hover:border-indigo-500/40 hover:bg-[#1a1d2e]/60"
            }
          `}
        >
          <input
            ref={inputRef}
            type="file"
            accept=".jpg,.jpeg,.png,.bmp,.tiff,.pdf"
            className="hidden"
            aria-hidden="true"
            tabIndex={-1}
            onChange={(e) => e.target.files?.[0] && handleFile(e.target.files[0])}
          />
          <div
            className={`w-16 h-16 rounded-2xl mx-auto mb-5 flex items-center justify-center transition-colors ${
              dragOver ? "bg-indigo-500/20" : "bg-[#1e2135]"
            }`}
          >
            <Upload size={28} className={dragOver ? "text-indigo-400" : "text-slate-500"} />
          </div>
          <p className="text-white font-semibold text-base">
            {dragOver ? "Drop to upload" : "Drop a file here or click to browse"}
          </p>
          <p className="text-slate-500 text-sm mt-2">JPG, PNG, BMP, TIFF, PDF — max 20 MB</p>

          <div className="flex items-center justify-center gap-2 mt-6 flex-wrap">
            {["JPG", "PNG", "BMP", "TIFF", "PDF"].map((fmt) => (
              <span
                key={fmt}
                className="px-2.5 py-1 bg-[#1e2135] border border-[#2e3250] rounded-md text-xs text-slate-500 font-mono"
              >
                {fmt}
              </span>
            ))}
          </div>
        </div>
      )}

      {/* ── Uploading ── */}
      {stage === "uploading" && (
        <div
          className="bg-[#141726] border border-[#2e3250] rounded-2xl p-10 text-center space-y-4"
          role="status"
          aria-live="polite"
        >
          <div className="w-12 h-12 mx-auto relative" aria-hidden="true">
            <div className="absolute inset-0 rounded-full border-2 border-[#2e3250]" />
            <div className="absolute inset-0 rounded-full border-2 border-indigo-500 border-t-transparent animate-spin motion-reduce:animate-none" />
          </div>
          <div>
            <p className="text-white font-medium text-sm">{fileName}</p>
            <p className="text-slate-500 text-xs mt-1">Uploading…</p>
          </div>
        </div>
      )}

      {/* ── Processing ── */}
      {stage === "processing" && job && (
        <div
          className="bg-[#141726] border border-[#2e3250] rounded-2xl p-8 space-y-6"
          role="status"
          aria-live="polite"
        >
          <div className="flex items-center gap-3 pb-4 border-b border-[#2e3250]">
            <div className="w-9 h-9 rounded-lg bg-indigo-500/15 flex items-center justify-center flex-shrink-0">
              <FileText size={16} className="text-indigo-400" aria-hidden="true" />
            </div>
            <div className="min-w-0">
              <p className="text-white font-medium text-sm truncate">{fileName}</p>
              <p className="text-slate-500 text-xs mt-0.5">Processing document…</p>
            </div>
          </div>
          <ProgressBar progress={job.progress} stage={job.stage} status={job.status} />
          <p className="text-slate-600 text-xs text-center">
            This may take 15–30 seconds. It's safe to switch tabs — progress resumes when you
            come back.
          </p>
        </div>
      )}

      {/* ── Error ── */}
      {stage === "error" && (
        <div
          className="bg-[#141726] border border-red-500/20 rounded-2xl p-10 text-center space-y-5"
          role="alert"
        >
          <div className="w-14 h-14 rounded-2xl bg-red-500/10 mx-auto flex items-center justify-center">
            <AlertCircle size={28} className="text-red-400" aria-hidden="true" />
          </div>
          <div>
            <p className="text-white font-semibold">Upload failed</p>
            <p className="text-slate-500 text-sm mt-1.5 max-w-xs mx-auto">{error}</p>
          </div>
          <button
            onClick={reset}
            className="inline-flex items-center gap-2 px-5 py-2.5 bg-[#242840] hover:bg-[#2e3250] text-slate-300 rounded-lg text-sm transition-colors border border-[#2e3250] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-indigo-400"
          >
            <Upload size={13} aria-hidden="true" /> Try again
          </button>
        </div>
      )}

      {/* ── Done ── */}
      {stage === "done" && job && (
        <div
          className="bg-[#141726] border border-emerald-500/20 rounded-2xl p-8 space-y-6"
          role="status"
        >
          <div className="flex items-center gap-3">
            <div className="w-9 h-9 rounded-lg bg-emerald-500/15 flex items-center justify-center flex-shrink-0">
              <CheckCircle size={18} className="text-emerald-400" aria-hidden="true" />
            </div>
            <div>
              <p className="text-white font-semibold text-sm">Processing complete</p>
              <p className="text-slate-500 text-xs mt-0.5">Document is ready to view</p>
            </div>
          </div>

          <div className="grid grid-cols-2 gap-3">
            <div className="bg-[#1c2036] rounded-xl p-4 border border-[#2e3250]">
              <p className="text-slate-500 text-xs mb-1.5">Document ID</p>
              <p className="text-white font-mono font-bold tabular-nums">#{job.document_id}</p>
            </div>
            <div className="bg-[#1c2036] rounded-xl p-4 border border-[#2e3250]">
              <p className="text-slate-500 text-xs mb-1.5">Status</p>
              <StatusBadge value="done" variant="status" />
            </div>
          </div>

          {/* Download options — the extracted data belongs to the user the
              moment it's produced, independent of the database view. */}
          <div className="border border-teal-500/20 bg-teal-500/5 rounded-xl p-4 space-y-3">
            <p className="text-teal-300 text-xs font-medium flex items-center gap-1.5">
              <FileJson size={13} aria-hidden="true" /> Download extracted data
            </p>
            <div className="flex gap-3">
              <button
                onClick={handleDownloadJson}
                disabled={!documentDetail}
                className="flex-1 flex items-center justify-center gap-2 bg-teal-500/15 hover:bg-teal-500/25 disabled:opacity-40 disabled:cursor-not-allowed text-teal-300 rounded-lg py-2.5 text-sm font-medium transition-colors border border-teal-500/30 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-teal-400"
              >
                <Download size={14} aria-hidden="true" />
                {documentDetail ? "Download JSON" : "Preparing…"}
              </button>
              <button
                onClick={handleDownloadReport}
                disabled={!documentDetail?.report}
                className="flex-1 flex items-center justify-center gap-2 bg-[#1c2036] hover:bg-[#242840] disabled:opacity-40 disabled:cursor-not-allowed text-slate-300 rounded-lg py-2.5 text-sm transition-colors border border-[#2e3250] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-indigo-400"
              >
                <Download size={14} aria-hidden="true" /> Download report
              </button>
            </div>
          </div>

          <div className="flex gap-3 pt-1">
            <button
              onClick={() => navigate(`/database?id=${job.document_id}`)}
              className="flex-1 flex items-center justify-center gap-2 bg-indigo-500 hover:bg-indigo-600 text-white rounded-xl py-3 text-sm font-semibold transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-indigo-400 focus-visible:ring-offset-2 focus-visible:ring-offset-[#141726]"
            >
              <ExternalLink size={14} aria-hidden="true" /> View in Database
            </button>
            <button
              onClick={reset}
              className="flex-1 bg-[#1c2036] hover:bg-[#242840] border border-[#2e3250] text-slate-300 rounded-xl py-3 text-sm transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-indigo-400"
            >
              Process another
            </button>
          </div>
        </div>
      )}
    </div>
  );
}