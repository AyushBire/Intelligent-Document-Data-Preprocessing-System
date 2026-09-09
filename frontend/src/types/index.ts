export interface DocumentListItem {
  id: number;
  filename: string;
  document_type: string;
  created_at: string;
}

export interface DocumentResponse {
  id: number;
  filename: string;
  file_path: string;
  document_type: string;
  ocr_text: string;
  report: string;
  structured_data: Record<string, unknown>;
  created_at: string;
  updated_at: string;
}

export interface DocumentUpdate {
  document_type?: string;
  report?: string;
  structured_data?: Record<string, unknown>;
}

export interface JobStatus {
  job_id: string;
  status: "pending" | "processing" | "done" | "error";
  stage: string;
  progress: number;
  document_id?: number;
  error?: string;
}

export interface TypeCount {
  document_type: string;
  count: number;
}

export interface StatsResponse {
  total: number;
  by_type: TypeCount[];
}

export interface UploadResponse {
  job_id: string;
  filename: string;
}