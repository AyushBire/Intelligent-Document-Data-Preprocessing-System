import { useEffect, useRef, useState } from "react";
import { useNavigate } from "react-router-dom";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import {
  ArrowRight,
  Check,
  FileImage,
  ScanLine,
  UploadCloud,
  X,
} from "lucide-react";
import { uploadDocument } from "../api/documents";
import { ErrorState, PageHeader } from "../components/ui";
import { readActiveJob, saveActiveJob, useJob } from "../hooks/useJob";

const stages = [
  ["preprocessing", "Prepare image"],
  ["ocr", "Read document"],
  ["llm", "Extract information"],
  ["saving", "Save results"],
];

/** Render file selection, preview and resumable extraction.
 * @returns Extraction workflow. @throws None; failures render recovery controls.
 */
export default function ExtractPage() {
  const [file, setFile] = useState<File | null>(null);
  const [preview, setPreview] = useState("");
  const [previewError, setPreviewError] = useState(false);
  const [validation, setValidation] = useState("");
  const [dragging, setDragging] = useState(false);
  const [active, setActive] = useState(readActiveJob);
  const input = useRef<HTMLInputElement>(null);
  const navigate = useNavigate();
  const cache = useQueryClient();
  const job = useJob(active?.job_id);
  const upload = useMutation({
    mutationFn: uploadDocument,
    onSuccess: (value) => {
      setActive(value);
      saveActiveJob(value);
    },
  });
  const busy =
    upload.isPending ||
    (!!active && !job.isError && job.data?.status !== "error");

  /** Validate and select an image. @param candidate File. @returns Nothing. @throws None. */
  function select(candidate?: File) {
    if (!candidate || busy) return;
    if (
      !/\.(jpe?g|png|bmp|tiff?)$/i.test(candidate.name) &&
      !["image/jpeg", "image/png", "image/bmp", "image/tiff"].includes(
        candidate.type,
      )
    ) {
      setValidation(
        "Choose a JPG, PNG, BMP or TIFF image. PDF is not supported.",
      );
      return;
    }
    if (candidate.size > 20 * 1024 * 1024 || candidate.size === 0) {
      setValidation("Choose a nonempty image up to 20 MB.");
      return;
    }
    setPreview(URL.createObjectURL(candidate));
    setFile(candidate);
    setValidation("");
    setPreviewError(false);
    upload.reset();
  }
  useEffect(
    () => () => {
      if (preview) URL.revokeObjectURL(preview);
    },
    [preview],
  );
  useEffect(() => {
    /** Select a pasted image. @param event Clipboard event. @returns Nothing. @throws None. */
    function paste(event: ClipboardEvent) {
      if (
        event.target instanceof HTMLInputElement ||
        event.target instanceof HTMLTextAreaElement ||
        busy
      )
        return;
      const pasted = event.clipboardData?.files[0];
      if (pasted) {
        event.preventDefault();
        select(pasted);
      }
    }
    window.addEventListener("paste", paste);
    return () => window.removeEventListener("paste", paste);
  });
  useEffect(() => {
    if (job.data?.status === "done" && job.data.document_id) {
      saveActiveJob(null);
      void cache.invalidateQueries({ queryKey: ["documents"] });
      void cache.invalidateQueries({ queryKey: ["stats"] });
      navigate(`/documents/${job.data.document_id}`, { replace: true });
    }
  }, [job.data, cache, navigate]);

  /** Clear a failed or expired job. @returns Nothing. @throws None. */
  function reset() {
    setActive(null);
    saveActiveJob(null);
    upload.reset();
    setValidation("");
  }
  return (
    <>
      <PageHeader
        title="Extract a document"
        subtitle="From an image to structured information in a few simple steps."
      />
      <div className="workflow-steps">
        <span className={!active ? "current" : ""}>
          01 <b>Upload</b>
        </span>
        <i />
        <span className={active ? "current" : ""}>
          02 <b>Process</b>
        </span>
        <i />
        <span>
          03 <b>Review results</b>
        </span>
      </div>
      <div className="extraction-grid">
        <section className="panel upload-panel">
          <div className="panel-heading">
            <div>
              <h2>{active ? "Extraction in progress" : "Add your document"}</h2>
              <p>
                {active
                  ? active.filename
                  : "A clear, well-lit image gives the best results."}
              </p>
            </div>
            <span className="badge">IMAGE INPUT</span>
          </div>
          {active ? (
            <div className="processing" aria-live="polite">
              <span className="processing-icon">
                <ScanLine size={32} />
              </span>
              <h2>
                {job.isError
                  ? "Job unavailable"
                  : job.data?.status === "error"
                    ? "Processing failed"
                    : job.data?.status === "pending"
                      ? "Waiting to process"
                      : "Turning your document into data"}
              </h2>
              <p>
                Progress is reported by the IDPS pipeline. Larger documents may
                take several minutes.
              </p>
              <progress
                max={100}
                value={job.data?.progress ?? 0}
                aria-label="Extraction progress"
              />
              <div className="processing-stages">
                {stages.map(([key, label], index) => (
                  <div
                    className={
                      stages.findIndex(
                        ([value]) => value === job.data?.stage,
                      ) >= index
                        ? "complete"
                        : ""
                    }
                    key={key}
                  >
                    <span>
                      {job.data &&
                      job.data.progress > [10, 30, 60, 85][index]! ? (
                        <Check size={14} />
                      ) : (
                        index + 1
                      )}
                    </span>
                    {label}
                  </div>
                ))}
              </div>
              {job.isError && <ErrorState error={job.error} />}
              {job.data?.status === "error" && (
                <ErrorState
                  error={new Error(job.data.error ?? "Processing failed")}
                />
              )}
              {(job.isError || job.data?.status === "error") && (
                <button className="button" onClick={reset}>
                  Choose another file
                </button>
              )}
            </div>
          ) : (
            <>
              <input
                ref={input}
                type="file"
                accept=".jpg,.jpeg,.png,.bmp,.tif,.tiff"
                className="sr-only"
                aria-label="Choose document image"
                onChange={(event) => {
                  select(event.target.files?.[0]);
                  event.target.value = "";
                }}
              />
              {file ? (
                <div className="selected-file">
                  <div className="preview-frame">
                    {previewError ? (
                      <p>
                        Preview unavailable in this browser. The image can still
                        be processed.
                      </p>
                    ) : (
                      <img
                        src={preview}
                        alt="Selected document preview"
                        onError={() => setPreviewError(true)}
                      />
                    )}
                  </div>
                  <div className="file-meta">
                    <FileImage size={22} />
                    <div>
                      <strong>{file.name}</strong>
                      <small>{(file.size / 1024 / 1024).toFixed(2)} MB</small>
                    </div>
                    <button
                      className="icon-button"
                      aria-label="Remove selected file"
                      disabled={busy}
                      onClick={() => {
                        setFile(null);
                        setPreview("");
                      }}
                    >
                      <X />
                    </button>
                  </div>
                </div>
              ) : (
                <button
                  type="button"
                  disabled={busy}
                  className={`dropzone ${dragging ? "dragging" : ""}`}
                  onClick={() => input.current?.click()}
                  onDragOver={(event) => {
                    event.preventDefault();
                    setDragging(true);
                  }}
                  onDragLeave={() => setDragging(false)}
                  onDrop={(event) => {
                    event.preventDefault();
                    setDragging(false);
                    select(event.dataTransfer.files[0]);
                  }}
                >
                  <span className="upload-icon">
                    <UploadCloud size={30} />
                  </span>
                  <strong>Drop your document here</strong>
                  <span>
                    or <b>browse files</b> to upload
                  </span>
                  <small>You can also paste an image from your clipboard</small>
                  <span className="format-tags">
                    <span>JPG</span>
                    <span>PNG</span>
                    <span>BMP</span>
                    <span>TIFF</span>
                  </span>
                  <small>Maximum file size: 20 MB</small>
                </button>
              )}
              {validation && <ErrorState error={new Error(validation)} />}
              {upload.isError && <ErrorState error={upload.error} />}
              <div className="upload-actions">
                <span>One document at a time</span>
                <button
                  className="button"
                  disabled={!file || busy}
                  onClick={() => file && upload.mutate(file)}
                >
                  {upload.isPending ? "Uploading…" : "Extract information"}
                  <ArrowRight size={17} />
                </button>
              </div>
            </>
          )}
          <p className="privacy-note">
            Files are stored in your workspace. Extracted text is sent to Gemini
            for AI processing. Upload only documents you are authorized to
            process.
          </p>
        </section>
        <aside className="extraction-aside">
          <article className="panel">
            <span className="eyebrow">HOW IT WORKS</span>
            <h2>
              One document.
              <br />A clearer picture.
            </h2>
            {[
              [
                "01",
                "Upload your image",
                "Invoices, receipts, identity documents and more.",
              ],
              [
                "02",
                "Let IDPS do the reading",
                "OCR reads the text. AI organizes the fields and creates a summary.",
              ],
              [
                "03",
                "Review and export",
                "Check the extracted values, make edits and download your results.",
              ],
            ].map(([number, title, text]) => (
              <div className="how-step" key={number}>
                <span>{number}</span>
                <div>
                  <h3>{title}</h3>
                  <p>{text}</p>
                </div>
              </div>
            ))}
          </article>
          <div className="tip-card">
            <h3>Make every detail count</h3>
            <p>
              Keep the full page in frame, avoid shadows, and use a sharp image
              with readable text.
            </p>
          </div>
        </aside>
      </div>
    </>
  );
}
