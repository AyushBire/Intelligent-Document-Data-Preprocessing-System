import axios from "axios";

/** Format legacy naive timestamps as UTC.
 * @param value ISO timestamp. @returns Local date and time. @throws None.
 */
export function dateLabel(value: string): string {
  const date = new Date(
    /[zZ]|[+-]\d{2}:\d{2}$/.test(value) ? value : `${value}Z`,
  );
  return Number.isNaN(date.valueOf())
    ? "Unknown date"
    : date.toLocaleString(undefined, {
        dateStyle: "medium",
        timeStyle: "short",
      });
}

/** Render nested extracted values.
 * @param value JSON value. @returns Readable text. @throws None for JSON values.
 */
export function valueLabel(value: unknown): string {
  return value == null
    ? "—"
    : typeof value === "object"
      ? JSON.stringify(value, null, 2)
      : String(value);
}

/** Explain backend and transport failures.
 * @param error Caught failure. @returns Safe message. @throws None.
 */
export function errorLabel(error: unknown): string {
  if (axios.isAxiosError(error)) {
    const detail: unknown = error.response?.data?.detail;
    if (typeof detail === "string") return detail;
    if (error.response?.status === 422)
      return "Invalid input. Check the values and try again.";
    if (error.response?.status === 404)
      return "This item is unavailable. It may have expired or been deleted.";
    if (error.response?.status === 401)
      return "Authentication is required. Sign in and try again.";
    if (!error.response)
      return "Cannot reach the API. Check your connection and try again.";
    return "The server could not complete the request. Please try again.";
  }
  return error instanceof Error
    ? error.message
    : "Something went wrong. Please try again.";
}

/** Save a generated export and release its URL.
 * @param name Filename. @param text Content. @param type MIME type.
 * @returns Nothing. @throws DOMException if downloads are blocked.
 */
export function download(
  name: string,
  text: string,
  type = "text/plain;charset=utf-8",
): void {
  const url = URL.createObjectURL(new Blob([text], { type }));
  const link = document.createElement("a");
  link.href = url;
  link.download = Array.from(name, (char) =>
    char.charCodeAt(0) < 32 || '<>:"/\\|?*'.includes(char) ? "_" : char,
  ).join("");
  link.click();
  window.setTimeout(() => URL.revokeObjectURL(url), 1000);
}

/** Export field-value CSV with formula-injection protection.
 * @param data Extracted fields. @returns CSV. @throws None for JSON values.
 */
export function toCsv(data: Record<string, unknown>): string {
  /** Quote a cell. @param value Cell text. @returns Safe text. @throws None. */
  const cell = (value: string) =>
    `"${(/^[\s]*[=+@-]/.test(value) ? "'" + value : value).replace(/"/g, '""')}"`;
  return (
    "field,value\r\n" +
    Object.entries(data)
      .map(([key, value]) => `${cell(key)},${cell(valueLabel(value))}`)
      .join("\r\n")
  );
}
