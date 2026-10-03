import { useEffect, useRef, useState } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import {
  listDocuments,
  getDocument,
  updateDocument,
  deleteDocument,
  getDocumentTypes,
} from "../api/documents";
import type { DocumentResponse, DocumentUpdate } from "../types";
import { Search, Trash2, Pencil, Eye, X, Save, ChevronDown, Download, FileJson, FileText } from "lucide-react";
import StatusBadge from "../components/StatusBadge";

function Section({
  title,
  id,
  children,
}: {
  title: string;
  id: string;
  children: React.ReactNode;
}) {
  return (
    <section aria-labelledby={id} className="space-y-2">
      <h2 id={id} className="text-xs font-semibold text-slate-500 uppercase tracking-wider">
        {title}
      </h2>
      {children}
    </section>
  );
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

export default function DatabasePage() {
  const qc = useQueryClient();
  const [search, setSearch] = useState("");
  const [typeFilter, setTypeFilter] = useState("");
  const [selectedDoc, setSelectedDoc] = useState<DocumentResponse | null>(null);
  const [editMode, setEditMode] = useState(false);
  const [editData, setEditData] = useState<DocumentUpdate>({});
  const [deleteConfirm, setDeleteConfirm] = useState<number | null>(null);
  const cancelDeleteRef = useRef<HTMLButtonElement>(null);

  const { data: types = [] } = useQuery({ queryKey: ["types"], queryFn: getDocumentTypes });
  const { data: docs = [], isLoading } = useQuery({
    queryKey: ["documents", search, typeFilter],
    queryFn: () =>
      listDocuments({
        search: search || undefined,
        document_type: typeFilter || undefined,
      }),
  });

  const viewMut = useMutation({
    mutationFn: (id: number) => getDocument(id),
    onSuccess: (doc) => {
      setSelectedDoc(doc);
      setEditMode(false);
    },
  });

  const updateMut = useMutation({
    mutationFn: ({ id, data }: { id: number; data: DocumentUpdate }) => updateDocument(id, data),
    onSuccess: (doc) => {
      setSelectedDoc(doc);
      setEditMode(false);
      qc.invalidateQueries({ queryKey: ["documents"] });
    },
  });

  const deleteMut = useMutation({
    mutationFn: deleteDocument,
    onSuccess: () => {
      setDeleteConfirm(null);
      setSelectedDoc(null);
      qc.invalidateQueries({ queryKey: ["documents"] });
      qc.invalidateQueries({ queryKey: ["stats"] });
    },
  });

  useEffect(() => {
    if (deleteConfirm !== null) {
      cancelDeleteRef.current?.focus();
      const onKeyDown = (e: KeyboardEvent) => {
        if (e.key === "Escape") setDeleteConfirm(null);
      };
      document.addEventListener("keydown", onKeyDown);
      return () => document.removeEventListener("keydown", onKeyDown);
    }
  }, [deleteConfirm]);

  const startEdit = () => {
    if (!selectedDoc) return;
    setEditData({
      document_type: selectedDoc.document_type,
      report: selectedDoc.report,
      structured_data: selectedDoc.structured_data,
    });
    setEditMode(true);
  };

  const saveEdit = () => {
    if (!selectedDoc) return;
    updateMut.mutate({ id: selectedDoc.id, data: editData });
  };

  const handleDownloadJson = () => {
    if (!selectedDoc) return;
    downloadBlob(
      JSON.stringify(selectedDoc.structured_data, null, 2),
      `${baseName(selectedDoc.filename)}_extracted.json`,
      "application/json"
    );
  };

  const handleDownloadReport = () => {
    if (!selectedDoc?.report) return;
    downloadBlob(
      selectedDoc.report,
      `${baseName(selectedDoc.filename)}_report.txt`,
      "text/plain"
    );
  };

  return (
    <div className="flex h-screen overflow-hidden">
      {/* Left panel — list */}
      <nav aria-label="Document list" className="w-96 border-r border-[#2e3250] flex flex-col">
        <div className="p-4 border-b border-[#2e3250] space-y-3">
          <h1 className="text-lg font-bold text-white">Database</h1>

          <div className="relative">
            <label htmlFor="doc-search" className="sr-only">
              Search documents by filename, type, or OCR text
            </label>
            <Search
              size={14}
              className="absolute left-3 top-1/2 -translate-y-1/2 text-slate-500"
              aria-hidden="true"
            />
            <input
              id="doc-search"
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              placeholder="Search documents..."
              className="w-full bg-[#1c2036] border border-[#2e3250] rounded-lg pl-8 pr-3 py-2 text-sm text-slate-200 placeholder-slate-500 focus:outline-none focus-visible:ring-2 focus-visible:ring-indigo-400 focus:border-indigo-500"
            />
          </div>

          <div className="relative">
            <label htmlFor="doc-type-filter" className="sr-only">
              Filter by document type
            </label>
            <select
              id="doc-type-filter"
              value={typeFilter}
              onChange={(e) => setTypeFilter(e.target.value)}
              className="w-full appearance-none bg-[#1c2036] border border-[#2e3250] rounded-lg px-3 py-2 text-sm text-slate-200 focus:outline-none focus-visible:ring-2 focus-visible:ring-indigo-400 focus:border-indigo-500"
            >
              <option value="">All types</option>
              {types.map((t) => (
                <option key={t} value={t}>
                  {t.replace(/_/g, " ")}
                </option>
              ))}
            </select>
            <ChevronDown
              size={13}
              className="absolute right-3 top-1/2 -translate-y-1/2 text-slate-500 pointer-events-none"
              aria-hidden="true"
            />
          </div>

          <p className="sr-only" role="status" aria-live="polite">
            {isLoading
              ? "Loading documents"
              : `${docs.length} document${docs.length === 1 ? "" : "s"} found`}
          </p>
        </div>

        <div className="flex-1 overflow-y-auto">
          {isLoading ? (
            <div className="p-4 text-slate-500 text-sm">Loading…</div>
          ) : docs.length === 0 ? (
            <div className="p-4 text-slate-500 text-sm">
              No documents found. Try a different search or filter.
            </div>
          ) : (
            <ul role="list">
              {docs.map((doc) => {
                const isSelected = selectedDoc?.id === doc.id;
                return (
                  <li key={doc.id}>
                    <button
                      onClick={() => viewMut.mutate(doc.id)}
                      aria-current={isSelected ? "true" : undefined}
                      className={`w-full text-left px-4 py-3 border-b border-[#2e3250] hover:bg-[#1c2036] transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-inset focus-visible:ring-indigo-400 ${
                        isSelected ? "bg-[#1c2036] border-l-2 border-l-indigo-500" : ""
                      }`}
                    >
                      <p className="text-slate-200 text-sm font-medium truncate">{doc.filename}</p>
                      <div className="flex items-center justify-between mt-1">
                        <StatusBadge value={doc.document_type} />
                        <span className="text-slate-500 text-xs tabular-nums">
                          {new Date(doc.created_at).toLocaleDateString()}
                        </span>
                      </div>
                    </button>
                  </li>
                );
              })}
            </ul>
          )}
        </div>
      </nav>

      {/* Right panel — detail */}
      <main className="flex-1 overflow-y-auto">
        {!selectedDoc ? (
          <div className="h-full flex items-center justify-center text-slate-600">
            <div className="text-center">
              <Eye size={36} className="mx-auto mb-3 opacity-30" aria-hidden="true" />
              <p className="text-sm">Select a document to view details</p>
            </div>
          </div>
        ) : (
          <div className="p-6 space-y-5">
            {/* Header */}
            <div className="flex items-start justify-between gap-4">
              <div className="min-w-0">
                <h1 className="text-white font-semibold text-lg truncate">
                  {selectedDoc.filename}
                </h1>
                <p className="text-slate-500 text-xs mt-0.5 tabular-nums">
                  ID #{selectedDoc.id} · {new Date(selectedDoc.created_at).toLocaleString()}
                </p>
              </div>
              <div className="flex gap-2 flex-shrink-0">
                {!editMode ? (
                  <>
                    <button
                      onClick={startEdit}
                      className="flex items-center gap-1.5 px-3 py-1.5 bg-[#1c2036] hover:bg-[#242840] text-slate-300 rounded-lg text-xs transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-indigo-400"
                    >
                      <Pencil size={13} aria-hidden="true" /> Edit
                    </button>
                    <button
                      onClick={() => setDeleteConfirm(selectedDoc.id)}
                      className="flex items-center gap-1.5 px-3 py-1.5 bg-red-500/10 hover:bg-red-500/20 text-red-400 rounded-lg text-xs transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-red-400"
                    >
                      <Trash2 size={13} aria-hidden="true" /> Delete
                    </button>
                  </>
                ) : (
                  <>
                    <button
                      onClick={saveEdit}
                      disabled={updateMut.isPending}
                      className="flex items-center gap-1.5 px-3 py-1.5 bg-indigo-500 hover:bg-indigo-600 text-white rounded-lg text-xs transition-colors disabled:opacity-50 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-indigo-300"
                    >
                      <Save size={13} aria-hidden="true" /> {updateMut.isPending ? "Saving…" : "Save"}
                    </button>
                    <button
                      onClick={() => setEditMode(false)}
                      className="flex items-center gap-1.5 px-3 py-1.5 bg-[#1c2036] hover:bg-[#242840] text-slate-300 rounded-lg text-xs transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-indigo-400"
                    >
                      <X size={13} aria-hidden="true" /> Cancel
                    </button>
                  </>
                )}
              </div>
            </div>

            {/* Download bar — always visible when not editing */}
            {!editMode && (
              <div className="flex gap-2 p-3 bg-[#1a1d2e] border border-[#2e3250] rounded-xl">
                <button
                  onClick={handleDownloadJson}
                  disabled={Object.keys(selectedDoc.structured_data).length === 0}
                  className="flex items-center gap-1.5 px-3 py-2 bg-teal-500/15 hover:bg-teal-500/25 disabled:opacity-40 disabled:cursor-not-allowed text-teal-300 rounded-lg text-xs font-medium transition-colors border border-teal-500/30 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-teal-400"
                >
                  <FileJson size={13} aria-hidden="true" /> Download JSON
                </button>
                <button
                  onClick={handleDownloadReport}
                  disabled={!selectedDoc.report}
                  className="flex items-center gap-1.5 px-3 py-2 bg-[#242840] hover:bg-[#2e3250] disabled:opacity-40 disabled:cursor-not-allowed text-slate-300 rounded-lg text-xs transition-colors border border-[#2e3250] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-indigo-400"
                >
                  <Download size={13} aria-hidden="true" /><FileText size={13} aria-hidden="true" /> Download report
                </button>
              </div>
            )}

            <Section id="doc-type-heading" title="Document type">
              {editMode ? (
                <>
                  <label htmlFor="edit-doc-type" className="sr-only">
                    Document type
                  </label>
                  <input
                    id="edit-doc-type"
                    value={editData.document_type ?? ""}
                    onChange={(e) => setEditData({ ...editData, document_type: e.target.value })}
                    className="bg-[#1c2036] border border-[#2e3250] rounded-lg px-3 py-2 text-sm text-slate-200 focus:outline-none focus-visible:ring-2 focus-visible:ring-indigo-400 w-full"
                  />
                </>
              ) : (
                <StatusBadge value={selectedDoc.document_type} />
              )}
            </Section>

            <Section id="fields-heading" title="Extracted fields">
              {editMode ? (
                <>
                  <label htmlFor="edit-structured-data" className="sr-only">
                    Extracted fields as JSON
                  </label>
                  <textarea
                    id="edit-structured-data"
                    rows={10}
                    value={JSON.stringify(editData.structured_data ?? {}, null, 2)}
                    onChange={(e) => {
                      try {
                        setEditData({ ...editData, structured_data: JSON.parse(e.target.value) });
                      } catch {
                        /* invalid JSON while typing */
                      }
                    }}
                    className="w-full bg-[#1c2036] border border-[#2e3250] rounded-lg px-3 py-2 text-xs font-mono text-slate-200 focus:outline-none focus-visible:ring-2 focus-visible:ring-indigo-400 resize-none"
                  />
                </>
              ) : Object.keys(selectedDoc.structured_data).length === 0 ? (
                <p className="text-slate-500 text-sm">No fields were extracted for this document.</p>
              ) : (
                <dl className="grid grid-cols-2 gap-2">
                  {Object.entries(selectedDoc.structured_data).map(([k, v]) => (
                    <div key={k} className="bg-[#1c2036] rounded-lg p-3">
                      <dt className="text-slate-500 text-xs capitalize">{k.replace(/_/g, " ")}</dt>
                      <dd className="text-slate-200 text-sm mt-0.5 truncate">
                        {String(v ?? "—")}
                      </dd>
                    </div>
                  ))}
                </dl>
              )}
            </Section>

            <Section id="report-heading" title="Report">
              {editMode ? (
                <>
                  <label htmlFor="edit-report" className="sr-only">
                    Report
                  </label>
                  <textarea
                    id="edit-report"
                    rows={5}
                    value={editData.report ?? ""}
                    onChange={(e) => setEditData({ ...editData, report: e.target.value })}
                    className="w-full bg-[#1c2036] border border-[#2e3250] rounded-lg px-3 py-2 text-sm text-slate-200 focus:outline-none focus-visible:ring-2 focus-visible:ring-indigo-400 resize-none"
                  />
                </>
              ) : (
                <p className="text-slate-300 text-sm leading-relaxed whitespace-pre-wrap">
                  {selectedDoc.report || "No report generated."}
                </p>
              )}
            </Section>

            <Section id="ocr-heading" title="Raw OCR text">
              <pre className="text-slate-400 text-xs leading-relaxed whitespace-pre-wrap bg-[#1c2036] rounded-lg p-3 max-h-48 overflow-y-auto">
                {selectedDoc.ocr_text || "No OCR text."}
              </pre>
            </Section>
          </div>
        )}
      </main>

      {/* Delete confirm modal */}
      {deleteConfirm !== null && (
        <div className="fixed inset-0 bg-black/60 flex items-center justify-center z-50">
          <div
            role="dialog"
            aria-modal="true"
            aria-labelledby="delete-dialog-title"
            aria-describedby="delete-dialog-desc"
            className="bg-[#141726] border border-[#2e3250] rounded-xl p-6 w-80 space-y-4"
          >
            <p id="delete-dialog-title" className="text-white font-semibold">
              Delete document?
            </p>
            <p id="delete-dialog-desc" className="text-slate-400 text-sm">
              This action cannot be undone.
            </p>
            <div className="flex gap-3">
              <button
                onClick={() => deleteMut.mutate(deleteConfirm)}
                disabled={deleteMut.isPending}
                className="flex-1 bg-red-500 hover:bg-red-600 text-white rounded-lg py-2 text-sm font-medium transition-colors disabled:opacity-50 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-red-300"
              >
                {deleteMut.isPending ? "Deleting…" : "Delete"}
              </button>
              <button
                ref={cancelDeleteRef}
                onClick={() => setDeleteConfirm(null)}
                className="flex-1 bg-[#1c2036] hover:bg-[#242840] text-slate-300 rounded-lg py-2 text-sm transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-indigo-400"
              >
                Cancel
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}