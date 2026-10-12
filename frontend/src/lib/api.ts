/**
 * Real API client for DevMind AI FastAPI backend.
 * Ref: PRD Section 6, 17; Step 25 of execution guide.
 */
import {
  BackendHealth,
  IngestResponse,
  IngestionProgress,
  ChatRequest,
  ChatResponse,
  SuggestedQuestionsResponse,
  RepositorySummary,
} from "./types";
import { getStoredToken } from "./auth";

const API_BASE = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

export class ApiError extends Error {
  constructor(public status: number, message: string) {
    super(message);
    this.name = "ApiError";
  }
}

function getAuthHeaders(): Record<string, string> {
  const token = getStoredToken();
  if (token) {
    return { Authorization: `Bearer ${token}` };
  }
  return {};
}


/**
 * Checks connection and configuration of backend service.
 */
export async function checkBackendHealth(): Promise<BackendHealth> {
  try {
    const res = await fetch(`${API_BASE}/api/health`, {
      method: "GET",
      cache: "no-store",
    });

    if (!res.ok) {
      return {
        status: "down",
        storage_ready: false,
        llm_configured: false,
        llm_provider: "unknown",
        llm_model: "unknown",
        embedding_provider: "unknown",
        message: `Backend returned status ${res.status}`,
      };
    }

    const data = await res.json();
    return {
      status: "ok",
      storage_ready: Boolean(data.storage_ready),
      llm_configured: Boolean(data.llm_valid),
      llm_provider: data.llm_provider || "unknown",
      llm_model: data.llm_model || "unknown",
      embedding_provider: data.embedding_provider || "local",
      message: data.llm_message,
    };
  } catch (err: unknown) {
    const msg = err instanceof Error ? err.message : "Connection failed";
    return {
      status: "down",
      storage_ready: false,
      llm_configured: false,
      llm_provider: "unknown",
      llm_model: "unknown",
      embedding_provider: "unknown",
      message: `Cannot connect to backend at ${API_BASE} (${msg})`,
    };
  }
}

/**
 * Uploads repository ZIP archive to backend.
 */
export async function uploadZipRepository(file: File): Promise<IngestResponse> {
  // Client-side validation: must be a ZIP file
  if (!file.name.toLowerCase().endsWith(".zip")) {
    throw new ApiError(400, "Please upload a valid .zip archive file.");
  }

  // Client-side validation: max 100 MB limit
  const maxBytes = 100 * 1024 * 1024;
  if (file.size > maxBytes) {
    const sizeMb = (file.size / (1024 * 1024)).toFixed(1);
    throw new ApiError(413, `File is too large (${sizeMb} MB). Maximum allowed size is 100 MB.`);
  }

  const formData = new FormData();
  formData.append("file", file);

  try {
    const res = await fetch(`${API_BASE}/api/ingest/zip`, {
      method: "POST",
      headers: {
        ...getAuthHeaders(),
      },
      body: formData,
    });

    if (!res.ok) {
      let errorDetail = "Upload failed.";
      try {
        const errorJson = await res.json();
        errorDetail = errorJson.detail || errorDetail;
      } catch {
        errorDetail = `Server returned status ${res.status} (${res.statusText})`;
      }
      throw new ApiError(res.status, errorDetail);
    }

    return await res.json();
  } catch (err: unknown) {
    if (err instanceof ApiError) throw err;
    const msg = err instanceof Error ? err.message : "Network error";
    throw new ApiError(0, `Failed to communicate with backend server: ${msg}`);
  }
}

/**
 * Clones and ingests a public Git repository from URL.
 */
export async function importGitRepository(url: string): Promise<IngestResponse> {
  const cleanUrl = url.trim();

  // Client-side URL validation
  if (!cleanUrl) {
    throw new ApiError(400, "Please enter a Git repository URL.");
  }

  if (!cleanUrl.startsWith("https://")) {
    throw new ApiError(400, "Only HTTPS Git URLs are supported (e.g., https://github.com/owner/repo).");
  }

  if (cleanUrl.includes("@") || cleanUrl.includes("://") && cleanUrl.split("://")[1]?.includes(":")) {
    throw new ApiError(400, "Credentials inside URLs are prohibited for security reasons.");
  }

  try {
    const res = await fetch(`${API_BASE}/api/ingest/git`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        ...getAuthHeaders(),
      },
      body: JSON.stringify({ url: cleanUrl }),
    });


    if (!res.ok) {
      let errorDetail = "Git repository import failed.";
      try {
        const errorJson = await res.json();
        errorDetail = errorJson.detail || errorDetail;
      } catch {
        errorDetail = `Server returned status ${res.status} (${res.statusText})`;
      }
      throw new ApiError(res.status, errorDetail);
    }

    return await res.json();
  } catch (err: unknown) {
    if (err instanceof ApiError) throw err;
    const msg = err instanceof Error ? err.message : "Network error";
    throw new ApiError(0, `Failed to communicate with backend server: ${msg}`);
  }
}

/**
 * Retrieves indexing progress for a repository.
 */
