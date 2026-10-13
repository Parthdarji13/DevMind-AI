"use client";

import React, { useState } from "react";
import {
  Plus,
  MessageSquare,
  Search,
  Edit2,
  Trash2,
  Check,
  X,
  PanelLeftClose,
  PanelLeftOpen,
  Calendar,
  Layers,
  Sparkles,
  History,
} from "lucide-react";
import { IngestResponse, ChatSession } from "@/lib/types";

interface ChatSidebarProps {
  repo: IngestResponse;
  sessions: ChatSession[];
  activeSessionId: string | null;
  onSelectSession: (sessionId: string) => void;
  onNewChat: () => void;
  onRenameSession: (sessionId: string, newTitle: string) => void;
  onDeleteSession: (sessionId: string) => void;
  isCollapsed: boolean;
  onToggleCollapse: () => void;
}

// Helper to format timestamps nicely (e.g. "Just now", "2h ago", "Yesterday", "Oct 12")
function formatSessionDate(timestamp: number): string {
  const now = Date.now();
  const diffMs = now - timestamp;
  const diffMins = Math.floor(diffMs / (1000 * 60));
  const diffHours = Math.floor(diffMs / (1000 * 60 * 60));
  const diffDays = Math.floor(diffMs / (1000 * 60 * 60 * 24));

  if (diffMins < 2) return "Just now";
  if (diffMins < 60) return `${diffMins}m ago`;
  if (diffHours < 24) return `${diffHours}h ago`;
  if (diffDays === 1) return "Yesterday";
  if (diffDays < 7) return `${diffDays}d ago`;

  return new Date(timestamp).toLocaleDateString([], { month: "short", day: "numeric" });
}

