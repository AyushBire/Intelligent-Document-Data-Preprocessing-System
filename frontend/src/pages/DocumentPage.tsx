import { useState } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  ArrowLeft,
  Download,
  Pencil,
  RotateCw,
  Trash2,
  ZoomIn,
  ZoomOut,
} from "lucide-react";
import { deleteDocument, getDocument, updateDocument } from "../api/documents";
import {
  CopyButton,
  EmptyState,
  ErrorState,
  Loading,
  Modal,
  PageHeader,
} from "../components/ui";
import { dateLabel, download, toCsv, valueLabel } from "../lib/utils";
import type { DocumentResponse, DocumentUpdate } from "../types";

const tabs = [
  "Overview",
  "Extracted data",
  "JSON",
  "Summary",
  "Source document",
  "Raw OCR",
];

/** Edit data while retaining invalid intermediate JSON.
 * @param props Document, callbacks and request state. @returns Editor. @throws None.
 */
function DocumentEditor({
  doc,
  save,
  cancel,
  pending,
  error,
}: {
  doc: DocumentResponse;
  save: (body: DocumentUpdate) => void;
  cancel: () => void;
  pending: boolean;
  error: unknown;
}) {
  const [type, setType] = useState(doc.document_type);
  const [report, setReport] = useState(doc.report);
  const [raw, setRaw] = useState(JSON.stringify(doc.structured_data, null, 2));
  const [mode, setMode] = useState("fields");
  const [fields, setFields] = useState(doc.structured_data);
  const [invalid, setInvalid] = useState("");
  /** Validate and submit. @returns Nothing. @throws None; parse errors render inline. */
  function submit() {
    try {
      const parsed: unknown = mode === "json" ? JSON.parse(raw) : fields;
      if (!parsed || Array.isArray(parsed) || typeof parsed !== "object")
        throw new Error("JSON must be an object of field names and values.");
      if (!type.trim()) throw new Error("Document type is required.");
      setInvalid("");
      save({
        document_type: type.trim(),
        report,
        structured_data: parsed as Record<string, unknown>,
      });
    } catch (failure) {
      setInvalid(failure instanceof Error ? failure.message : "Invalid JSON");
    }
  }
  /** Switch to fields after validating the JSON draft. @returns Nothing. @throws None. */
  function showFields() {
    if (mode !== "json") return;
    try {
      const parsed: unknown = JSON.parse(raw);
      if (!parsed || Array.isArray(parsed) || typeof parsed !== "object")
        throw new Error("JSON must be an object");
      setFields(parsed as Record<string, unknown>);
      setMode("fields");
      setInvalid("");
    } catch {
      setInvalid("Fix the JSON before switching to fields.");
    }
  }
  return (
    <Modal title="Edit document" onClose={() => !pending && cancel()}>
      <div className="editor">
        <label>
          Document type
          <input
            value={type}
            onChange={(event) => setType(event.target.value)}
          />
        </label>
        <div className="actions">
          <button className="button secondary" onClick={showFields}>
            Fields
          </button>
          <button
            className="button secondary"
            onClick={() => {
              if (mode === "fields") setRaw(JSON.stringify(fields, null, 2));
              setMode("json");
            }}
          >
            JSON editor
          </button>
        </div>
        {mode === "json" ? (
          <label>
            Structured data
            <textarea
              className="code-editor"
              rows={12}
              value={raw}
              onChange={(event) => setRaw(event.target.value)}
              spellCheck={false}
            />
          </label>
        ) : (
          Object.entries(fields).map(([key, value]) => (
            <label key={key}>
              {key.replaceAll("_", " ")}
              {typeof value === "object" && value !== null ? (
                <>
                  <pre>{valueLabel(value)}</pre>
                  <small>Edit nested values in the JSON editor.</small>
                </>
              ) : typeof value === "boolean" ? (
                <select
                  value={String(value)}
                  onChange={(event) =>
                    setFields({
                      ...fields,
                      [key]: event.target.value === "true",
                    })
                  }
                >
                  <option value="true">true</option>
                  <option value="false">false</option>
                </select>
              ) : (
                <input
                  value={value == null ? "" : String(value)}
                  type={typeof value === "number" ? "number" : "text"}
                  onChange={(event) =>
                    setFields({
                      ...fields,
                      [key]:
                        typeof value === "number"
                          ? event.target.value === ""
                            ? null
                            : Number(event.target.value)
                          : event.target.value === "" && value === null
                            ? null
                            : event.target.value,
                    })
                  }
                />
              )}
            </label>
          ))
        )}
        <label>
          Summary
          <textarea
            rows={5}
            value={report}
            onChange={(event) => setReport(event.target.value)}
          />
        </label>
        {invalid && <ErrorState error={new Error(invalid)} />}
        {error != null && <ErrorState error={error} />}
        <div className="actions">
          <button
            className="button secondary"
            disabled={pending}
            onClick={cancel}
          >
            Cancel
          </button>
          <button className="button" disabled={pending} onClick={submit}>
            {pending ? "Saving…" : "Save changes"}
          </button>
        </div>
      </div>
    </Modal>
  );
}

