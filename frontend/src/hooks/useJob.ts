import { useQuery } from "@tanstack/react-query";
import { getJobStatus } from "../api/documents";

export const ACTIVE_JOB_KEY = "idps_active_job";
export interface ActiveJob {
  job_id: string;
  filename: string;
}

/** Restore job metadata, clearing legacy cached document contents.
 * @returns Active job or null. @throws None; disabled storage is tolerated.
 */
export function readActiveJob(): ActiveJob | null {
  try {
    localStorage.removeItem("idps_done_state");
    const value: unknown = JSON.parse(
      localStorage.getItem(ACTIVE_JOB_KEY) || "null",
    );
    if (
      value &&
      typeof value === "object" &&
      "job_id" in value &&
      "filename" in value &&
      typeof value.job_id === "string" &&
      typeof value.filename === "string"
    )
      return { job_id: value.job_id, filename: value.filename };
  } catch {
    return null;
  }
  return null;
}

/** Persist only job metadata. @param job Metadata or null. @returns Nothing. @throws None. */
export function saveActiveJob(job: ActiveJob | null): void {
  try {
    if (job) localStorage.setItem(ACTIVE_JOB_KEY, JSON.stringify(job));
    else localStorage.removeItem(ACTIVE_JOB_KEY);
  } catch {
    return;
  }
}

/** Poll until completion, failure or expiration.
 * @param id Job id. @returns Query state. @throws None; errors are returned in query state.
 */
export function useJob(id?: string) {
  return useQuery({
    queryKey: ["job", id],
    queryFn: () => getJobStatus(id!),
    enabled: !!id,
    retry: false,
    refetchInterval: (query) =>
      query.state.error ||
      ["done", "error"].includes(query.state.data?.status ?? "")
        ? false
        : 1000,
  });
}
