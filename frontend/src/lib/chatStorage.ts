import { IngestResponse, ChatSession, SourceType } from "./types";

export interface HomeChatSessionItem {
  sessionId: string;
  title: string;
  repo_id: string;
  repo_name: string;
  source_type: SourceType;
  createdAt: number;
  updatedAt: number;
  messageCount: number;
  lastMessagePreview?: string;
}

const SESSIONS_PREFIX = "devmind_sessions_";
const REPO_META_PREFIX = "devmind_repo_meta_";

export const getSessionsStorageKey = (repoId: string) => `${SESSIONS_PREFIX}${repoId}`;
export const getRepoMetaKey = (repoId: string) => `${REPO_META_PREFIX}${repoId}`;

/**
 * Saves repository metadata so any session can be tied back to its repository name and source type.
 */
export function saveRepoMeta(repo: IngestResponse): void {
  if (typeof window === "undefined" || !repo?.repo_id) return;
  try {
    localStorage.setItem(getRepoMetaKey(repo.repo_id), JSON.stringify(repo));
  } catch (e) {
    console.warn("Failed to cache repo meta:", e);
  }
}

/**
 * Retrieves repository metadata by repo_id from localStorage.
 */
export function getRepoMeta(repoId: string): IngestResponse | null {
  if (typeof window === "undefined" || !repoId) return null;
  try {
    const raw = localStorage.getItem(getRepoMetaKey(repoId));
    if (raw) return JSON.parse(raw);
  } catch (e) {
    console.warn("Failed to load repo meta:", e);
  }
  return null;
}

/**
 * Loads stored sessions for a specific repository.
 */
export function loadStoredSessions(repoId: string): ChatSession[] {
  if (typeof window === "undefined" || !repoId) return [];
  try {
    const raw = localStorage.getItem(getSessionsStorageKey(repoId));
    if (raw) {
      const parsed = JSON.parse(raw);
      if (Array.isArray(parsed) && parsed.length > 0) return parsed;
    }
  } catch (e) {
    console.warn("Failed to load stored chat sessions:", e);
  }
  return [];
}

/**
 * Saves chat sessions for a specific repository.
 */
export function saveStoredSessions(repoId: string, sessions: ChatSession[]): void {
  if (typeof window === "undefined" || !repoId) return;
  try {
    localStorage.setItem(getSessionsStorageKey(repoId), JSON.stringify(sessions));
  } catch (e) {
    console.warn("Failed to save chat sessions:", e);
  }
}

/**
 * Scans all stored chat sessions across all repositories in localStorage
 * and returns them formatted for the Home page chat history list.
 */
export function getAllHomeChatSessions(): HomeChatSessionItem[] {
  if (typeof window === "undefined") return [];

  const items: HomeChatSessionItem[] = [];

  try {
    for (let i = 0; i < localStorage.length; i++) {
      const key = localStorage.key(i);
      if (key && key.startsWith(SESSIONS_PREFIX)) {
        const repoId = key.replace(SESSIONS_PREFIX, "");
        const meta = getRepoMeta(repoId);
        const rawSessions = localStorage.getItem(key);

        if (rawSessions) {
          const sessions: ChatSession[] = JSON.parse(rawSessions);
          if (Array.isArray(sessions)) {
            for (const s of sessions) {
              const msgs = s.messages || [];
              const lastMsg = msgs.length > 0 ? msgs[msgs.length - 1] : null;
              const lastPreview = lastMsg
                ? typeof lastMsg.content === "string"
                  ? lastMsg.content.slice(0, 100)
                  : ""
                : "";

              // Determine best human-readable repo name
              const repoName =
                meta?.repo_name ||
                (s.repo_id.length > 20 ? s.repo_id.slice(0, 16) + "..." : s.repo_id) ||
                "Indexed Repository";

              items.push({
                sessionId: s.id,
                title: s.title || "Untitled Chat",
                repo_id: s.repo_id || repoId,
                repo_name: repoName,
                source_type: meta?.source_type || "zip",
                createdAt: s.createdAt || Date.now(),
                updatedAt: s.updatedAt || s.createdAt || Date.now(),
                messageCount: msgs.length,
                lastMessagePreview: lastPreview,
              });
            }
          }
        }
      }
    }
  } catch (e) {
    console.warn("Failed scanning all chat sessions:", e);
  }

  // Sort by updatedAt descending (newest activity first)
  return items.sort((a, b) => b.updatedAt - a.updatedAt);
}

/**
 * Deletes a session from a specific repository in localStorage.
 */
export function deleteStoredSession(repoId: string, sessionId: string): void {
  if (typeof window === "undefined") return;
  const sessions = loadStoredSessions(repoId);
  const updated = sessions.filter((s) => s.id !== sessionId);
  if (updated.length > 0) {
    saveStoredSessions(repoId, updated);
  } else {
    // If no sessions remain, remove key
    localStorage.removeItem(getSessionsStorageKey(repoId));
  }
}
