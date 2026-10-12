/**
 * Shared TypeScript types for DevMind AI Frontend.
 * Ref: PRD Section 6, 7, 8, 17.5; ARCHITECTURE.md.
 */

export type SourceType = "zip" | "git";

export type RepositoryStatus = "uploading" | "processing" | "ready" | "failed";

export type StageStatus = "waiting" | "in_progress" | "done" | "failed";

export interface StageDetail {
  step_number: number;
  name: string;
  status: StageStatus;
  detail: string;
  current_count?: number | null;
  total_count?: number | null;
}

export interface IngestionMetrics {
  discovered_files: number;
  included_files: number;
  skipped_files: number;
  failed_files: number;
  indexed_files: number;
  total_lines: number;
  duration_seconds: number;
}

export interface IngestionProgress {
  repo_id: string;
  repo_name: string;
  source_type: SourceType;
  overall_status: RepositoryStatus;
  current_step: number;
  percentage: number;
  stages: StageDetail[];
  metrics: IngestionMetrics;
  skipped_breakdown: Record<string, number>;
  languages: Record<string, number>;
  error_message?: string | null;
}

export interface IngestResponse {
  repo_id: string;
  repo_name: string;
  source_type: SourceType;
  status: string;
  message: string;
}

export interface Citation {
  file_path: string;
  start_line: number;
  end_line: number;
  snippet?: string | null;
  chunk_id?: string | null;
}

export interface ChatMessage {
  role: "user" | "assistant" | "system";
  content: string;
}

export interface ChatRequest {
  repo_id: string;
  question: string;
  history?: ChatMessage[];
  max_chunks?: number;
  session_id?: string | null;
}

export interface ChatResponse {
  answer: string;
  citations: Citation[];
  abstained: boolean;
  inference_detected: boolean;
  retrieved_chunks_count: number;
  session_id?: string | null;
}

export interface BackendHealth {
  status: "ok" | "degraded" | "down";
  storage_ready: boolean;
  llm_configured: boolean;
  llm_provider: string;
  llm_model: string;
  embedding_provider: string;
  message?: string;
}

export interface SuggestedQuestion {
  question: string;
  category: string;
  derived_from: string;
  is_verified: boolean;
}

export interface SuggestedQuestionsResponse {
  repo_id: string;
  suggestions: SuggestedQuestion[];
  total_chunks_analyzed: number;
  languages_detected: string[];
}
