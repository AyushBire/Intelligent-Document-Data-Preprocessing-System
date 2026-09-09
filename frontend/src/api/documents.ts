import client from "./client";
import type {
  DocumentListItem,
  DocumentResponse,
  DocumentUpdate,
  JobStatus,
  StatsResponse,
  UploadResponse,
} from "../types";

// Upload a document — returns job_id for tracking
export const uploadDocument = async (file: File): Promise<UploadResponse> => {
  const form = new FormData();
  form.append("file", file);
  const { data } = await client.post<UploadResponse>("/documents/upload", form, {
    headers: { "Content-Type": "multipart/form-data" },
  });
  return data;
};

// Poll job status
export const getJobStatus = async (jobId: string): Promise<JobStatus> => {
  const { data } = await client.get<JobStatus>(`/documents/jobs/${jobId}`);
  return data;
};

// List documents with optional filters
export const listDocuments = async (params?: {
  document_type?: string;
  search?: string;
  limit?: number;
  offset?: number;
}): Promise<DocumentListItem[]> => {
  const { data } = await client.get<DocumentListItem[]>("/documents", { params });
  return data;
};

// Get single document
export const getDocument = async (id: number): Promise<DocumentResponse> => {
  const { data } = await client.get<DocumentResponse>(`/documents/${id}`);
  return data;
};

// Update document
export const updateDocument = async (
  id: number,
  body: DocumentUpdate
): Promise<DocumentResponse> => {
  const { data } = await client.patch<DocumentResponse>(`/documents/${id}`, body);
  return data;
};

// Delete single document
export const deleteDocument = async (id: number): Promise<void> => {
  await client.delete(`/documents/${id}`);
};

// Bulk delete
export const bulkDeleteDocuments = async (ids: number[]): Promise<void> => {
  await client.delete("/documents", { params: { ids } });
};

// Get stats
export const getStats = async (): Promise<StatsResponse> => {
  const { data } = await client.get<StatsResponse>("/documents/stats");
  return data;
};

// Get all document types
export const getDocumentTypes = async (): Promise<string[]> => {
  const { data } = await client.get<string[]>("/documents/types");
  return data;
};