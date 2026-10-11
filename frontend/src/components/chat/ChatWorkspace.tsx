"use client";

import React, { useState, useEffect, useRef } from "react";
import {
  MessageSquare,
  Sparkles,
  Loader2,
  Trash2,
  AlertCircle,
} from "lucide-react";
import { IngestResponse, IngestionProgress, Citation, ChatMessage, SuggestedQuestion } from "@/lib/types";
import { askChatQuestion, getIngestionProgress, getSuggestedQuestions, ApiError } from "@/lib/api";
import { ChatSidebar } from "./ChatSidebar";
import { MessageItem, ChatMessageDisplay } from "./MessageItem";
import { ChatInput } from "./ChatInput";
import { EvidenceDrawer } from "./EvidenceDrawer";
import { SuggestedQuestions } from "./SuggestedQuestions";

interface ChatWorkspaceProps {
  repo: IngestResponse;
  onNewRepo: () => void;
}

export const ChatWorkspace: React.FC<ChatWorkspaceProps> = ({
  repo,
  onNewRepo,
}) => {
  const [messages, setMessages] = useState<ChatMessageDisplay[]>([]);
  const [sessionId, setSessionId] = useState<string | null>(null);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [progress, setProgress] = useState<IngestionProgress | null>(null);

  // Evidence Drawer state
  const [drawerCitations, setDrawerCitations] = useState<Citation[]>([]);
  const [isDrawerOpen, setIsDrawerOpen] = useState(false);
  const [drawerInitialIndex, setDrawerInitialIndex] = useState<number | null>(null);

  // Suggested inquiries state (Step 29)
  const [suggestions, setSuggestions] = useState<SuggestedQuestion[]>([]);
  const [isSuggestionsLoading, setIsSuggestionsLoading] = useState(true);

  const messagesEndRef = useRef<HTMLDivElement>(null);

  // Load progress details for the sidebar on mount
  useEffect(() => {
    let mounted = true;
    getIngestionProgress(repo.repo_id)
      .then((p) => {
        if (mounted) setProgress(p);
      })
      .catch(() => {});
    return () => {
      mounted = false;
    };
  }, [repo.repo_id]);

  // Fetch repository-derived suggested questions (Step 29)
  useEffect(() => {
    let mounted = true;
    getSuggestedQuestions(repo.repo_id)
      .then((res) => {
        if (mounted && res.suggestions && res.suggestions.length > 0) {
          setSuggestions(res.suggestions);
        }
      })
      .catch((err) => {
        console.warn("Could not fetch repository-derived suggestions:", err);
      })
      .finally(() => {
        if (mounted) setIsSuggestionsLoading(false);
      });

    return () => {
      mounted = false;
    };
  }, [repo.repo_id]);

  // Smooth scroll to bottom when messages update
  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages, isLoading]);

  const handleSendMessage = async (question: string) => {
    setError(null);
    const userMsg: ChatMessageDisplay = {
      id: `msg-${Date.now()}-user`,
      role: "user",
      content: question,
      timestamp: new Date().toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" }),
    };

    setMessages((prev) => [...prev, userMsg]);
    setIsLoading(true);

    try {
      // Build conversation history for the backend
      const historyPayload: ChatMessage[] = messages.map((m) => ({
        role: m.role,
        content: m.content,
      }));

      const res = await askChatQuestion({
        repo_id: repo.repo_id,
        question: question,
        history: historyPayload,
        session_id: sessionId,
      });

      if (res.session_id) {
        setSessionId(res.session_id);
      }

      const assistantMsg: ChatMessageDisplay = {
        id: `msg-${Date.now()}-ast`,
        role: "assistant",
        content: res.answer,
        citations: res.citations,
        abstained: res.abstained,
        inference_detected: res.inference_detected,
        timestamp: new Date().toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" }),
      };

      setMessages((prev) => [...prev, assistantMsg]);
    } catch (err: unknown) {
      const msg = err instanceof ApiError ? err.message : "Failed to generate answer.";
      setError(msg);
    } finally {
      setIsLoading(false);
    }
  };

  const handleClearChat = () => {
    setMessages([]);
    setSessionId(null);
    setError(null);
  };

  const handleOpenDrawer = (citations: Citation[], initialIndex?: number) => {
    setDrawerCitations(citations);
    setDrawerInitialIndex(initialIndex ?? null);
    setIsDrawerOpen(true);
  };

  return (
    <div className="w-full max-w-7xl mx-auto flex flex-col lg:flex-row items-start gap-6 py-4">
      {/* Sidebar Overview */}
      <ChatSidebar repo={repo} progress={progress} onNewRepo={onNewRepo} />

      {/* Main Chat Panel */}
      <section className="flex-1 w-full bg-white border border-[#E5E2DB] rounded-2xl shadow-sm flex flex-col h-[760px] overflow-hidden">
        {/* Chat Thread Header */}
        <div className="px-5 py-3.5 border-b border-[#EAE8E2] bg-[#FAF9F6] flex items-center justify-between">
          <div className="flex items-center gap-2">
            <div className="w-7 h-7 rounded-lg bg-[#E6F4F1] text-[#0B6E5F] flex items-center justify-center">
              <MessageSquare className="w-4 h-4" />
            </div>
            <div>
              <h3 className="text-sm font-bold text-[#1C2024] leading-tight">
                Conversation Thread
              </h3>
              <p className="text-[11px] text-[#636A74]">
                Multi-turn grounded QA with verified citations
              </p>
            </div>
          </div>

          {messages.length > 0 && (
            <button
              type="button"
              onClick={handleClearChat}
              className="flex items-center gap-1.5 px-2.5 py-1 text-xs font-semibold rounded-lg text-[#636A74] hover:text-red-700 hover:bg-red-50 transition-colors cursor-pointer"
              title="Clear conversation history"
            >
              <Trash2 className="w-3.5 h-3.5" />
              <span>Clear</span>
            </button>
          )}
        </div>

        {/* Messages Scroll Area */}
        <div className="flex-1 overflow-y-auto p-5 sm:p-6 space-y-6">
          {messages.length === 0 ? (
            /* Empty State / Starter Questions */
            <div className="h-full flex flex-col items-center justify-center text-center max-w-lg mx-auto py-12 space-y-6">
              <div className="w-14 h-14 rounded-2xl bg-[#E6F4F1] text-[#0B6E5F] flex items-center justify-center shadow-xs">
                <Sparkles className="w-7 h-7" />
              </div>

              <div className="space-y-1.5">
                <h3 className="text-lg font-bold text-[#1C2024]">
                  Ask your codebase anything
                </h3>
                <p className="text-xs text-[#636A74] leading-relaxed">
                  DevMind retrieves hybrid BM25 and vector evidence before generating answers with verified line numbers.
                </p>
              </div>

              {/* Step 29: Repository-derived suggested inquiries */}
              <SuggestedQuestions
                suggestions={suggestions}
                isLoading={isSuggestionsLoading}
                onSelectQuestion={handleSendMessage}
              />
            </div>
          ) : (
            /* Conversation messages */
            <>
              {messages.map((msg) => (
                <MessageItem
                  key={msg.id}
                  message={msg}
                  onOpenDrawer={handleOpenDrawer}
                />
              ))}

              {/* Loading thinking state */}
              {isLoading && (
                <div className="flex items-center gap-3 p-4 rounded-xl bg-[#FAF9F6] border border-[#EAE8E2] text-xs text-[#0B6E5F] max-w-md animate-pulse">
                  <Loader2 className="w-4 h-4 animate-spin text-[#0B6E5F]" />
                  <span>Retrieving codebase evidence & synthesizing cited response...</span>
                </div>
              )}

              {/* Error callout */}
              {error && (
                <div className="flex items-center gap-2 p-3.5 rounded-xl bg-red-50 border border-red-200 text-xs text-red-800">
                  <AlertCircle className="w-4 h-4 text-red-600 flex-shrink-0" />
                  <span>{error}</span>
                </div>
              )}

              <div ref={messagesEndRef} />
            </>
          )}
        </div>

        {/* Input Bar pinned to bottom */}
        <div className="p-4 border-t border-[#EAE8E2] bg-white">
          <ChatInput onSendMessage={handleSendMessage} isLoading={isLoading} />
        </div>
      </section>

      {/* Slide-over Evidence Drawer */}
      <EvidenceDrawer
        citations={drawerCitations}
        isOpen={isDrawerOpen}
        onClose={() => setIsDrawerOpen(false)}
        activeCitationIndex={drawerInitialIndex}
      />
    </div>
  );
};
