import { useEffect, useRef, useState } from "react";
import type { ReactNode } from "react";
import { AlertCircle, Check, Copy, FileText, X } from "lucide-react";
import { errorLabel } from "../lib/utils";

/** Present a page heading. @param props Heading and actions. @returns Section. @throws None. */
export function PageHeader({
  title,
  subtitle,
  actions,
}: {
  title: string;
  subtitle: string;
  actions?: ReactNode;
}) {
  return (
    <header className="page-header">
      <div>
        <p className="eyebrow">DOCUMENT INTELLIGENCE</p>
        <h1>{title}</h1>
        <p>{subtitle}</p>
      </div>
      <div className="actions">{actions}</div>
    </header>
  );
}

/** Present an actionable failure. @param props Error and retry. @returns Alert. @throws None. */
export function ErrorState({
  error,
  retry,
}: {
  error: unknown;
  retry?: () => void;
}) {
  return (
    <div className="error-box" role="alert">
      <AlertCircle size={20} />
      <span>{errorLabel(error)}</span>
      {retry && (
        <button className="button secondary" onClick={retry}>
          Try again
        </button>
      )}
    </div>
  );
}

/** Render loading placeholders. @returns Skeleton. @throws None. */
export function Loading() {
  return (
    <div role="status" aria-label="Loading" className="skeleton">
      <div />
      <div />
      <div />
    </div>
  );
}

/** Explain an empty collection. @param props Title and action. @returns Panel. @throws None. */
export function EmptyState({
  title,
  children,
}: {
  title: string;
  children?: ReactNode;
}) {
  return (
    <div className="empty">
      <FileText size={32} />
      <h3>{title}</h3>
      {children}
    </div>
  );
}

/** Copy with explicit feedback. @param props Text and label. @returns Button. @throws None. */
export function CopyButton({
  text,
  label = "Copy",
}: {
  text: string;
  label?: string;
}) {
  const [state, setState] = useState("");
  /** Write clipboard content. @returns Promise after feedback. @throws None. */
  async function copy() {
    try {
      await navigator.clipboard.writeText(text);
      setState("Copied");
    } catch {
      setState("Copy unavailable");
    }
  }
  return (
    <button
      className="button secondary compact"
      onClick={() => void copy()}
      aria-label={label}
    >
      {state === "Copied" ? <Check size={15} /> : <Copy size={15} />}
      <span aria-live="polite">{state || label}</span>
    </button>
  );
}

/** Native modal with focus trapping and restoration.
 * @param props Title, body and close callback. @returns Dialog. @throws None.
 */
export function Modal({
  title,
  children,
  onClose,
}: {
  title: string;
  children: ReactNode;
  onClose: () => void;
}) {
  const ref = useRef<HTMLDialogElement>(null);
  useEffect(() => {
    const previous = document.activeElement as HTMLElement | null;
    const dialog = ref.current;
    dialog?.showModal();
    return () => {
      dialog?.close();
      previous?.focus();
    };
  }, []);
  return (
    <dialog
      ref={ref}
      onCancel={(event) => {
        event.preventDefault();
        onClose();
      }}
      aria-labelledby="modal-title"
    >
      <div className="modal-heading">
        <h2 id="modal-title">{title}</h2>
        <button
          className="icon-button"
          aria-label="Close dialog"
          onClick={onClose}
        >
          <X />
        </button>
      </div>
      {children}
    </dialog>
  );
}