/** View source with local zoom and rotation.
 * @param props Record id. @returns Source viewer. @throws None.
 */
function SourceViewer({ id }: { id: number }) {
  const [angle, setAngle] = useState(0);
  const [zoom, setZoom] = useState(1);
  const [failed, setFailed] = useState(false);
  return (
    <>
      <div className="source-toolbar">
        <button
          className="button secondary"
          onClick={() => setAngle(angle + 90)}
        >
          <RotateCw size={16} />
          Rotate
        </button>
        <button
          className="icon-button"
          aria-label="Zoom out"
          disabled={zoom <= 0.5}
          onClick={() => setZoom(zoom - 0.25)}
        >
          <ZoomOut size={18} />
        </button>
        <span>{Math.round(zoom * 100)}%</span>
        <button
          className="icon-button"
          aria-label="Zoom in"
          disabled={zoom >= 3}
          onClick={() => setZoom(zoom + 0.25)}
        >
          <ZoomIn size={18} />
        </button>
        <a
          className="button secondary"
          href={`/api/documents/${id}/file`}
          target="_blank"
          rel="noreferrer"
        >
          Open original
        </a>
      </div>
      {failed ? (
        <EmptyState title="Source preview unavailable">
          <p>
            The source may be missing, or its format may not be supported by
            this browser.
          </p>
        </EmptyState>
      ) : (
        <div className="source-canvas">
          <img
            src={`/api/documents/${id}/file`}
            alt="Original document"
            style={{ transform: `rotate(${angle}deg) scale(${zoom})` }}
            onError={() => setFailed(true)}
          />
        </div>
      )}
      <p className="muted">Zoom and rotation change only this preview.</p>
    </>
  );
}

/** Render results, edits, source and exports.
 * @returns Document results. @throws None; request failures render inline.
 */
