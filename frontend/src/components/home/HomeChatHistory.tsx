"use client";

import React, { useState, useEffect } from "react";
import {
  MessageSquare,
  Search,
  ArrowRight,
  Trash2,
  FolderGit,
  Clock,
  Sparkles,
  History,
  LogIn,
  Layers,
} from "lucide-react";
import {
  getAllHomeChatSessions,
  deleteStoredSession,
  getRepoMeta,
  HomeChatSessionItem,
} from "@/lib/chatStorage";
import { fetchUserRepositories } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import { IngestResponse, RepositorySummary } from "@/lib/types";

interface HomeChatHistoryProps {
  onSelectChat: (repo: IngestResponse, sessionId?: string) => void;
  onOpenAuth: () => void;
}

// Relative date formatter
function formatRelativeDate(timestamp: number): string {
  const diffMs = Date.now() - timestamp;
  const diffMins = Math.floor(diffMs / (1000 * 60));
  const diffHours = Math.floor(diffMs / (1000 * 60 * 60));
  const diffDays = Math.floor(diffMs / (1000 * 60 * 60 * 24));

  if (diffMins < 2) return "Just now";
  if (diffMins < 60) return `${diffMins}m ago`;
  if (diffHours < 24) return `${diffHours}h ago`;
  if (diffDays === 1) return "Yesterday";
  if (diffDays < 7) return `${diffDays}d ago`;

  return new Date(timestamp).toLocaleDateString([], {
    month: "short",
    day: "numeric",
  });
}

