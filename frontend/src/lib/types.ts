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
  user_name?: string | null;
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

export interface User {
  id: string;
  email: string;
  name: string;
  picture?: string | null;
  is_guest: boolean;
}

export interface AuthResponse {
  access_token: string;
  token_type: string;
  user: User;
}

export interface RepositoryStats {
  discovered_files: number;
  included_files: number;
  skipped_files: number;
  failed_files: number;
  indexed_files: number;
  skipped_breakdown?: Record<string, number>;
  languages?: Record<string, number>;
  total_size_bytes?: number;
  total_lines?: number;
  duration_seconds?: number;
}

export interface RepositorySummary {
  repo_id: string;
  name: string;
  source_type: SourceType;
  status: RepositoryStatus;
  created_at: string;
  stats: RepositoryStats;
  progress?: IngestionProgress | null;
  owner_id?: string | null;
}

export interface FlowTraceStep {
  step_number: number;
  title: string;
  file_path: string;
  start_line: number;
  end_line: number;
  function_or_symbol?: string | null;
  description: string;
}

export interface FlowTraceResponse {
  flow_title: string;
  summary: string;
  steps: FlowTraceStep[];
  mermaid_diagram: string;
  citations: Citation[];
}

export interface OnboardingDocResponse {
  repo_id: string;
  title: string;
  content: string;
  summary: string;
  file_count: number;
  languages: string[];
}

export interface ArchitectureMapNode {
  id: string;
  label: string;
  module_type: "api" | "services" | "models" | "db" | "core" | "utils" | "other" | string;
  file_count: number;
  line_count: number;
  description?: string | null;
  key_files?: string[];
}

export interface ArchitectureMapEdge {
  source: string;
  target: string;
  relationship: string;
  import_count: number;
}

export interface ArchitectureMapResponse {
  repo_id: string;
  nodes: ArchitectureMapNode[];
  edges: ArchitectureMapEdge[];
  total_modules: number;
}

export interface QuizQuestion {
  id: string;
  question: string;
  options: string[];
  correct_index: number;
  hint: string;
  explanation: string;
  file_path: string;
  start_line: number;
  end_line: number;
}

export interface QuizResponse {
  repo_id: string;
  questions: QuizQuestion[];
  total_questions: number;
}

export interface VoiceChatRequest {
  repo_id: string;
  question: string;
  history?: ChatMessage[];
  session_id?: string | null;
  user_name?: string | null;
}

export interface VoiceChatResponse {
  answer: string;
  session_id?: string | null;
  cited_files: string[];
  audio_base64?: string | null;
}

export interface RepoFileInfo {
  file_path: string;
  line_count: number;
  chunk_count: number;
  language: string;
}

export interface RepoFilesResponse {
  repo_id: string;
  total_files: number;
  files: RepoFileInfo[];
}

export interface ChatSession {
  id: string;
  title: string;
  repo_id: string;
  createdAt: number;
  updatedAt: number;
  messages: any[]; // ChatMessageDisplay[]
}