export default function DocumentPage() {
  const { id } = useParams();
  const number = Number(id);
  const navigate = useNavigate();
  const cache = useQueryClient();
  const [tab, setTab] = useState(0);
  const [editing, setEditing] = useState(false);
  const [deleting, setDeleting] = useState(false);
  const [saved, setSaved] = useState(false);
  const result = useQuery({
    queryKey: ["document", number],
    queryFn: () => getDocument(number),
    enabled: Number.isInteger(number) && number > 0,
  });
  const edit = useMutation({
    mutationFn: (body: DocumentUpdate) => updateDocument(number, body),
    onSuccess: (doc) => {
      cache.setQueryData(["document", number], doc);
      void cache.invalidateQueries({ queryKey: ["documents"] });
      void cache.invalidateQueries({ queryKey: ["stats"] });
      void cache.invalidateQueries({ queryKey: ["types"] });
      setEditing(false);
      setSaved(true);
    },
  });
  const remove = useMutation({
    mutationFn: () => deleteDocument(number),
    onSuccess: () => {
      void cache.invalidateQueries({ queryKey: ["documents"] });
      void cache.invalidateQueries({ queryKey: ["stats"] });
      void cache.invalidateQueries({ queryKey: ["types"] });
      cache.removeQueries({ queryKey: ["document", number] });
      navigate("/documents");
    },
  });
  if (!Number.isInteger(number) || number <= 0)
    return (
      <EmptyState title="Invalid document identifier">
        <Link to="/documents">Back to library</Link>
      </EmptyState>
    );
  if (result.isPending) return <Loading />;
  if (result.isError)
    return (
      <ErrorState error={result.error} retry={() => void result.refetch()} />
    );
  const doc = result.data;
  const json = JSON.stringify(doc.structured_data, null, 2);
  return (
    <>
      <Link className="back-link" to="/documents">
        <ArrowLeft size={16} />
        Document library
      </Link>
      <PageHeader
        title={doc.filename}
        subtitle={`Document #${doc.id} · ${dateLabel(doc.created_at)}`}
        actions={
          <>
            <button
              className="button secondary"
              onClick={() => {
                edit.reset();
                setSaved(false);
                setEditing(true);
              }}
            >
              <Pencil size={16} />
              Edit
            </button>
            <button
              className="icon-button"
              aria-label="Delete document"
              onClick={() => {
                remove.reset();
                setDeleting(true);
              }}
            >
              <Trash2 size={18} />
            </button>
            <Link className="button" to="/extract">
              New extraction
            </Link>
          </>
        }
      />
      {saved && (
        <div className="success-box" role="status">
          Changes saved.
        </div>
      )}
      <div className="results-meta">
        <span className="badge">{doc.document_type.replaceAll("_", " ")}</span>
        <span>{Object.keys(doc.structured_data).length} extracted fields</span>
        <span>Updated {dateLabel(doc.updated_at)}</span>
      </div>
      <section className="panel results-panel">
        <div role="tablist" aria-label="Document results" className="tabs">
          {tabs.map((label, index) => (
            <button
              role="tab"
              aria-selected={tab === index}
              tabIndex={tab === index ? 0 : -1}
              id={`tab-${index}`}
              aria-controls="result-panel"
              key={label}
              onClick={() => setTab(index)}
              onKeyDown={(event) => {
                let next = index;
                if (event.key === "ArrowRight")
                  next = (index + 1) % tabs.length;
                else if (event.key === "ArrowLeft")
                  next = (index + tabs.length - 1) % tabs.length;
                else if (event.key === "Home") next = 0;
                else if (event.key === "End") next = tabs.length - 1;
                else return;
                event.preventDefault();
                setTab(next);
                document.getElementById(`tab-${next}`)?.focus();
              }}
            >
              {label}
            </button>
          ))}
        </div>
        <div
          id="result-panel"
          role="tabpanel"
          aria-labelledby={`tab-${tab}`}
          className="result-body"
        >
          {tab === 0 && (
            <div className="overview-grid">
              <div>
                <span className="eyebrow">EXTRACTION COMPLETE</span>
                <h2>Your document, organized.</h2>
                <p className="summary-text">
                  {doc.report || "No summary was returned."}
                </p>
                <div className="review-note">
                  AI-generated values can contain errors. Compare key
                  information with the source before using it.
                </div>
              </div>
              <div className="overview-fields">
                <h3>At a glance</h3>
                {Object.entries(doc.structured_data)
                  .slice(0, 6)
                  .map(([key, value]) => (
                    <div key={key}>
                      <span>{key.replaceAll("_", " ")}</span>
                      <strong>{valueLabel(value)}</strong>
                    </div>
                  ))}
                <button className="text-link" onClick={() => setTab(1)}>
                  View all extracted fields →
                </button>
              </div>
            </div>
          )}
          {tab === 1 && (
            <>
              <div className="panel-heading">
                <h2>Extracted fields</h2>
                <button
                  className="button secondary"
                  onClick={() => {
                    edit.reset();
                    setEditing(true);
                  }}
                >
                  Edit fields
                </button>
              </div>
              {Object.keys(doc.structured_data).length ? (
                <div className="field-list">
                  {Object.entries(doc.structured_data).map(([key, value]) => (
                    <div key={key}>
                      <span>{key.replaceAll("_", " ")}</span>
                      <pre>{valueLabel(value)}</pre>
                      <CopyButton
                        text={valueLabel(value)}
                        label={`Copy ${key.replaceAll("_", " ")}`}
                      />
                    </div>
                  ))}
                </div>
              ) : (
                <EmptyState title="No extracted fields" />
              )}
            </>
          )}
          {tab === 2 && (
            <>
              <div className="panel-heading">
                <h2>Structured JSON</h2>
                <CopyButton text={json} />
              </div>
              <pre className="json-view">{json}</pre>
            </>
          )}
          {tab === 3 && (
            <>
              <div className="panel-heading">
                <h2>Document summary</h2>
                <CopyButton text={doc.report} />
              </div>
              <p className="summary-text">
                {doc.report || "No summary available."}
              </p>
            </>
          )}
          {tab === 4 && <SourceViewer id={doc.id} />}
          {tab === 5 && (
            <>
              <div className="panel-heading">
                <h2>Original OCR text</h2>
                <CopyButton text={doc.ocr_text} />
              </div>
              <pre className="ocr-text">
                {doc.ocr_text || "No OCR text available."}
              </pre>
            </>
          )}
        </div>
        <div className="export-bar">
          <span>
            <Download size={17} />
            Download results
          </span>
          <div className="actions">
            <button
              className="button secondary compact"
              onClick={() =>
                download(
                  `${doc.filename}_extracted.json`,
                  json,
                  "application/json",
                )
              }
            >
              JSON
            </button>
            <button
              className="button secondary compact"
              onClick={() =>
                download(
                  `${doc.filename}_fields.csv`,
                  toCsv(doc.structured_data),
                  "text/csv;charset=utf-8",
                )
              }
            >
              CSV
            </button>
            <button
              className="button secondary compact"
              onClick={() => download(`${doc.filename}_report.txt`, doc.report)}
            >
              Summary TXT
            </button>
            <button
              className="button secondary compact"
              onClick={() => download(`${doc.filename}_ocr.txt`, doc.ocr_text)}
            >
              OCR TXT
            </button>
          </div>
        </div>
      </section>
      {editing && (
        <DocumentEditor
          doc={doc}
          save={(body) => edit.mutate(body)}
          cancel={() => setEditing(false)}
          pending={edit.isPending}
          error={edit.error}
        />
      )}
      {deleting && (
        <Modal
          title="Delete this document?"
          onClose={() => !remove.isPending && setDeleting(false)}
        >
          <p>
            The record and source image will be permanently deleted. This cannot
            be undone.
          </p>
          {remove.isError && <ErrorState error={remove.error} />}
          <div className="actions">
            <button
              className="button secondary"
              disabled={remove.isPending}
              onClick={() => setDeleting(false)}
            >
              Cancel
            </button>
            <button
              className="button danger"
              disabled={remove.isPending}
              onClick={() => remove.mutate()}
            >
              {remove.isPending ? "Deleting…" : "Delete document"}
            </button>
          </div>
        </Modal>
      )}
    </>
  );
}