export const HomeChatHistory: React.FC<HomeChatHistoryProps> = ({
  onSelectChat,
  onOpenAuth,
}) => {
  const { user, isAuthenticated } = useAuth();
  const [sessions, setSessions] = useState<HomeChatSessionItem[]>([]);
  const [repositories, setRepositories] = useState<RepositorySummary[]>([]);
  const [searchQuery, setSearchQuery] = useState("");
  const [isLoadingRepos, setIsLoadingRepos] = useState(false);

  // Load chat sessions from local master store
  const refreshSessions = () => {
    const list = getAllHomeChatSessions();
    setSessions(list);
  };

  useEffect(() => {
    refreshSessions();
  }, []);

  // When user is authenticated, also fetch their indexed repositories from the backend
  useEffect(() => {
    if (isAuthenticated) {
      setIsLoadingRepos(true);
      fetchUserRepositories()
        .then((repos) => {
          setRepositories(repos.filter((r) => r.status === "ready"));
        })
        .catch((err) => {
          console.warn("Could not fetch user repositories on home:", err);
        })
        .finally(() => {
          setIsLoadingRepos(false);
        });
    } else {
      setRepositories([]);
    }
  }, [isAuthenticated, user]);

  // Handle clicking a specific chat session to resume
  const handleResumeChat = (item: HomeChatSessionItem) => {
    // Look up cached repo meta or fallback to minimum IngestResponse
    const meta = getRepoMeta(item.repo_id);
    const repo: IngestResponse = {
      repo_id: item.repo_id,
      repo_name: meta?.repo_name || item.repo_name,
      source_type: meta?.source_type || item.source_type,
      status: meta?.status || "ready",
      message: "Resuming chat",
    };
    onSelectChat(repo, item.sessionId);
  };

  // Handle starting a fresh chat on an indexed repository from the cloud
  const handleStartChatOnRepo = (repo: RepositorySummary) => {
    const ingest: IngestResponse = {
      repo_id: repo.repo_id,
      repo_name: repo.name,
      source_type: repo.source_type,
      status: repo.status,
      message: "Ready for questions",
    };
    onSelectChat(ingest);
  };

  // Handle deleting a session
  const handleDeleteSession = (
    e: React.MouseEvent,
    item: HomeChatSessionItem
  ) => {
    e.stopPropagation();
    if (window.confirm(`Delete chat session "${item.title}"?`)) {
      deleteStoredSession(item.repo_id, item.sessionId);
      refreshSessions();
    }
  };

  // Filter sessions by search query
  const filteredSessions = sessions.filter((s) => {
    if (!searchQuery.trim()) return true;
    const q = searchQuery.toLowerCase();
    return (
      s.title.toLowerCase().includes(q) ||
      s.repo_name.toLowerCase().includes(q) ||
      (s.lastMessagePreview && s.lastMessagePreview.toLowerCase().includes(q))
    );
  });

  // Repositories that don't have existing local sessions, for quick-launch
  const reposWithoutSessions = repositories.filter(
    (r) => !sessions.some((s) => s.repo_id === r.repo_id)
  );

  return (
    <section className="w-full max-w-4xl mx-auto space-y-6 pt-2">
      {/* Header bar */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 border-b border-[#E5E2DB] pb-4">
        <div className="flex items-center gap-3">
          <div className="w-10 h-10 rounded-2xl bg-[#E6F4F1] text-[#0B6E5F] flex items-center justify-center shadow-xs">
            <History className="w-5 h-5" />
          </div>
          <div>
            <div className="flex items-center gap-2">
              <h2 className="text-xl font-bold text-[#1C2024] tracking-tight">
                Your Chat History
              </h2>
              {sessions.length > 0 && (
                <span className="px-2 py-0.5 rounded-full text-xs font-semibold bg-[#EAE8E2] text-[#636A74]">
                  {sessions.length} {sessions.length === 1 ? "chat" : "chats"}
                </span>
              )}
            </div>
            <p className="text-xs text-[#636A74] mt-0.5">
              Resume your previous conversations or jump directly into indexed codebases
            </p>
          </div>
        </div>

        {/* Search & Auth status */}
        <div className="flex items-center gap-2.5">
          {sessions.length > 2 && (
            <div className="relative w-full sm:w-56">
              <Search className="w-3.5 h-3.5 text-[#8C939D] absolute left-3 top-1/2 -translate-y-1/2 pointer-events-none" />
              <input
                type="text"
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
                placeholder="Search past chats..."
                className="w-full pl-8 pr-3 py-1.5 bg-white border border-[#E5E2DB] rounded-xl text-xs text-[#1C2024] placeholder-[#8C939D] focus:outline-none focus:ring-1 focus:ring-[#0B6E5F] shadow-2xs transition-all"
              />
            </div>
          )}

          {!isAuthenticated && (
            <button
              type="button"
              onClick={onOpenAuth}
              className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-xl bg-[#1C2024] hover:bg-[#2C3136] text-white text-xs font-semibold shadow-xs transition-all cursor-pointer whitespace-nowrap"
            >
              <LogIn className="w-3.5 h-3.5" />
              <span>Sign In to Sync</span>
            </button>
          )}
        </div>
      </div>

      {/* Non-authenticated banner if user isn't logged in */}
      {!isAuthenticated && sessions.length === 0 && (
        <div className="p-5 rounded-2xl bg-white border border-[#E5E2DB] shadow-xs flex flex-col sm:flex-row items-start sm:items-center justify-between gap-4">
          <div className="flex items-start gap-3">
            <div className="w-9 h-9 rounded-xl bg-[#E6F4F1] text-[#0B6E5F] flex items-center justify-center flex-shrink-0 mt-0.5">
              <Sparkles className="w-4 h-4" />
            </div>
            <div>
              <h4 className="text-sm font-bold text-[#1C2024]">
                Sign in to view your saved chats
              </h4>
              <p className="text-xs text-[#636A74] mt-0.5">
                Your past indexed codebases and chat sessions are preserved in your account.
              </p>
            </div>
          </div>
          <button
            type="button"
            onClick={onOpenAuth}
            className="px-4 py-2 rounded-xl bg-[#0B6E5F] hover:bg-[#085247] text-white text-xs font-bold transition-all shadow-xs cursor-pointer flex-shrink-0"
          >
            Sign In Now
          </button>
        </div>
      )}

      {/* Chat Sessions Grid / Cards */}
      {filteredSessions.length > 0 ? (
        <div className="grid grid-cols-1 md:grid-cols-2 gap-3.5">
          {filteredSessions.map((item) => (
            <div
              key={`${item.repo_id}-${item.sessionId}`}
              onClick={() => handleResumeChat(item)}
              className="group relative p-4 rounded-2xl bg-white border border-[#E5E2DB] hover:border-[#0B6E5F]/40 hover:shadow-md transition-all cursor-pointer flex flex-col justify-between gap-3 text-left"
            >
              <div className="space-y-1.5">
                {/* Top line: Repo badge & Relative date */}
                <div className="flex items-center justify-between gap-2 text-[11px]">
                  <div className="inline-flex items-center gap-1.5 px-2 py-0.5 rounded-lg bg-[#FAF9F6] border border-[#EAE8E2] text-[#1C2024] font-medium max-w-[200px] truncate">
                    <FolderGit className="w-3 h-3 text-[#0B6E5F] flex-shrink-0" />
                    <span className="truncate">{item.repo_name}</span>
                  </div>

                  <div className="flex items-center gap-1 text-[#8C939D] font-mono text-[10px]">
                    <Clock className="w-3 h-3" />
                    <span>{formatRelativeDate(item.updatedAt)}</span>
                  </div>
                </div>

                {/* Chat Title */}
                <h3 className="text-sm font-bold text-[#1C2024] group-hover:text-[#0B6E5F] transition-colors leading-snug line-clamp-1">
                  {item.title}
                </h3>

                {/* Message preview or message count */}
                <p className="text-xs text-[#636A74] line-clamp-2 leading-relaxed">
                  {item.lastMessagePreview
                    ? `"${item.lastMessagePreview}"`
                    : "Conversation ready to continue."}
                </p>
              </div>

              {/* Bottom footer: Message count + Resume button */}
              <div className="flex items-center justify-between pt-2 border-t border-[#F2EFE9] text-xs">
                <span className="text-[11px] font-semibold text-[#8C939D] flex items-center gap-1">
                  <MessageSquare className="w-3 h-3" />
                  {item.messageCount} {item.messageCount === 1 ? "turn" : "turns"}
                </span>

                <div className="flex items-center gap-2">
                  <button
                    type="button"
                    onClick={(e) => handleDeleteSession(e, item)}
                    className="p-1 rounded-lg text-[#8C939D] hover:text-red-600 hover:bg-red-50 transition-colors opacity-0 group-hover:opacity-100 cursor-pointer"
                    title="Delete chat session"
                  >
                    <Trash2 className="w-3.5 h-3.5" />
                  </button>

                  <div className="inline-flex items-center gap-1 text-xs font-bold text-[#0B6E5F] group-hover:translate-x-0.5 transition-transform">
                    <span>Resume</span>
                    <ArrowRight className="w-3.5 h-3.5" />
                  </div>
                </div>
              </div>
            </div>
          ))}
        </div>
      ) : sessions.length > 0 && searchQuery ? (
        <div className="p-8 text-center text-xs text-[#8C939D] bg-white border border-[#E5E2DB] rounded-2xl space-y-1">
          <p className="font-semibold text-[#1C2024]">No chats matched &quot;{searchQuery}&quot;</p>
          <p>Try searching for a different conversation title or codebase.</p>
        </div>
      ) : null}

      {/* Quick Launch: Indexed Repositories from Account (if any) */}
      {isAuthenticated && reposWithoutSessions.length > 0 && (
        <div className="space-y-2.5 pt-2">
          <div className="flex items-center gap-2 text-xs font-bold text-[#636A74] uppercase tracking-wider">
            <Layers className="w-3.5 h-3.5 text-[#0B6E5F]" />
            <span>Indexed Codebases Ready for Chat</span>
          </div>

          <div className="grid grid-cols-1 sm:grid-cols-2 md:grid-cols-3 gap-3">
            {reposWithoutSessions.map((repo) => (
              <button
                key={repo.repo_id}
                type="button"
                onClick={() => handleStartChatOnRepo(repo)}
                className="p-3.5 rounded-xl bg-white border border-[#E5E2DB] hover:border-[#0B6E5F] hover:bg-[#FAF9F6] text-left transition-all group cursor-pointer shadow-2xs"
              >
                <div className="flex items-center justify-between gap-1 mb-1.5">
                  <span className="text-xs font-bold text-[#1C2024] truncate group-hover:text-[#0B6E5F]">
                    {repo.name}
                  </span>
                  <span className="text-[10px] font-semibold text-emerald-700 bg-emerald-50 px-1.5 py-0.5 rounded border border-emerald-200">
                    Ready
                  </span>
                </div>
                <div className="text-[11px] text-[#636A74] flex items-center justify-between">
                  <span>
                    {repo.stats?.indexed_files || repo.stats?.discovered_files || 0} files • {repo.source_type.toUpperCase()}
                  </span>
                  <span className="text-[#0B6E5F] font-bold text-[11px] group-hover:translate-x-0.5 transition-transform flex items-center gap-0.5">
                    Start Chat →
                  </span>
                </div>
              </button>
            ))}
          </div>
        </div>
      )}
    </section>
  );
};
