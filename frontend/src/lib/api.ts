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
  FlowTraceResponse,
  OnboardingDocResponse,
  ArchitectureMapResponse,
  QuizResponse,
  VoiceChatRequest,
  VoiceChatResponse,
} from "./types";
import { getStoredToken, getStoredUser } from "./auth";

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
    const user = getStoredUser();
    const payload: ChatRequest = {
      ...request,
      user_name: request.user_name || user?.name || user?.id || "Parth",
    };
    const res = await fetch(`${API_BASE}/api/chat`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        ...getAuthHeaders(),
      },
      body: JSON.stringify(payload),
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
 * Streams real-time tokens using Server-Sent Events (SSE) for responsive typewriter answers.
 */
export async function askChatQuestionStream(
  request: ChatRequest,
  callbacks: {
    onChunk: (token: string) => void;
    onMetadata?: (meta: { session_id?: string; retrieved_chunks_count?: number }) => void;
    onDone?: (response: ChatResponse) => void;
    onError?: (err: Error) => void;
  }
): Promise<void> {
  try {
    const user = getStoredUser();
    const payload: ChatRequest = {
      ...request,
      user_name: request.user_name || user?.name || user?.id || "Parth",
    };
    const res = await fetch(`${API_BASE}/api/chat/stream`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        ...getAuthHeaders(),
      },
      body: JSON.stringify(payload),
    });

    if (!res.ok) {
      let errorDetail = "Chat stream failed.";
      try {
        const errorJson = await res.json();
        errorDetail = errorJson.detail || errorDetail;
      } catch {
        errorDetail = `Server returned status ${res.status}`;
      }
      throw new ApiError(res.status, errorDetail);
    }

    if (!res.body) {
      throw new ApiError(0, "Readable stream not supported by browser.");
    }

    const reader = res.body.getReader();
    const decoder = new TextDecoder("utf-8");
    let buffer = "";

    while (true) {
      const { done, value } = await reader.read();
      if (done) break;

      buffer += decoder.decode(value, { stream: true });
      const blocks = buffer.split("\n\n");
      buffer = blocks.pop() || "";

      for (const block of blocks) {
        const eventMatch = block.match(/^event:\s*([^\n\r]+)/m);
        const dataPrefixIdx = block.indexOf("data:");
        const rawData = dataPrefixIdx !== -1 ? block.slice(dataPrefixIdx + 5).trim() : "";
        const event = eventMatch ? eventMatch[1].trim() : "message";

        if (event === "token") {
          try {
            const parsed = JSON.parse(rawData);
            if (parsed.token) callbacks.onChunk(parsed.token);
          } catch {
            callbacks.onChunk(rawData);
          }
        } else if (event === "metadata") {
          try {
            const parsed = JSON.parse(rawData);
            callbacks.onMetadata?.(parsed);
          } catch {}
        } else if (event === "done") {
          try {
            const parsed: ChatResponse = JSON.parse(rawData);
            callbacks.onDone?.(parsed);
          } catch {}
        }
      }
    }
  } catch (err: unknown) {
    const errorObj = err instanceof Error ? err : new Error("Streaming error");
    callbacks.onError?.(errorObj);
    throw errorObj;
  }
}

/**
 * Submits user satisfaction rating (thumbs up/down) and quality reports.
 */
export async function submitChatFeedback(feedback: {
  repo_id: string;
  message_id?: string;
  session_id?: string;
  rating: "up" | "down";
  feedback_tag?: string;
  comment?: string;
}): Promise<{ status: string; message: string }> {
  try {
    const res = await fetch(`${API_BASE}/api/chat/feedback`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        ...getAuthHeaders(),
      },
      body: JSON.stringify(feedback),
    });

    if (!res.ok) {
      throw new ApiError(res.status, `Failed to submit feedback (${res.status})`);
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

/**
 * Traces execution path with steps and Mermaid sequence diagram (Feature 8).
 */
export async function getFlowTrace(repoId: string, flowQuery: string): Promise<FlowTraceResponse> {
  try {
    const res = await fetch(`${API_BASE}/api/chat/flow-trace`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        ...getAuthHeaders(),
      },
      body: JSON.stringify({ repo_id: repoId, flow_query: flowQuery }),
    });

    if (!res.ok) {
      let errDetail = "Failed to trace execution flow.";
      try {
        const errJson = await res.json();
        errDetail = errJson.detail || errDetail;
      } catch {}
      throw new ApiError(res.status, errDetail);
    }

    return await res.json();
  } catch (err: unknown) {
    if (err instanceof ApiError) throw err;
    const msg = err instanceof Error ? err.message : "Network error";
    throw new ApiError(0, msg);
  }
}

