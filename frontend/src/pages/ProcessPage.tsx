import { useCallback, useEffect, useRef, useState } from "react";
import { useNavigate } from "react-router-dom";
import { Upload, FileText, CheckCircle, XCircle, ExternalLink, AlertCircle } from "lucide-react";
import type { JobStatus } from "../types";
import ProgressBar from "../components/ProgressBar";
import StatusBadge from "../components/StatusBadge";
// ✅ Use the shared API functions — they have the correct endpoints
import { uploadDocument, getJobStatus } from "../api/documents";

type Stage = "idle" | "uploading" | "processing" | "done" | "error";

export default function ProcessPage() {
  const navigate = useNavigate();
  const [stage, setStage] = useState<Stage>("idle");
  const [file, setFile] = useState<File | null>(null);
  const [dragOver, setDragOver] = useState(false);
  const [job, setJob] = useState<JobStatus | null>(null);
  const [error, setError] = useState("");
  const pollRef = useRef<ReturnType<typeof setInterval> | null>(null);
  const inputRef = useRef<HTMLInputElement>(null);

  const stopPolling = () => {
    if (pollRef.current) clearInterval(pollRef.current);
  };

  const pollJob = (jobId: string) => {
    pollRef.current = setInterval(async () => {
      try {
        const status = await getJobStatus(jobId); // ✅ /documents/jobs/:id
        setJob(status);
        if (status.status === "done") {
          stopPolling();
          setStage("done");
        } else if (status.status === "error") {
          stopPolling();
          setStage("error");
          setError(status.error ?? "Processing failed");
        }
      } catch {
        stopPolling();
        setStage("error");
        setError("Lost connection to server");
      }
    }, 1000);
  };

  const handleFile = useCallback(async (f: File) => {
    setFile(f);
    setStage("uploading");
    setError("");
    setJob(null);
    try {
      const res = await uploadDocument(f); // ✅ /documents/upload
      setStage("processing");
      setJob({ job_id: res.job_id, status: "pending", stage: "", progress: 0 });
      pollJob(res.job_id);
    } catch (e: unknown) {
      setStage("error");
      setError(e instanceof Error ? e.message : "Upload failed");
    }
  }, []);

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
    setStage("idle");
    setFile(null);
    setJob(null);
    setError("");
  };

  useEffect(() => () => stopPolling(), []);

  return (
    <div className="p-8 max-w-2xl mx-auto space-y-6">
      {/* Header */}
      <div>
        <h1 className="text-2xl font-bold text-white tracking-tight">Process Document</h1>
        <p className="text-slate-400 text-sm mt-1">Upload a document to extract and analyze its content</p>
      </div>

      {/* ── Idle: Upload Zone ── */}
      {stage === "idle" && (
        <div
          onDrop={onDrop}
          onDragOver={(e) => { e.preventDefault(); setDragOver(true); }}
          onDragLeave={() => setDragOver(false)}
          onClick={() => inputRef.current?.click()}
          className={`
            relative border-2 border-dashed rounded-2xl p-16 text-center cursor-pointer
            transition-all duration-200
            ${dragOver
              ? "border-indigo-400 bg-indigo-500/10 scale-[1.01]"
              : "border-[#2e3250] hover:border-indigo-500/40 hover:bg-[#1a1d2e]/60"
            }
          `}
        >
          <input
            ref={inputRef}
            type="file"
            accept=".jpg,.jpeg,.png,.bmp,.tiff,.pdf"
            className="hidden"
            onChange={(e) => e.target.files?.[0] && handleFile(e.target.files[0])}
          />
          <div className={`w-16 h-16 rounded-2xl mx-auto mb-5 flex items-center justify-center transition-colors ${dragOver ? "bg-indigo-500/20" : "bg-[#1e2135]"}`}>
            <Upload size={28} className={dragOver ? "text-indigo-400" : "text-slate-500"} />
          </div>
          <p className="text-white font-semibold text-base">
            {dragOver ? "Drop to upload" : "Drop a file here or click to browse"}
          </p>
          <p className="text-slate-500 text-sm mt-2">JPG, PNG, BMP, TIFF, PDF — max 20 MB</p>

          {/* Format pills */}
          <div className="flex items-center justify-center gap-2 mt-6 flex-wrap">
            {["JPG", "PNG", "BMP", "TIFF", "PDF"].map((fmt) => (
              <span key={fmt} className="px-2.5 py-1 bg-[#1e2135] border border-[#2e3250] rounded-md text-xs text-slate-500 font-mono">
                {fmt}
              </span>
            ))}
          </div>
        </div>
      )}

      {/* ── Uploading ── */}
      {stage === "uploading" && (
        <div className="bg-[#1a1d2e] border border-[#2e3250] rounded-2xl p-10 text-center space-y-4">
          <div className="w-12 h-12 mx-auto relative">
            <div className="absolute inset-0 rounded-full border-2 border-[#2e3250]" />
            <div className="absolute inset-0 rounded-full border-2 border-indigo-500 border-t-transparent animate-spin" />
          </div>
          <div>
            <p className="text-white font-medium text-sm">{file?.name}</p>
            <p className="text-slate-500 text-xs mt-1">Uploading...</p>
          </div>
        </div>
      )}

      {/* ── Processing ── */}
      {stage === "processing" && job && (
        <div className="bg-[#1a1d2e] border border-[#2e3250] rounded-2xl p-8 space-y-6">
          <div className="flex items-center gap-3 pb-4 border-b border-[#2e3250]">
            <div className="w-9 h-9 rounded-lg bg-indigo-500/15 flex items-center justify-center flex-shrink-0">
              <FileText size={16} className="text-indigo-400" />
            </div>
            <div className="min-w-0">
              <p className="text-white font-medium text-sm truncate">{file?.name}</p>
              <p className="text-slate-500 text-xs mt-0.5">Processing document...</p>
            </div>
          </div>
          <ProgressBar progress={job.progress} stage={job.stage} status={job.status} />
          <p className="text-slate-600 text-xs text-center">
            This may take 15–30 seconds depending on document complexity
          </p>
        </div>
      )}

      {/* ── Error ── */}
      {stage === "error" && (
        <div className="bg-[#1a1d2e] border border-red-500/20 rounded-2xl p-10 text-center space-y-5">
          <div className="w-14 h-14 rounded-2xl bg-red-500/10 mx-auto flex items-center justify-center">
            <AlertCircle size={28} className="text-red-400" />
          </div>
          <div>
            <p className="text-white font-semibold">Upload failed</p>
            <p className="text-slate-500 text-sm mt-1.5 max-w-xs mx-auto">{error}</p>
          </div>
          <button
            onClick={reset}
            className="inline-flex items-center gap-2 px-5 py-2.5 bg-[#242840] hover:bg-[#2e3250] text-slate-300 rounded-lg text-sm transition-colors border border-[#2e3250]"
          >
            <Upload size={13} /> Try again
          </button>
        </div>
      )}

      {/* ── Done ── */}
      {stage === "done" && job && (
        <div className="bg-[#1a1d2e] border border-green-500/20 rounded-2xl p-8 space-y-6">
          <div className="flex items-center gap-3">
            <div className="w-9 h-9 rounded-lg bg-green-500/15 flex items-center justify-center flex-shrink-0">
              <CheckCircle size={18} className="text-green-400" />
            </div>
            <div>
              <p className="text-white font-semibold text-sm">Processing complete</p>
              <p className="text-slate-500 text-xs mt-0.5">Document is ready to view</p>
            </div>
          </div>

          <div className="grid grid-cols-2 gap-3">
            <div className="bg-[#242840] rounded-xl p-4 border border-[#2e3250]">
              <p className="text-slate-500 text-xs mb-1.5">Document ID</p>
              <p className="text-white font-mono font-bold">#{job.document_id}</p>
            </div>
            <div className="bg-[#242840] rounded-xl p-4 border border-[#2e3250]">
              <p className="text-slate-500 text-xs mb-1.5">Status</p>
              <StatusBadge value="done" variant="status" />
            </div>
          </div>

          <div className="flex gap-3 pt-1">
            <button
              onClick={() => navigate(`/database?id=${job.document_id}`)}
              className="flex-1 flex items-center justify-center gap-2 bg-indigo-500 hover:bg-indigo-600 text-white rounded-xl py-3 text-sm font-semibold transition-colors"
            >
              <ExternalLink size={14} /> View in Database
            </button>
            <button
              onClick={reset}
              className="flex-1 bg-[#242840] hover:bg-[#2e3250] border border-[#2e3250] text-slate-300 rounded-xl py-3 text-sm transition-colors"
            >
              Process another
            </button>
          </div>
        </div>
      )}
    </div>
  );
}