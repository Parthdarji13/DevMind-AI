"use client";

import React, { useState, useEffect } from "react";
import {
  History,
  X,
  Search,
  MessageSquare,
  FolderGit,
  Clock,
  Trash2,
  ArrowRight,
  LogIn,
  Home,
  Sparkles,
} from "lucide-react";
import {
  getAllHomeChatSessions,
  deleteStoredSession,
  getRepoMeta,
  HomeChatSessionItem,
} from "@/lib/chatStorage";
import { useAuth } from "@/lib/auth";
import { IngestResponse } from "@/lib/types";

interface ChatHistoryDrawerProps {
  isOpen: boolean;
  onClose: () => void;
  onSelectChat: (repo: IngestResponse, sessionId?: string) => void;
  onOpenAuth: () => void;
  onGoHome?: () => void;
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

export const ChatHistoryDrawer: React.FC<ChatHistoryDrawerProps> = ({
  isOpen,
  onClose,
  onSelectChat,
  onOpenAuth,
  onGoHome,
}) => {
  const { user, isAuthenticated } = useAuth();
  const [sessions, setSessions] = useState<HomeChatSessionItem[]>([]);
  const [searchQuery, setSearchQuery] = useState("");

  // Refresh sessions whenever drawer opens
  const refreshSessions = () => {
    const list = getAllHomeChatSessions();
    setSessions(list);
  };

  useEffect(() => {
    if (isOpen) {
      refreshSessions();
    }
  }, [isOpen, isAuthenticated, user]);

  if (!isOpen) return null;

  // Handle clicking a past chat session
  const handleResumeChat = (item: HomeChatSessionItem) => {
    const meta = getRepoMeta(item.repo_id);
    const repo: IngestResponse = {
      repo_id: item.repo_id,
      repo_name: meta?.repo_name || item.repo_name,
      source_type: meta?.source_type || item.source_type,
      status: meta?.status || "ready",
      message: "Resuming chat",
    };
    onSelectChat(repo, item.sessionId);
    onClose();
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

  return (
    <div className="fixed inset-0 z-50 overflow-hidden">
      {/* Backdrop */}
      <div
        className="fixed inset-0 bg-black/40 backdrop-blur-xs transition-opacity animate-in fade-in duration-200"
        onClick={onClose}
      />

      {/* Slide-over Drawer Panel */}
      <div className="fixed inset-y-0 right-0 max-w-full flex pl-10">
        <aside className="w-screen max-w-md bg-white border-l border-[#E5E2DB] shadow-2xl flex flex-col h-full animate-in slide-in-from-right duration-250">
          {/* Drawer Header */}
          <div className="p-4 border-b border-[#EAE8E2] bg-[#FAF9F6] flex items-center justify-between gap-3">
            <div className="flex items-center gap-2.5">
              <div className="w-8 h-8 rounded-xl bg-[#E6F4F1] text-[#0B6E5F] flex items-center justify-center shadow-xs">
                <History className="w-4 h-4" />
              </div>
              <div>
                <div className="flex items-center gap-2">
                  <h3 className="text-base font-bold text-[#1C2024] tracking-tight">
                    Chat History
                  </h3>
                  {sessions.length > 0 && (
                    <span className="px-2 py-0.5 rounded-full text-[11px] font-semibold bg-[#EAE8E2] text-[#636A74]">
                      {sessions.length}
                    </span>
                  )}
                </div>
                <p className="text-[11px] text-[#636A74]">
                  Resume your previous conversations
                </p>
              </div>
            </div>

            <button
              type="button"
              onClick={onClose}
              className="p-1.5 rounded-lg text-[#636A74] hover:text-[#1C2024] hover:bg-[#EAE8E2] transition-colors cursor-pointer"
              title="Close Chat History"
            >
              <X className="w-4 h-4" />
            </button>
          </div>

          {/* User Account Info Bar (if logged in) */}
          {isAuthenticated && user && (
            <div className="px-4 py-2.5 bg-white border-b border-[#F2EFE9] flex items-center justify-between text-xs">
              <div className="flex items-center gap-2 min-w-0">
                <div className="w-6 h-6 rounded-full bg-[#0B6E5F] text-white text-[10px] font-bold flex items-center justify-center flex-shrink-0">
                  {user.name.charAt(0).toUpperCase()}
                </div>
                <div className="min-w-0">
                  <span className="font-semibold text-[#1C2024] truncate block">
                    {user.name}
                  </span>
                  <span className="text-[10px] text-[#8C939D] truncate block">
                    {user.email}
                  </span>
                </div>
              </div>
              <span className="text-[10px] font-semibold text-[#0B6E5F] bg-[#E6F4F1] px-2 py-0.5 rounded-full border border-[#BDE3DC]">
                Connected
              </span>
            </div>
          )}

          {/* Search Bar */}
          <div className="p-3 border-b border-[#EAE8E2] bg-white">
            <div className="relative">
              <Search className="w-3.5 h-3.5 text-[#8C939D] absolute left-3 top-1/2 -translate-y-1/2 pointer-events-none" />
              <input
                type="text"
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
                placeholder="Search conversations by title or repo..."
                className="w-full pl-8 pr-3 py-1.5 bg-[#FAF9F6] border border-[#E5E2DB] rounded-xl text-xs text-[#1C2024] placeholder-[#8C939D] focus:outline-none focus:ring-1 focus:ring-[#0B6E5F] focus:bg-white transition-all"
              />
            </div>
          </div>

          {/* Sessions List Content */}
          <div className="flex-1 overflow-y-auto p-3 space-y-2.5">
            {/* Non-authenticated prompt */}
            {!isAuthenticated && (
              <div className="p-3.5 rounded-xl bg-[#FAF9F6] border border-[#EAE8E2] text-xs space-y-2">
                <div className="flex items-center gap-2 text-[#1C2024] font-semibold">
                  <Sparkles className="w-3.5 h-3.5 text-[#0B6E5F]" />
                  <span>Sync your chats across devices</span>
                </div>
                <p className="text-[11px] text-[#636A74]">
                  Sign in to keep all your codebase conversations permanently synced to your account.
                </p>
                <button
                  type="button"
                  onClick={() => {
                    onClose();
                    onOpenAuth();
                  }}
                  className="w-full flex items-center justify-center gap-1.5 py-1.5 rounded-lg bg-[#0B6E5F] hover:bg-[#085247] text-white text-xs font-bold transition-all shadow-2xs cursor-pointer"
                >
                  <LogIn className="w-3 h-3" />
                  <span>Sign In</span>
                </button>
              </div>
            )}

            {filteredSessions.length > 0 ? (
              filteredSessions.map((item) => (
                <div
                  key={`${item.repo_id}-${item.sessionId}`}
                  onClick={() => handleResumeChat(item)}
                  className="group relative p-3 rounded-xl bg-white border border-[#E5E2DB] hover:border-[#0B6E5F]/50 hover:bg-[#FAF9F6] hover:shadow-xs transition-all cursor-pointer flex flex-col gap-2"
                >
                  {/* Top: Repo badge & Date */}
                  <div className="flex items-center justify-between gap-2 text-[11px]">
                    <div className="inline-flex items-center gap-1 px-2 py-0.5 rounded-md bg-[#FAF9F6] border border-[#EAE8E2] text-[#1C2024] font-medium max-w-[180px] truncate">
                      <FolderGit className="w-3 h-3 text-[#0B6E5F] flex-shrink-0" />
                      <span className="truncate">{item.repo_name}</span>
                    </div>

                    <div className="flex items-center gap-1 text-[#8C939D] font-mono text-[10px]">
                      <Clock className="w-3 h-3" />
                      <span>{formatRelativeDate(item.updatedAt)}</span>
                    </div>
                  </div>

                  {/* Title */}
                  <h4 className="text-xs font-bold text-[#1C2024] group-hover:text-[#0B6E5F] transition-colors line-clamp-1">
                    {item.title}
                  </h4>

                  {/* Message preview snippet */}
                  {item.lastMessagePreview && (
                    <p className="text-[11px] text-[#636A74] line-clamp-2 leading-relaxed">
                      &quot;{item.lastMessagePreview}&quot;
                    </p>
                  )}

                  {/* Footer: Turns + Resume action */}
                  <div className="flex items-center justify-between pt-1.5 border-t border-[#F2EFE9] text-[11px]">
                    <span className="text-[#8C939D] flex items-center gap-1 font-medium">
                      <MessageSquare className="w-3 h-3" />
                      {item.messageCount} {item.messageCount === 1 ? "turn" : "turns"}
                    </span>

                    <div className="flex items-center gap-2">
                      <button
                        type="button"
                        onClick={(e) => handleDeleteSession(e, item)}
                        className="p-1 rounded-md text-[#8C939D] hover:text-red-600 hover:bg-red-50 transition-colors opacity-0 group-hover:opacity-100 cursor-pointer"
                        title="Delete chat"
                      >
                        <Trash2 className="w-3 h-3" />
                      </button>

                      <span className="inline-flex items-center gap-1 font-bold text-[#0B6E5F] group-hover:translate-x-0.5 transition-transform text-xs">
                        Resume <ArrowRight className="w-3 h-3" />
                      </span>
                    </div>
                  </div>
                </div>
              ))
            ) : (
              <div className="py-12 px-4 text-center text-xs text-[#8C939D] space-y-2">
                <div className="w-10 h-10 rounded-full bg-[#FAF9F6] border border-[#EAE8E2] text-[#8C939D] flex items-center justify-center mx-auto">
                  <MessageSquare className="w-4 h-4" />
                </div>
                <p className="font-semibold text-[#1C2024]">
                  {searchQuery ? `No chats match "${searchQuery}"` : "No chat history found"}
                </p>
                <p className="text-[11px] text-[#636A74]">
                  {searchQuery
                    ? "Try a different search term"
                    : "Upload a repository to start your first conversation."}
                </p>
              </div>
            )}
          </div>

          {/* Drawer Footer: Simple Home Button */}
          <div className="p-3 border-t border-[#EAE8E2] bg-[#FAF9F6]">
            <button
              type="button"
              onClick={() => {
                onClose();
                onGoHome?.();
              }}
              className="w-full flex items-center justify-center gap-2 py-2.5 px-4 rounded-xl border border-[#D5D1C8] bg-white hover:bg-[#F2EFE9] text-xs font-bold text-[#1C2024] transition-all cursor-pointer shadow-2xs hover:border-[#0B6E5F]/50 group"
            >
              <Home className="w-4 h-4 text-[#0B6E5F] group-hover:scale-110 transition-transform" />
              <span>Home / Ingest New Repo</span>
            </button>
          </div>
        </aside>
      </div>
    </div>
  );
};
