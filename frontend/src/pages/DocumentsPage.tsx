import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  ArrowUpRight,
  ChevronLeft,
  ChevronRight,
  Search,
  Trash2,
  Upload,
} from "lucide-react";
import {
  bulkDeleteDocuments,
  getDocumentPage,
  getDocumentTypes,
} from "../api/documents";
import {
  EmptyState,
  ErrorState,
  Loading,
  Modal,
  PageHeader,
} from "../components/ui";
import { dateLabel } from "../lib/utils";

/** Render paginated history and confirmed bulk deletion. @returns Library. @throws None. */
export default function DocumentsPage() {
  const [search, setSearch] = useState("");
  const [query, setQuery] = useState("");
  const [type, setType] = useState("");
  const [page, setPage] = useState(0);
  const [selected, setSelected] = useState<number[]>([]);
  const [confirm, setConfirm] = useState(false);
  const cache = useQueryClient();
  const size = 20;
  useEffect(() => {
    const timer = window.setTimeout(() => {
      setQuery(search);
      setPage(0);
      setSelected([]);
    }, 300);
    return () => window.clearTimeout(timer);
  }, [search]);
  const documents = useQuery({
    queryKey: ["documents", "history", query, type, page],
    queryFn: () =>
      getDocumentPage({
        search: query || undefined,
        document_type: type || undefined,
        limit: size,
        offset: page * size,
      }),
  });
  const types = useQuery({ queryKey: ["types"], queryFn: getDocumentTypes });
  const remove = useMutation({
    mutationFn: bulkDeleteDocuments,
    onSuccess: () => {
      setConfirm(false);
      setSelected([]);
      setPage(0);
      void cache.invalidateQueries({ queryKey: ["documents"] });
      void cache.invalidateQueries({ queryKey: ["stats"] });
      void cache.invalidateQueries({ queryKey: ["types"] });
    },
  });
  /** Toggle selection. @param id Document id. @returns Nothing. @throws None. */
  function toggle(id: number) {
    setSelected((values) =>
      values.includes(id)
        ? values.filter((value) => value !== id)
        : [...values, id],
    );
  }
  return (
    <>
      <PageHeader
        title="Document library"
        subtitle="Find, review and manage all your extracted documents."
        actions={
          <Link to="/extract" className="button">
            <Upload size={17} />
            New extraction
          </Link>
        }
      />
      <section className="panel">
        <div className="library-toolbar">
          <label className="search-input">
            <Search size={18} />
            <input
              aria-label="Search documents"
              placeholder="Search filenames, types or document text…"
              value={search}
              onChange={(event) => setSearch(event.target.value)}
            />
          </label>
          <select
            aria-label="Filter document type"
            value={type}
            onChange={(event) => {
              setType(event.target.value);
              setPage(0);
              setSelected([]);
            }}
          >
            <option value="">All document types</option>
            {types.data?.map((value) => (
              <option key={value} value={value}>
                {value.replaceAll("_", " ")}
              </option>
            ))}
          </select>
          {selected.length > 0 && (
            <button
              className="button danger"
              onClick={() => {
                remove.reset();
                setConfirm(true);
              }}
            >
              <Trash2 size={16} />
              Delete ({selected.length})
            </button>
          )}
        </div>
        {types.isError && (
          <ErrorState error={types.error} retry={() => void types.refetch()} />
        )}
        {documents.isPending ? (
          <Loading />
        ) : documents.isError ? (
          <ErrorState
            error={documents.error}
            retry={() => void documents.refetch()}
          />
        ) : documents.data.items.length === 0 ? (
          <EmptyState
            title={
              query || type
                ? "No matching documents"
                : "Your library is ready for its first document"
            }
          >
            <p>
              {query || type
                ? "Try a different search or type filter."
                : "Start an extraction to save a document here."}
            </p>
            <Link to="/extract" className="button">
              Extract a document
            </Link>
          </EmptyState>
        ) : (
          <div className="table-wrap">
            <table className="document-table">
              <thead>
                <tr>
                  <th>
                    <input
                      type="checkbox"
                      aria-label="Select all documents on this page"
                      checked={documents.data.items.every((doc) =>
                        selected.includes(doc.id),
                      )}
                      onChange={(event) =>
                        setSelected(
                          event.target.checked
                            ? documents.data.items.map((doc) => doc.id)
                            : [],
                        )
                      }
                    />
                  </th>
                  <th>Document</th>
                  <th>Type</th>
                  <th>Created</th>
                  <th>
                    <span className="sr-only">Open</span>
                  </th>
                </tr>
              </thead>
              <tbody>
                {documents.data.items.map((doc) => (
                  <tr key={doc.id}>
                    <td>
                      <input
                        type="checkbox"
                        aria-label={`Select ${doc.filename}`}
                        checked={selected.includes(doc.id)}
                        onChange={() => toggle(doc.id)}
                      />
                    </td>
                    <td>
                      <Link
                        to={`/documents/${doc.id}`}
                        className="document-name"
                      >
                        {doc.filename}
                        <small>Document #{doc.id}</small>
                      </Link>
                    </td>
                    <td>
                      <span className="badge">
                        {doc.document_type.replaceAll("_", " ")}
                      </span>
                    </td>
                    <td>{dateLabel(doc.created_at)}</td>
                    <td>
                      <Link
                        className="icon-button"
                        aria-label={`Open ${doc.filename}`}
                        to={`/documents/${doc.id}`}
                      >
                        <ArrowUpRight size={18} />
                      </Link>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
        {documents.data && (
          <div className="pagination">
            <span>
              {documents.data.total === 0
                ? "0 documents"
                : `${page * size + 1}–${Math.min((page + 1) * size, documents.data.total)} of ${documents.data.total} documents`}
            </span>
            <div>
              <button
                className="icon-button"
                aria-label="Previous page"
                disabled={page === 0}
                onClick={() => {
                  setPage(page - 1);
                  setSelected([]);
                }}
              >
                <ChevronLeft size={18} />
              </button>
              <span>Page {page + 1}</span>
              <button
                className="icon-button"
                aria-label="Next page"
                disabled={(page + 1) * size >= documents.data.total}
                onClick={() => {
                  setPage(page + 1);
                  setSelected([]);
                }}
              >
                <ChevronRight size={18} />
              </button>
            </div>
          </div>
        )}
      </section>
      {confirm && (
        <Modal
          title={`Delete ${selected.length} document${selected.length === 1 ? "" : "s"}?`}
          onClose={() => !remove.isPending && setConfirm(false)}
        >
          <p>
            This permanently removes the selected records and their source
            images. This cannot be undone.
          </p>
          {remove.isError && <ErrorState error={remove.error} />}
          <div className="actions">
            <button
              className="button secondary"
              disabled={remove.isPending}
              onClick={() => setConfirm(false)}
            >
              Cancel
            </button>
            <button
              className="button danger"
              disabled={remove.isPending}
              onClick={() => remove.mutate(selected)}
            >
              {remove.isPending ? "Deleting…" : "Delete documents"}
            </button>
          </div>
        </Modal>
      )}
    </>
  );
}