export const ChatSidebar: React.FC<ChatSidebarProps> = ({
  repo,
  sessions,
  activeSessionId,
  onSelectSession,
  onNewChat,
  onRenameSession,
  onDeleteSession,
  isCollapsed,
  onToggleCollapse,
}) => {
  const [searchQuery, setSearchQuery] = useState("");
  const [editingSessionId, setEditingSessionId] = useState<string | null>(null);
  const [editTitleInput, setEditTitleInput] = useState("");

  // Filter sessions by search query
  const filteredSessions = sessions.filter((s) => {
    if (!searchQuery.trim()) return true;
    return s.title.toLowerCase().includes(searchQuery.toLowerCase());
  });

  const handleStartRename = (e: React.MouseEvent, s: ChatSession) => {
    e.stopPropagation();
    setEditingSessionId(s.id);
    setEditTitleInput(s.title);
  };

  const handleSaveRename = (e?: React.MouseEvent | React.FormEvent, sessionId?: string) => {
    if (e) e.stopPropagation();
    const id = sessionId || editingSessionId;
    if (id && editTitleInput.trim()) {
      onRenameSession(id, editTitleInput.trim());
    }
    setEditingSessionId(null);
    setEditTitleInput("");
  };

  const handleCancelRename = (e: React.MouseEvent) => {
    e.stopPropagation();
    setEditingSessionId(null);
    setEditTitleInput("");
  };

  const handleDelete = (e: React.MouseEvent, sessionId: string) => {
    e.stopPropagation();
    if (window.confirm("Are you sure you want to delete this chat session?")) {
      onDeleteSession(sessionId);
    }
  };

  // If collapsed, render slim vertical launcher bar
  if (isCollapsed) {
    return (
      <aside className="w-14 flex-shrink-0 flex flex-col items-center py-4 bg-white border border-[#E5E2DB] rounded-2xl shadow-xs space-y-4">
        <button
          type="button"
          onClick={onToggleCollapse}
          className="p-2 rounded-xl hover:bg-[#F2EFE9] text-[#0B6E5F] transition-colors cursor-pointer"
          title="Expand Chat History Panel"
        >
          <PanelLeftOpen className="w-5 h-5" />
        </button>

        <div className="w-8 h-px bg-[#EAE8E2]" />

        <button
          type="button"
          onClick={onNewChat}
          className="p-2.5 rounded-xl bg-[#E6F4F1] hover:bg-[#D2EDE7] text-[#0B6E5F] transition-colors cursor-pointer shadow-2xs"
          title="New Chat"
        >
          <Plus className="w-4 h-4" />
        </button>

        <div className="flex-1" />

        <div className="text-[10px] font-mono text-[#8C939D] rotate-90 pb-2">
          {sessions.length} chats
        </div>
      </aside>
    );
  }

  return (
    <aside className="w-full lg:w-[320px] flex-shrink-0 bg-white border border-[#E5E2DB] rounded-2xl shadow-sm flex flex-col h-[760px] overflow-hidden transition-all">
      {/* 1. Header: Chat History & Collapse Toggle */}
      <div className="p-3 border-b border-[#EAE8E2] bg-[#FAF9F6] flex items-center justify-between gap-2">
        <div className="flex items-center gap-2">
          <div className="w-6 h-6 rounded-lg bg-[#E6F4F1] text-[#0B6E5F] flex items-center justify-center">
            <History className="w-3.5 h-3.5" />
          </div>
          <span className="text-xs font-bold text-[#1C2024] tracking-tight">
            Chat History
          </span>
          <span className="px-1.5 py-0.5 rounded-full text-[10px] font-semibold bg-[#EAE8E2] text-[#636A74]">
            {sessions.length}
          </span>
        </div>

        <button
          type="button"
          onClick={onToggleCollapse}
          className="p-1.5 rounded-lg text-[#636A74] hover:text-[#0B6E5F] hover:bg-[#ECE9E3] transition-colors cursor-pointer"
          title="Collapse Chat History"
        >
          <PanelLeftClose className="w-4 h-4" />
        </button>
      </div>

      {/* 2. Primary Action: + New Chat Button */}
      <div className="p-3 border-b border-[#EAE8E2] bg-white space-y-2">
        <button
          type="button"
          onClick={onNewChat}
          className="w-full flex items-center justify-center gap-2 py-2.5 px-3 rounded-xl bg-gradient-to-r from-[#0B6E5F] to-[#085247] hover:from-[#095b4e] hover:to-[#064239] text-white text-xs font-bold transition-all shadow-xs cursor-pointer group"
        >
          <Plus className="w-4 h-4 group-hover:rotate-90 transition-transform" />
          <span>New Chat</span>
        </button>

        {/* Search Bar for past chats */}
        {sessions.length > 3 && (
          <div className="relative">
            <Search className="w-3.5 h-3.5 text-[#8C939D] absolute left-3 top-1/2 -translate-y-1/2 pointer-events-none" />
            <input
              type="text"
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              placeholder="Search chat history..."
              className="w-full pl-8 pr-3 py-1.5 bg-[#FAF9F6] border border-[#E5E2DB] rounded-lg text-xs text-[#1C2024] placeholder-[#8C939D] focus:outline-none focus:ring-1 focus:ring-[#0B6E5F] focus:bg-white transition-all"
            />
          </div>
        )}
      </div>

      {/* 3. Chat History List */}
      <div className="flex-1 overflow-y-auto p-2 space-y-1">
        <div className="px-2 pt-1 pb-1.5 flex items-center justify-between text-[11px] font-bold uppercase tracking-wider text-[#636A74]">
          <span>Chat History</span>
          <span className="font-mono text-[10px] text-[#8C939D]">
            {filteredSessions.length} {filteredSessions.length === 1 ? "thread" : "threads"}
          </span>
        </div>

        {filteredSessions.length === 0 ? (
          <div className="py-12 px-4 text-center text-xs text-[#8C939D] space-y-2">
            <div className="w-9 h-9 rounded-full bg-[#FAF9F6] border border-[#EAE8E2] text-[#8C939D] flex items-center justify-center mx-auto">
              <MessageSquare className="w-4 h-4" />
            </div>
            <p className="font-medium text-[#1C2024]">No chat history found</p>
            <p className="text-[11px]">Start a new conversation to begin exploring the codebase!</p>
          </div>
        ) : (
          filteredSessions.map((session) => {
            const isActive = session.id === activeSessionId;
            const isEditing = editingSessionId === session.id;
            const msgCount = session.messages?.length || 0;

            return (
              <div
                key={session.id}
                onClick={() => {
                  if (!isEditing) onSelectSession(session.id);
                }}
                className={`group relative w-full rounded-xl px-3 py-2.5 transition-all text-left cursor-pointer flex items-start gap-2.5 border ${
                  isActive
                    ? "bg-[#E6F4F1] border-[#BDE3DC] shadow-2xs"
                    : "bg-white border-transparent hover:bg-[#FAF9F6] hover:border-[#EAE8E2]"
                }`}
              >
                {/* Chat Icon */}
                <div
                  className={`mt-0.5 w-6 h-6 rounded-lg flex items-center justify-center flex-shrink-0 transition-colors ${
                    isActive ? "bg-[#0B6E5F] text-white" : "bg-[#FAF9F6] text-[#636A74] group-hover:text-[#0B6E5F]"
                  }`}
                >
                  <MessageSquare className="w-3.5 h-3.5" />
                </div>

                {/* Content Area */}
                <div className="flex-1 min-w-0 pr-1">
                  {isEditing ? (
                    /* Inline Title Editing Mode */
                    <form
                      onSubmit={(e) => {
                        e.preventDefault();
                        handleSaveRename(e, session.id);
                      }}
                      onClick={(e) => e.stopPropagation()}
                      className="flex items-center gap-1 mt-0.5"
                    >
                      <input
                        type="text"
                        autoFocus
                        value={editTitleInput}
                        onChange={(e) => setEditTitleInput(e.target.value)}
                        onKeyDown={(e) => {
                          if (e.key === "Escape") handleCancelRename(e as any);
                        }}
                        className="w-full text-xs font-semibold px-2 py-1 bg-white border border-[#0B6E5F] rounded-md focus:outline-none text-[#1C2024]"
                      />
                      <button
                        type="submit"
                        className="p-1 rounded bg-[#0B6E5F] text-white hover:bg-[#095b4e] transition-colors"
                        title="Save title"
                      >
                        <Check className="w-3 h-3" />
                      </button>
                      <button
                        type="button"
                        onClick={handleCancelRename}
                        className="p-1 rounded bg-[#EAE8E2] text-[#636A74] hover:bg-[#D5D1C8] transition-colors"
                        title="Cancel"
                      >
                        <X className="w-3 h-3" />
                      </button>
                    </form>
                  ) : (
                    /* Display Mode */
                    <>
                      <div
                        className={`text-xs font-semibold truncate leading-snug ${
                          isActive ? "text-[#0B6E5F]" : "text-[#1C2024]"
                        }`}
                        title={session.title}
                      >
                        {session.title || "Untitled Chat"}
                      </div>

                      <div className="flex items-center gap-2 mt-1 text-[10px] text-[#8C939D]">
                        <span className="flex items-center gap-1 font-mono">
                          <Calendar className="w-2.5 h-2.5" />
                          <span>{formatSessionDate(session.updatedAt || session.createdAt)}</span>
                        </span>
                        <span>•</span>
                        <span>{msgCount} {msgCount === 1 ? "msg" : "msgs"}</span>
                      </div>
                    </>
                  )}
                </div>

                {/* Action Buttons: Rename & Delete (visible on hover or when active) */}
                {!isEditing && (
                  <div
                    className={`flex items-center gap-0.5 transition-opacity ${
                      isActive ? "opacity-100" : "opacity-0 group-hover:opacity-100"
                    }`}
                  >
                    <button
                      type="button"
                      onClick={(e) => handleStartRename(e, session)}
                      className="p-1.5 rounded-md hover:bg-white text-[#636A74] hover:text-[#0B6E5F] transition-colors cursor-pointer"
                      title="Rename chat title"
                    >
                      <Edit2 className="w-3 h-3" />
                    </button>

                    <button
                      type="button"
                      onClick={(e) => handleDelete(e, session.id)}
                      className="p-1.5 rounded-md hover:bg-red-50 text-[#636A74] hover:text-red-600 transition-colors cursor-pointer"
                      title="Delete chat thread"
                    >
                      <Trash2 className="w-3 h-3" />
                    </button>
                  </div>
                )}
              </div>
            );
          })
        )}
      </div>

      {/* 4. Footer: Repository Status & Citations Grounding Info */}
      <div className="p-3 border-t border-[#EAE8E2] bg-[#FAF9F6] flex items-center justify-between text-[11px] text-[#636A74]">
        <div className="flex items-center gap-1.5 min-w-0">
          <span className="w-2 h-2 rounded-full bg-emerald-500 flex-shrink-0" />
          <span className="font-semibold text-[#1C2024] truncate" title={repo.repo_name}>
            {repo.repo_name}
          </span>
        </div>
        <span className="text-[10px] text-emerald-700 bg-emerald-50 px-2 py-0.5 rounded-full font-semibold border border-emerald-200 flex-shrink-0">
          Active
        </span>
      </div>
    </aside>
  );
};
