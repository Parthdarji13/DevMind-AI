"use client";

import React, { useState, useEffect, useRef } from "react";
import {
  MessageSquare,
  Sparkles,
  Trash2,
  AlertCircle,
  GitMerge,
  FileText,
  Network,
  GraduationCap,
  Download,
  Mic,
  Radio,
} from "lucide-react";
import { IngestResponse, IngestionProgress, Citation, ChatMessage, SuggestedQuestion } from "@/lib/types";
import { askChatQuestionStream, getIngestionProgress, getSuggestedQuestions, ApiError } from "@/lib/api";
import { getStoredUser } from "@/lib/auth";
import { ChatSidebar } from "./ChatSidebar";
import { MessageItem, ChatMessageDisplay } from "./MessageItem";
import { ChatInput } from "./ChatInput";
import { EvidenceDrawer } from "./EvidenceDrawer";
import { SuggestedQuestions } from "./SuggestedQuestions";
import { FlowTraceModal } from "./FlowTraceModal";
import { OnboardingDocModal } from "./OnboardingDocModal";
import { ArchitectureMapModal } from "./ArchitectureMapModal";
import { LearningQuizModal } from "./LearningQuizModal";
import { VoiceConversationModal } from "./VoiceConversationModal";

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

  // Advanced Feature Modals
  const [isFlowTraceOpen, setIsFlowTraceOpen] = useState(false);
  const [isOnboardingOpen, setIsOnboardingOpen] = useState(false);
  const [isArchMapOpen, setIsArchMapOpen] = useState(false);
  const [isQuizOpen, setIsQuizOpen] = useState(false);
  const [isVoiceOpen, setIsVoiceOpen] = useState(false);

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
      .catch(() => { });
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
    const nowTime = new Date().toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" });
    const userMsgId = `msg-${Date.now()}-user`;
    const assistantMsgId = `msg-${Date.now()}-ast`;

    const userMsg: ChatMessageDisplay = {
      id: userMsgId,
      role: "user",
      content: question,
      timestamp: nowTime,
    };

    const initialAssistantMsg: ChatMessageDisplay = {
      id: assistantMsgId,
      role: "assistant",
      content: "",
      isStreaming: true,
      timestamp: nowTime,
    };

    // Add user message & streaming assistant placeholder
    setMessages((prev) => [...prev, userMsg, initialAssistantMsg]);
    setIsLoading(true);

    try {
      // Build conversation history for the backend
      const historyPayload: ChatMessage[] = messages.map((m) => ({
        role: m.role,
        content: m.content,
      }));

      const currentUser = getStoredUser();
      await askChatQuestionStream(
        {
          repo_id: repo.repo_id,
          question: question,
          history: historyPayload,
          session_id: sessionId,
          user_name: currentUser?.name || currentUser?.id || "Parth",
        },
        {
          onChunk: (token: string) => {
            setMessages((prev) =>
              prev.map((m) =>
                m.id === assistantMsgId
                  ? { ...m, content: m.content + token, isStreaming: true }
                  : m
              )
            );
          },
          onMetadata: (meta) => {
            if (meta.session_id) {
              setSessionId(meta.session_id);
            }
          },
          onDone: (res) => {
            if (res.session_id) {
              setSessionId(res.session_id);
            }
            setMessages((prev) =>
              prev.map((m) =>
                m.id === assistantMsgId
                  ? {
                    ...m,
                    content: res.answer || m.content,
                    citations: res.citations,
                    abstained: res.abstained,
                    inference_detected: res.inference_detected,
                    isStreaming: false,
                  }
                  : m
              )
            );
          },
          onError: (err) => {
            console.warn("Stream error encountered:", err);
          },
        }
      );
    } catch (err: unknown) {
      const msg = err instanceof ApiError ? err.message : "Failed to generate answer.";
      setError(msg);
      // Mark assistant message as finished if failed
      setMessages((prev) =>
        prev.map((m) =>
          m.id === assistantMsgId
            ? {
              ...m,
              content: m.content || "Unable to complete response. Please retry.",
              isStreaming: false,
            }
            : m
        )
      );
    } finally {
      setIsLoading(false);
    }
  };

  const handleClearChat = () => {
    setMessages([]);
    setSessionId(null);
    setError(null);
  };

  // Feature 10: Chat Export to Markdown
  const handleExportChat = () => {
    if (messages.length === 0) return;

    let md = `# DevMind AI — Conversation Transcript\n\n`;
    md += `- **Repository**: \`${repo.repo_name}\` (\`${repo.repo_id}\`)\n`;
    md += `- **Exported At**: ${new Date().toLocaleString()}\n`;
    md += `- **Total Messages**: ${messages.length}\n\n`;
    md += `---\n\n`;

    messages.forEach((m) => {
      const speaker = m.role === "user" ? "👤 User" : "🤖 DevMind AI";
      md += `### ${speaker} (${m.timestamp || "N/A"})\n\n`;
      md += `${m.content}\n\n`;

      if (m.citations && m.citations.length > 0) {
        md += `**Verified Citations:**\n`;
        m.citations.forEach((c) => {
          md += `- \`${c.file_path}:${c.start_line}-${c.end_line}\``;
          if (c.snippet) {
            md += ` — *${c.snippet.slice(0, 80).replace(/\n/g, " ")}*`;
          }
          md += `\n`;
        });
        md += `\n`;
      }

      md += `---\n\n`;
    });

    const blob = new Blob([md], { type: "text/markdown;charset=utf-8" });
    const url = URL.createObjectURL(blob);
    const link = document.createElement("a");
    const safeRepo = repo.repo_id.replace(/[^a-zA-Z0-9_-]/g, "_");
    link.href = url;
    link.download = `devmind_chat_${safeRepo}_${Date.now()}.md`;
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
    URL.revokeObjectURL(url);
  };

  const handleOpenDrawer = (citations: Citation[], initialIndex?: number) => {
    setDrawerCitations(citations);
    setDrawerInitialIndex(initialIndex ?? null);
    setIsDrawerOpen(true);
  };

  const handleSyncVoiceTurn = (question: string, spokenAnswer: string, citedFiles: string[]) => {
    const nowTime = new Date().toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" });
    const userMsgId = `voice-user-${Date.now()}`;
    const assistantMsgId = `voice-ast-${Date.now()}`;

    const userMsg: ChatMessageDisplay = {
      id: userMsgId,
      role: "user",
      content: `🎙️ ${question}`,
      timestamp: nowTime,
    };

    const assistantMsg: ChatMessageDisplay = {
      id: assistantMsgId,
      role: "assistant",
      content: spokenAnswer,
      citations: citedFiles.map((file) => ({
        file_path: file,
        start_line: 1,
        end_line: 1,
        snippet: "Referenced during live voice call.",
      })),
      timestamp: nowTime,
    };

    setMessages((prev) => [...prev, userMsg, assistantMsg]);
  };

  return (
    <div className="w-full max-w-7xl mx-auto flex flex-col lg:flex-row items-start gap-6 py-4">
      {/* Sidebar Overview */}
      <ChatSidebar repo={repo} progress={progress} onNewRepo={onNewRepo} />

      {/* Main Chat Panel */}
      <section className="flex-1 w-full bg-white border border-[#E5E2DB] rounded-2xl shadow-sm flex flex-col h-[760px] overflow-hidden">
        {/* Chat Thread Header */}
        <div className="px-5 py-3 border-b border-[#EAE8E2] bg-[#FAF9F6] flex flex-wrap items-center justify-between gap-3">
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

          {/* Action Bar: Voice Call, Flow Trace, Onboarding, Architecture Map, Quiz, Export */}
          <div className="flex items-center flex-wrap gap-1.5">
            <button
              type="button"
              onClick={() => setIsVoiceOpen(true)}
              className="inline-flex items-center gap-1.5 px-3 py-1 text-xs font-semibold rounded-lg text-white bg-gradient-to-r from-[#0B6E5F] to-[#085247] hover:from-[#095b4e] hover:to-[#064239] transition-all cursor-pointer shadow-xs"
              title="Open hands-free real-time Voice Call"
            >
              <Radio className="w-3.5 h-3.5 text-white animate-pulse" />
              <span>Voice Call</span>
            </button>

            <button
              type="button"
              onClick={() => setIsFlowTraceOpen(true)}
              className="inline-flex items-center gap-1 px-2.5 py-1 text-xs font-medium rounded-lg text-[#1C2024] bg-white border border-[#E5E2DB] hover:bg-[#F2EFE9] transition-colors cursor-pointer shadow-xs"
              title="Trace multi-step code execution path"
            >
              <GitMerge className="w-3.5 h-3.5 text-[#0B6E5F]" />
              <span className="hidden sm:inline">Trace Flow</span>
            </button>

            <button
              type="button"
              onClick={() => setIsOnboardingOpen(true)}
              className="inline-flex items-center gap-1 px-2.5 py-1 text-xs font-medium rounded-lg text-[#1C2024] bg-white border border-[#E5E2DB] hover:bg-[#F2EFE9] transition-colors cursor-pointer shadow-xs"
              title="Generate comprehensive onboarding and architecture guide"
            >
              <FileText className="w-3.5 h-3.5 text-[#0B6E5F]" />
              <span className="hidden sm:inline">Onboarding Doc</span>
            </button>

            <button
              type="button"
              onClick={() => setIsArchMapOpen(true)}
              className="inline-flex items-center gap-1 px-2.5 py-1 text-xs font-medium rounded-lg text-[#1C2024] bg-white border border-[#E5E2DB] hover:bg-[#F2EFE9] transition-colors cursor-pointer shadow-xs"
              title="Inspect architectural module dependency map"
            >
              <Network className="w-3.5 h-3.5 text-[#0B6E5F]" />
              <span className="hidden sm:inline">Arch Map</span>
            </button>

            <button
              type="button"
              onClick={() => setIsQuizOpen(true)}
              className="inline-flex items-center gap-1 px-2.5 py-1 text-xs font-medium rounded-lg text-[#1C2024] bg-white border border-[#E5E2DB] hover:bg-[#F2EFE9] transition-colors cursor-pointer shadow-xs"
              title="Take interactive codebase quiz"
            >
              <GraduationCap className="w-3.5 h-3.5 text-[#0B6E5F]" />
              <span className="hidden sm:inline">Quiz</span>
            </button>

            {messages.length > 0 && (
              <>
                <button
                  type="button"
                  onClick={handleExportChat}
                  className="inline-flex items-center gap-1 px-2.5 py-1 text-xs font-semibold rounded-lg text-[#0B6E5F] bg-[#E6F4F1] hover:bg-[#D2EDE7] border border-[#BDE3DC] transition-colors cursor-pointer shadow-xs"
                  title="Export conversation thread to Markdown file"
                >
                  <Download className="w-3.5 h-3.5" />
                  <span className="hidden sm:inline">Export</span>
                </button>

                <button
                  type="button"
                  onClick={handleClearChat}
                  className="flex items-center gap-1 px-2 py-1 text-xs font-semibold rounded-lg text-[#636A74] hover:text-red-700 hover:bg-red-50 transition-colors cursor-pointer ml-1"
                  title="Clear conversation history"
                >
                  <Trash2 className="w-3.5 h-3.5" />
                </button>
              </>
            )}
          </div>
        </div>

        {/* Messages Scroll Area */}
        <div className="flex-1 overflow-y-auto p-5 sm:p-6 space-y-6">
          {messages.length === 0 ? (
            /* Empty State / Starter Questions */
            <div className="w-full max-w-2xl mx-auto py-2 sm:py-4 flex flex-col items-center text-center space-y-4">
              <div className="w-12 h-12 rounded-2xl bg-[#E6F4F1] text-[#0B6E5F] flex items-center justify-center shadow-xs">
                <Sparkles className="w-6 h-6" />
              </div>

              <div className="space-y-1 max-w-lg">
                <h3 className="text-base sm:text-lg font-bold text-[#1C2024]">
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
                  repoId={repo.repo_id}
                  sessionId={sessionId}
                  onOpenDrawer={handleOpenDrawer}
                />
              ))}

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
          <ChatInput
            onSendMessage={handleSendMessage}
            isLoading={isLoading}
            onOpenVoiceCall={() => setIsVoiceOpen(true)}
          />
        </div>
      </section>

      {/* Slide-over Evidence Drawer */}
      <EvidenceDrawer
        citations={drawerCitations}
        isOpen={isDrawerOpen}
        onClose={() => setIsDrawerOpen(false)}
        activeCitationIndex={drawerInitialIndex}
      />

      {/* Feature 8: Execution Flow Trace Modal */}
      <FlowTraceModal
        repoId={repo.repo_id}
        isOpen={isFlowTraceOpen}
        onClose={() => setIsFlowTraceOpen(false)}
        onSelectQuery={(q) => handleSendMessage(q)}
      />

      {/* Feature 9: Onboarding Doc Modal */}
      <OnboardingDocModal
        repoId={repo.repo_id}
        repoName={repo.repo_name}
        isOpen={isOnboardingOpen}
        onClose={() => setIsOnboardingOpen(false)}
      />

      {/* Feature 11: Architecture Dependency Map Modal */}
      <ArchitectureMapModal
        repoId={repo.repo_id}
        repoName={repo.repo_name}
        isOpen={isArchMapOpen}
        onClose={() => setIsArchMapOpen(false)}
        onSelectQuestion={(q) => handleSendMessage(q)}
      />

      {/* Feature 12: Learning Quiz Modal */}
      <LearningQuizModal
        repoId={repo.repo_id}
        repoName={repo.repo_name}
        isOpen={isQuizOpen}
        onClose={() => setIsQuizOpen(false)}
        onSelectQuestion={(q) => handleSendMessage(q)}
      />

      {/* Feature 13: Dedicated Voice Conversation Modal */}
      <VoiceConversationModal
        repo={repo}
        history={messages.map((m) => ({ role: m.role, content: m.content }))}
        isOpen={isVoiceOpen}
        onClose={() => setIsVoiceOpen(false)}
        onSyncTurn={handleSyncVoiceTurn}
      />
    </div>
  );
};
