import client from "./client";
import type {
  DocumentListItem,
  DocumentResponse,
  DocumentUpdate,
  JobStatus,
  StatsResponse,
  UploadResponse,
} from "../types";

/** Upload an image for asynchronous extraction.
 * @param file Image file. @returns Job metadata. @throws AxiosError on upload failure.
 */
export const uploadDocument = async (file: File): Promise<UploadResponse> => {
  const form = new FormData();
  form.append("file", file);
  const { data } = await client.post<UploadResponse>(
    "/documents/upload",
    form,
    {
      headers: { "Content-Type": "multipart/form-data" },
    },
  );
  return data;
};

/** Retrieve processing status.
 * @param jobId Job identifier. @returns Job state. @throws AxiosError for expired jobs or request failure.
 */
export const getJobStatus = async (jobId: string): Promise<JobStatus> => {
  const { data } = await client.get<JobStatus>(`/documents/jobs/${jobId}`);
  return data;
};

/** Retrieve documents using optional filters.
 * @param params Type, search and pagination. @returns Document rows. @throws AxiosError on request failure.
 */
export const listDocuments = async (params?: {
  document_type?: string;
  search?: string;
  limit?: number;
  offset?: number;
}): Promise<DocumentListItem[]> => {
  const { data } = await client.get<DocumentListItem[]>("/documents", {
    params,
  });
  return data;
};

/** Retrieve one document.
 * @param id Record identifier. @returns Document data. @throws AxiosError for missing records or request failure.
 */
export const getDocument = async (id: number): Promise<DocumentResponse> => {
  const { data } = await client.get<DocumentResponse>(`/documents/${id}`);
  return data;
};

/** Apply supported document edits.
 * @param id Record identifier. @param body Changed values. @returns Updated record. @throws AxiosError on validation or request failure.
 */
export const updateDocument = async (
  id: number,
  body: DocumentUpdate,
): Promise<DocumentResponse> => {
  const { data } = await client.patch<DocumentResponse>(
    `/documents/${id}`,
    body,
  );
  return data;
};

/** Delete a record and its source image.
 * @param id Record identifier. @returns Resolves on deletion. @throws AxiosError on request failure.
 */
export const deleteDocument = async (id: number): Promise<void> => {
  await client.delete(`/documents/${id}`);
};

/** Delete selected records using repeated ids query parameters.
 * @param ids Record identifiers. @returns Resolves on deletion. @throws AxiosError on request failure.
 */
export const bulkDeleteDocuments = async (ids: number[]): Promise<void> => {
  await client.delete("/documents", {
    params: { ids },
    paramsSerializer: { indexes: null },
  });
};

/** Fetch a history page with the filtered total.
 * @param params Search, type and paging parameters.
 * @returns Items and total row count. @throws AxiosError if the request fails.
 */
export async function getDocumentPage(params: {
  search?: string;
  document_type?: string;
  limit: number;
  offset: number;
}) {
  const response = await client.get<DocumentListItem[]>("/documents", {
    params,
  });
  return {
    items: response.data,
    total: Number(response.headers["x-total-count"] ?? response.data.length),
  };
}

/** Retrieve total, UTC daily count and type distribution.
 * @returns Library statistics. @throws AxiosError on request failure.
 */
export const getStats = async (): Promise<StatsResponse> => {
  const { data } = await client.get<StatsResponse>("/documents/stats");
  return data;
};

/** Retrieve distinct document types.
 * @returns Sorted type values. @throws AxiosError on request failure.
 */
export const getDocumentTypes = async (): Promise<string[]> => {
  const { data } = await client.get<string[]>("/documents/types");
  return data;
};
