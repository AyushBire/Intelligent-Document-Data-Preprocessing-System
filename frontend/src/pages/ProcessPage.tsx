import { useCallback, useEffect, useRef, useState } from "react";
import { useNavigate } from "react-router-dom";
import { Upload, FileText, CheckCircle, XCircle, ExternalLink } from "lucide-react";
import type { JobStatus } from "../types";
import ProgressBar from "../components/ProgressBar";
import StatusBadge from "../components/StatusBadge";

type Stage = "idle" | "uploading" | "processing" | "done" | "error";

type UploadResponse = { job_id: string };

async function uploadDocument(file: File): Promise<UploadResponse> {
  const formData = new FormData();
  formData.append("file", file);

  const response = await fetch("/api/documents", {
    method: "POST",
    body: formData,
  });

  if (!response.ok) {
    throw new Error("Upload failed");
  }

  return response.json() as Promise<UploadResponse>;
}

async function getJobStatus(jobId: string): Promise<JobStatus> {
  const response = await fetch(`/api/jobs/${jobId}`);

  if (!response.ok) {
    throw new Error("Failed to fetch job status");
  }

  return response.json() as Promise<JobStatus>;
}

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
        const status = await getJobStatus(jobId);
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
      const res = await uploadDocument(f);
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
    <div className="p-8 max-w-3xl mx-auto space-y-6">
      <div>
        <h1 className="text-2xl font-bold text-white">Process Document</h1>
        <p className="text-slate-400 text-sm mt-1">Upload a document to extract and analyze its content</p>
      </div>

      {/* Upload Zone */}
      {stage === "idle" && (
        <div
          onDrop={onDrop}
          onDragOver={(e) => { e.preventDefault(); setDragOver(true); }}
          onDragLeave={() => setDragOver(false)}
          onClick={() => inputRef.current?.click()}
          className={`border-2 border-dashed rounded-xl p-16 text-center cursor-pointer transition-colors ${
            dragOver
              ? "border-indigo-400 bg-indigo-500/10"
              : "border-[#2e3250] hover:border-indigo-500/50 hover:bg-[#1a1d2e]"
          }`}
        >
          <input
            ref={inputRef}
            type="file"
            accept=".jpg,.jpeg,.png,.bmp,.tiff,.pdf"
            className="hidden"
            onChange={(e) => e.target.files?.[0] && handleFile(e.target.files[0])}
          />
          <Upload size={36} className="mx-auto text-slate-500 mb-4" />
          <p className="text-slate-300 font-medium">Drop a file here or click to browse</p>
          <p className="text-slate-500 text-sm mt-2">JPG, PNG, BMP, TIFF, PDF — max 20MB</p>
        </div>
      )}

      {/* Uploading */}
      {stage === "uploading" && (
        <div className="bg-[#1a1d2e] border border-[#2e3250] rounded-xl p-8 text-center">
          <div className="animate-spin w-8 h-8 border-2 border-indigo-500 border-t-transparent rounded-full mx-auto mb-4" />
          <p className="text-slate-300">Uploading {file?.name}...</p>
        </div>
      )}

      {/* Processing */}
      {stage === "processing" && job && (
        <div className="bg-[#1a1d2e] border border-[#2e3250] rounded-xl p-8 space-y-6">
          <div className="flex items-center gap-3">
            <FileText size={20} className="text-indigo-400" />
            <p className="text-white font-medium text-sm">{file?.name}</p>
          </div>
          <ProgressBar
            progress={job.progress}
            stage={job.stage}
            status={job.status}
          />
          <p className="text-slate-500 text-xs text-center">
            This may take 15–30 seconds depending on document complexity
          </p>
        </div>
      )}

      {/* Error */}
      {stage === "error" && (
        <div className="bg-[#1a1d2e] border border-red-500/30 rounded-xl p-8 text-center space-y-4">
          <XCircle size={36} className="mx-auto text-red-400" />
          <p className="text-red-400 font-medium">Processing Failed</p>
          <p className="text-slate-400 text-sm">{error}</p>
          <button
            onClick={reset}
            className="px-4 py-2 bg-[#242840] hover:bg-[#2e3250] text-slate-300 rounded-lg text-sm transition-colors"
          >
            Try Again
          </button>
        </div>
      )}

      {/* Done */}
      {stage === "done" && job && (
        <div className="bg-[#1a1d2e] border border-green-500/30 rounded-xl p-8 space-y-6">
          <div className="flex items-center gap-3">
            <CheckCircle size={22} className="text-green-400" />
            <p className="text-white font-semibold">Processing Complete</p>
          </div>

          <div className="grid grid-cols-2 gap-3 text-sm">
            <div className="bg-[#242840] rounded-lg p-3">
              <p className="text-slate-500 text-xs mb-1">Document ID</p>
              <p className="text-white font-mono font-bold">#{job.document_id}</p>
            </div>
            <div className="bg-[#242840] rounded-lg p-3">
              <p className="text-slate-500 text-xs mb-1">Status</p>
              <StatusBadge value="done" variant="status" />
            </div>
          </div>

          <div className="flex gap-3">
            <button
              onClick={() => navigate(`/database?id=${job.document_id}`)}
              className="flex-1 flex items-center justify-center gap-2 bg-indigo-500 hover:bg-indigo-600 text-white rounded-lg py-2.5 text-sm font-medium transition-colors"
            >
              <ExternalLink size={15} />
              View in Database
            </button>
            <button
              onClick={reset}
              className="flex-1 bg-[#242840] hover:bg-[#2e3250] text-slate-300 rounded-lg py-2.5 text-sm transition-colors"
            >
              Process Another
            </button>
          </div>
        </div>
      )}
    </div>
  );
}