/**
 * Generates comprehensive Onboarding Architecture Guide (Feature 9).
 */
export async function getOnboardingDoc(repoId: string): Promise<OnboardingDocResponse> {
  try {
    const res = await fetch(`${API_BASE}/api/chat/onboarding-doc`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        ...getAuthHeaders(),
      },
      body: JSON.stringify({ repo_id: repoId }),
    });

    if (!res.ok) {
      let errDetail = "Failed to generate onboarding document.";
      try {
        const errJson = await res.json();
        errDetail = errJson.detail || errDetail;
      } catch {}
      throw new ApiError(res.status, errDetail);
    }

    return await res.json();
  } catch (err: unknown) {
    if (err instanceof ApiError) throw err;
    const msg = err instanceof Error ? err.message : "Network error";
    throw new ApiError(0, msg);
  }
}

/**
 * Retrieves interactive architectural dependency graph (Feature 11).
 */
export async function getArchitectureMap(repoId: string): Promise<ArchitectureMapResponse> {
  try {
    const res = await fetch(`${API_BASE}/api/chat/architecture-map/${encodeURIComponent(repoId)}`, {
      method: "GET",
      headers: {
        ...getAuthHeaders(),
      },
    });

    if (!res.ok) {
      let errDetail = "Failed to fetch architecture map.";
      try {
        const errJson = await res.json();
        errDetail = errJson.detail || errDetail;
      } catch {}
      throw new ApiError(res.status, errDetail);
    }

    return await res.json();
  } catch (err: unknown) {
    if (err instanceof ApiError) throw err;
    const msg = err instanceof Error ? err.message : "Network error";
    throw new ApiError(0, msg);
  }
}

/**
 * Generates codebase understanding quiz questions (Feature 12).
 */
export async function getLearningQuiz(repoId: string): Promise<QuizResponse> {
  try {
    const res = await fetch(`${API_BASE}/api/chat/quiz/${encodeURIComponent(repoId)}`, {
      method: "GET",
      headers: {
        ...getAuthHeaders(),
      },
    });

    if (!res.ok) {
      let errDetail = "Failed to fetch codebase quiz.";
      try {
        const errJson = await res.json();
        errDetail = errJson.detail || errDetail;
      } catch {}
      throw new ApiError(res.status, errDetail);
    }

    return await res.json();
  } catch (err: unknown) {
    if (err instanceof ApiError) throw err;
    const msg = err instanceof Error ? err.message : "Network error";
    throw new ApiError(0, msg);
  }
}

/**
 * Ask a spoken conversational question for voice chat (Feature 13).
 */
export async function askVoiceQuestion(req: VoiceChatRequest): Promise<VoiceChatResponse> {
  try {
    const user = getStoredUser();
    const payload: VoiceChatRequest = {
      ...req,
      user_name: req.user_name || user?.name || user?.id || "Parth",
    };
    const res = await fetch(`${API_BASE}/api/chat/voice`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        ...getAuthHeaders(),
      },
      body: JSON.stringify(payload),
    });

    if (!res.ok) {
      let errDetail = `Voice request failed (${res.status})`;
      try {
        const errJson = await res.json();
        errDetail = errJson.detail || errDetail;
      } catch {}
      throw new ApiError(res.status, errDetail);
    }

    return await res.json();
  } catch (err: unknown) {
    if (err instanceof ApiError) throw err;
    const msg = err instanceof Error ? err.message : "Network error";
    throw new ApiError(0, msg);
  }
}