export async function getIngestionProgress(repoId: string): Promise<IngestionProgress> {
  try {
    const res = await fetch(`${API_BASE}/api/ingest/progress/${encodeURIComponent(repoId)}`, {
      method: "GET",
      headers: {
        ...getAuthHeaders(),
      },
      cache: "no-store",
    });

    if (!res.ok) {
      throw new ApiError(res.status, `Failed to fetch progress (${res.status})`);
    }

    return await res.json();
  } catch (err: unknown) {
    if (err instanceof ApiError) throw err;
    const msg = err instanceof Error ? err.message : "Network error";
    throw new ApiError(0, msg);
  }
}

/**
 * Manually triggers or retries background indexing for a repository.
 */
export async function triggerIndexing(repoId: string): Promise<void> {
  try {
    const res = await fetch(`${API_BASE}/api/ingest/index/${encodeURIComponent(repoId)}`, {
      method: "POST",
      headers: {
        ...getAuthHeaders(),
      },
    });

    if (!res.ok) {
      throw new ApiError(res.status, `Failed to trigger indexing (${res.status})`);
    }
  } catch (err: unknown) {
    if (err instanceof ApiError) throw err;
    const msg = err instanceof Error ? err.message : "Network error";
    throw new ApiError(0, msg);
  }
}

/**
 * Sends a question to the FastAPI QA service and receives evidence-grounded answer with citations.
 */
export async function askChatQuestion(request: ChatRequest): Promise<ChatResponse> {
  try {
    const res = await fetch(`${API_BASE}/api/chat`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        ...getAuthHeaders(),
      },
      body: JSON.stringify(request),
    });

    if (!res.ok) {
      let errorDetail = "Chat request failed.";
      try {
        const errorJson = await res.json();
        errorDetail = errorJson.detail || errorDetail;
      } catch {
        errorDetail = `Server returned status ${res.status}`;
      }
      throw new ApiError(res.status, errorDetail);
    }

    return await res.json();
  } catch (err: unknown) {
    if (err instanceof ApiError) throw err;
    const msg = err instanceof Error ? err.message : "Network error";
    throw new ApiError(0, msg);
  }
}

/**
 * Fetches repository-derived suggested questions based on indexed files and symbols.
 * Ref: Step 29 of execution guide.
 */
export async function getSuggestedQuestions(repoId: string): Promise<SuggestedQuestionsResponse> {
  try {
    const res = await fetch(`${API_BASE}/api/chat/suggested-questions/${encodeURIComponent(repoId)}`, {
      method: "GET",
      headers: {
        ...getAuthHeaders(),
      },
      cache: "no-store",
    });

    if (!res.ok) {
      let errorDetail = `Failed to fetch suggested questions (${res.status})`;
      try {
        const errorJson = await res.json();
        errorDetail = errorJson.detail || errorDetail;
      } catch {}
      throw new ApiError(res.status, errorDetail);
    }

    return await res.json();
  } catch (err: unknown) {
    if (err instanceof ApiError) throw err;
    const msg = err instanceof Error ? err.message : "Network error";
    throw new ApiError(0, msg);
  }
}

/**
 * Lists repositories owned by the current authenticated user or session.
 */
export async function fetchUserRepositories(): Promise<RepositorySummary[]> {
  try {
    const res = await fetch(`${API_BASE}/api/repositories`, {
      method: "GET",
      headers: {
        ...getAuthHeaders(),
      },
      cache: "no-store",
    });

    if (!res.ok) {
      throw new ApiError(res.status, `Failed to fetch repositories (${res.status})`);
    }

    return await res.json();
  } catch (err: unknown) {
    if (err instanceof ApiError) throw err;
    const msg = err instanceof Error ? err.message : "Network error";
    throw new ApiError(0, msg);
  }
}

/**
 * Deletes a repository, its disk source files, BM25 indices, and vector embeddings.
 */
export async function deleteRepository(repoId: string): Promise<{ status: string; message: string }> {
  try {
    const res = await fetch(`${API_BASE}/api/repositories/${encodeURIComponent(repoId)}`, {
      method: "DELETE",
      headers: {
        ...getAuthHeaders(),
      },
    });

    if (!res.ok) {
      let errorDetail = "Failed to delete repository.";
      try {
        const errJson = await res.json();
        errorDetail = errJson.detail || errorDetail;
      } catch {}
      throw new ApiError(res.status, errorDetail);
    }

    return await res.json();
  } catch (err: unknown) {
    if (err instanceof ApiError) throw err;
    const msg = err instanceof Error ? err.message : "Network error";
    throw new ApiError(0, msg);
  }
}

/**
 * Triggers on-demand re-indexing for an ingested repository.
 */
export async function reindexRepository(repoId: string): Promise<{ status: string; message: string }> {
  try {
    const res = await fetch(`${API_BASE}/api/repositories/${encodeURIComponent(repoId)}/reindex`, {
      method: "POST",
      headers: {
        ...getAuthHeaders(),
      },
    });

    if (!res.ok) {
      let errorDetail = "Failed to re-index repository.";
      try {
        const errJson = await res.json();
        errorDetail = errJson.detail || errorDetail;
      } catch {}
      throw new ApiError(res.status, errorDetail);
    }

    return await res.json();
  } catch (err: unknown) {
    if (err instanceof ApiError) throw err;
    const msg = err instanceof Error ? err.message : "Network error";
    throw new ApiError(0, msg);
  }
}

