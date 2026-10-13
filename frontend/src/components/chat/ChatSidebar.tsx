"use client";

import React, { useState, useEffect, useMemo } from "react";
import {
  FileCode2,
  FolderTree,
  Sparkles,
  Radio,
  GitMerge,
  FileText,
  Network,
  GraduationCap,
  RotateCcw,
  Plus,
  Search,
  ChevronRight,
  ChevronDown,
  MessageSquare,
  ShieldAlert,
  Bug,
  HelpCircle,
  FileSearch,
  PanelLeftClose,
  PanelLeftOpen,
  Download,
  Terminal,
  Layers,
  ArrowRight,
} from "lucide-react";
import { IngestResponse, RepoFileInfo } from "@/lib/types";
import { getRepoFiles } from "@/lib/api";

interface ChatSidebarProps {
  repo: IngestResponse;
  onNewRepo: () => void;
  onSelectPrompt: (prompt: string) => void;
  onNewChat: () => void;
  onOpenVoiceCall: () => void;
  onOpenFlowTrace: () => void;
  onOpenOnboarding: () => void;
  onOpenArchMap: () => void;
  onOpenQuiz: () => void;
  onExportChat?: () => void;
  recentQuestions?: string[];
  isCollapsed: boolean;
  onToggleCollapse: () => void;
}

type TabType = "files" | "tools" | "chat";

// Helper to pick file icon color based on extension
function getFileBadgeColor(fileName: string): { bg: string; text: string } {
  const ext = fileName.split(".").pop()?.toLowerCase() || "";
  switch (ext) {
    case "ts":
    case "tsx":
      return { bg: "bg-blue-50 text-blue-700 border-blue-200", text: "text-blue-600" };
    case "js":
    case "jsx":
      return { bg: "bg-amber-50 text-amber-700 border-amber-200", text: "text-amber-600" };
    case "py":
      return { bg: "bg-emerald-50 text-emerald-700 border-emerald-200", text: "text-emerald-600" };
    case "html":
      return { bg: "bg-orange-50 text-orange-700 border-orange-200", text: "text-orange-600" };
    case "css":
      return { bg: "bg-cyan-50 text-cyan-700 border-cyan-200", text: "text-cyan-600" };
    case "json":
      return { bg: "bg-yellow-50 text-yellow-700 border-yellow-200", text: "text-yellow-600" };
    case "md":
      return { bg: "bg-purple-50 text-purple-700 border-purple-200", text: "text-purple-600" };
    case "sql":
      return { bg: "bg-rose-50 text-rose-700 border-rose-200", text: "text-rose-600" };
    default:
      return { bg: "bg-gray-50 text-gray-700 border-gray-200", text: "text-gray-600" };
  }
}

export const ChatSidebar: React.FC<ChatSidebarProps> = ({
  repo,
  onNewRepo,
  onSelectPrompt,
  onNewChat,
  onOpenVoiceCall,
  onOpenFlowTrace,
  onOpenOnboarding,
  onOpenArchMap,
  onOpenQuiz,
  onExportChat,
  recentQuestions = [],
  isCollapsed,
  onToggleCollapse,
}) => {
  const [activeTab, setActiveTab] = useState<TabType>("files");
  const [files, setFiles] = useState<RepoFileInfo[]>([]);
  const [fileSearch, setFileSearch] = useState<string>("");
  const [expandedFile, setExpandedFile] = useState<string | null>(null);
  const [isLoadingFiles, setIsLoadingFiles] = useState<boolean>(false);

  // Load indexed files for the interactive explorer
  useEffect(() => {
    let isMounted = true;
    async function loadFiles() {
      setIsLoadingFiles(true);
      try {
        const res = await getRepoFiles(repo.repo_id);
        if (isMounted) {
          setFiles(res.files || []);
        }
      } catch (err) {
        console.warn("Could not load repo files for sidebar:", err);
      } finally {
        if (isMounted) setIsLoadingFiles(false);
      }
    }
    loadFiles();
    return () => {
      isMounted = false;
    };
  }, [repo.repo_id]);

  // Filtered files list based on search
  const filteredFiles = useMemo(() => {
    if (!fileSearch.trim()) return files;
    const q = fileSearch.toLowerCase();
    return files.filter((f) => f.file_path.toLowerCase().includes(q));
  }, [files, fileSearch]);

  // Quick Action cards for AI Tools tab
  const aiTools = [
    {
      id: "voice",
      title: "Voice Conversation Mode",
      desc: "Speak naturally hands-free with neural Indian & US voices",
      icon: Radio,
      badge: "Live Audio",
      color: "from-emerald-600 to-teal-700 text-white",
      onClick: onOpenVoiceCall,
    },
    {
      id: "flow",
      title: "Execution Flow Tracer",
      desc: "Generate Mermaid sequence diagrams of code execution",
      icon: GitMerge,
      badge: "Diagrams",
      color: "bg-white text-[#1C2024] hover:bg-[#F9F8F6] border-[#E5E2DB]",
      onClick: onOpenFlowTrace,
    },
    {
      id: "onboard",
      title: "Onboarding Architecture Doc",
      desc: "Synthesize full system architecture & module overview",
      icon: FileText,
      badge: "Docs",
      color: "bg-white text-[#1C2024] hover:bg-[#F9F8F6] border-[#E5E2DB]",
      onClick: onOpenOnboarding,
    },
    {
      id: "arch",
      title: "Architecture Dependency Map",
      desc: "Explore visual dependency graph of modules and imports",
      icon: Network,
      badge: "Graph",
      color: "bg-white text-[#1C2024] hover:bg-[#F9F8F6] border-[#E5E2DB]",
      onClick: onOpenArchMap,
    },
    {
      id: "quiz",
      title: "Interactive Codebase Quiz",
      desc: "Test your comprehension with grounded code challenges",
      icon: GraduationCap,
      badge: "Learning",
      color: "bg-white text-[#1C2024] hover:bg-[#F9F8F6] border-[#E5E2DB]",
      onClick: onOpenQuiz,
    },
  ];

  // Curated 1-click prompts
  const curatedPrompts = [
    {
      label: "Project Overview",
      query: "Explain what this project does, its architecture, and main tech stack.",
    },
    {
      label: "API Endpoints",
      query: "List all API endpoints and routes defined in this codebase.",
    },
    {
      label: "Authentication Flow",
      query: "How does user authentication and access control work in this project?",
    },
    {
      label: "Database & Models",
      query: "Explain the database models, schemas, and storage structure used here.",
    },
    {
      label: "Main Entrypoint",
      query: "Trace the execution starting from the main application entrypoint.",
    },
  ];

  // If collapsed, render slim vertical launcher bar
  if (isCollapsed) {
    return (
      <aside className="w-14 flex-shrink-0 flex flex-col items-center py-4 bg-white border border-[#E5E2DB] rounded-2xl shadow-xs space-y-4">
        <button
          type="button"
          onClick={onToggleCollapse}
          className="p-2 rounded-xl hover:bg-[#F2EFE9] text-[#0B6E5F] transition-colors cursor-pointer"
          title="Expand AI Workspace Panel"
        >
          <PanelLeftOpen className="w-5 h-5" />
        </button>

        <div className="w-8 h-px bg-[#EAE8E2]" />

        <button
          type="button"
          onClick={() => {
            setActiveTab("files");
            onToggleCollapse();
          }}
          className="p-2 rounded-xl hover:bg-[#F2EFE9] text-[#636A74] hover:text-[#0B6E5F] transition-colors cursor-pointer"
          title="Open Files Explorer"
        >
          <FolderTree className="w-4 h-4" />
        </button>

        <button
          type="button"
          onClick={() => {
            setActiveTab("tools");
            onToggleCollapse();
          }}
          className="p-2 rounded-xl hover:bg-[#F2EFE9] text-[#636A74] hover:text-[#0B6E5F] transition-colors cursor-pointer"
          title="Open AI Tools Hub"
        >
          <Sparkles className="w-4 h-4" />
        </button>

        <button
          type="button"
          onClick={() => {
            setActiveTab("chat");
            onToggleCollapse();
          }}
          className="p-2 rounded-xl hover:bg-[#F2EFE9] text-[#636A74] hover:text-[#0B6E5F] transition-colors cursor-pointer"
          title="Open Chat Sessions"
        >
          <MessageSquare className="w-4 h-4" />
        </button>

        <div className="flex-1" />

        <button
          type="button"
          onClick={onNewChat}
          className="p-2 rounded-xl bg-[#E6F4F1] hover:bg-[#D2EDE7] text-[#0B6E5F] transition-colors cursor-pointer"
          title="New Chat Session"
        >
          <Plus className="w-4 h-4" />
        </button>
      </aside>
    );
  }

  return (
    <aside className="w-full lg:w-[340px] flex-shrink-0 bg-white border border-[#E5E2DB] rounded-2xl shadow-sm flex flex-col h-[760px] overflow-hidden transition-all">
      {/* 1. Header: Repository Pill & Collapse Toggle */}
      <div className="px-4 py-3 border-b border-[#EAE8E2] bg-[#FAF9F6] flex items-center justify-between gap-2">
        <div className="flex items-center gap-2 min-w-0">
          <div className="w-7 h-7 rounded-lg bg-[#E6F4F1] text-[#0B6E5F] flex items-center justify-center flex-shrink-0">
            <Terminal className="w-4 h-4" />
          </div>
          <div className="min-w-0">
            <h2 className="text-xs font-bold text-[#1C2024] truncate" title={repo.repo_name}>
              {repo.repo_name}
            </h2>
            <div className="flex items-center gap-1.5 text-[10px] text-[#636A74]">
              <span className="inline-block w-1.5 h-1.5 rounded-full bg-emerald-500" />
              <span>{files.length > 0 ? `${files.length} files indexed` : "Indexed"}</span>
            </div>
          </div>
        </div>

        <div className="flex items-center gap-1">
          <button
            type="button"
            onClick={onNewRepo}
            className="p-1.5 rounded-lg text-[#636A74] hover:text-[#1C2024] hover:bg-[#ECE9E3] transition-colors cursor-pointer"
            title="Switch Repository"
          >
            <RotateCcw className="w-3.5 h-3.5" />
          </button>
          <button
            type="button"
            onClick={onToggleCollapse}
            className="p-1.5 rounded-lg text-[#636A74] hover:text-[#0B6E5F] hover:bg-[#ECE9E3] transition-colors cursor-pointer"
            title="Collapse Sidebar"
          >
            <PanelLeftClose className="w-4 h-4" />
          </button>
        </div>
      </div>

      {/* 2. Interactive Segmented Navigation Tabs */}
      <div className="p-2 border-b border-[#EAE8E2] bg-white">
        <div className="grid grid-cols-3 gap-1 p-1 bg-[#F5F4F0] rounded-xl text-xs font-medium">
          <button
            type="button"
            onClick={() => setActiveTab("files")}
            className={`flex items-center justify-center gap-1.5 py-1.5 rounded-lg transition-all cursor-pointer ${
              activeTab === "files"
                ? "bg-white text-[#0B6E5F] font-semibold shadow-xs"
                : "text-[#636A74] hover:text-[#1C2024]"
            }`}
          >
            <FolderTree className="w-3.5 h-3.5" />
            <span>Files</span>
            {files.length > 0 && (
              <span className="text-[10px] px-1.5 py-0.2 rounded-full bg-[#EAE8E2] text-[#636A74]">
                {files.length}
              </span>
            )}
          </button>

          <button
            type="button"
            onClick={() => setActiveTab("tools")}
            className={`flex items-center justify-center gap-1.5 py-1.5 rounded-lg transition-all cursor-pointer ${
              activeTab === "tools"
                ? "bg-white text-[#0B6E5F] font-semibold shadow-xs"
                : "text-[#636A74] hover:text-[#1C2024]"
            }`}
          >
            <Sparkles className="w-3.5 h-3.5" />
            <span>AI Tools</span>
          </button>

          <button
            type="button"
            onClick={() => setActiveTab("chat")}
            className={`flex items-center justify-center gap-1.5 py-1.5 rounded-lg transition-all cursor-pointer ${
              activeTab === "chat"
                ? "bg-white text-[#0B6E5F] font-semibold shadow-xs"
                : "text-[#636A74] hover:text-[#1C2024]"
            }`}
          >
            <MessageSquare className="w-3.5 h-3.5" />
            <span>Chats</span>
          </button>
        </div>
      </div>

      {/* 3. Tab Contents */}
      <div className="flex-1 overflow-y-auto p-3">
        {/* ============================================================== */}
        {/* TAB 1: CODEBASE FILE EXPLORER & QUICK AI ACTIONS               */}
        {/* ============================================================== */}
        {activeTab === "files" && (
          <div className="space-y-3">
            {/* Search Input */}
            <div className="relative">
              <Search className="w-3.5 h-3.5 text-[#8C939D] absolute left-3 top-1/2 -translate-y-1/2 pointer-events-none" />
              <input
                type="text"
                value={fileSearch}
                onChange={(e) => setFileSearch(e.target.value)}
                placeholder="Search repository files..."
                className="w-full pl-8 pr-3 py-1.5 bg-[#FAF9F6] border border-[#E5E2DB] rounded-lg text-xs text-[#1C2024] placeholder-[#8C939D] focus:outline-none focus:ring-1 focus:ring-[#0B6E5F] focus:bg-white transition-all"
              />
            </div>

            {/* Files List */}
            {isLoadingFiles ? (
              <div className="py-8 text-center text-xs text-[#8C939D] space-y-2">
                <div className="w-5 h-5 border-2 border-[#0B6E5F] border-t-transparent rounded-full animate-spin mx-auto" />
                <p>Loading codebase files...</p>
              </div>
            ) : filteredFiles.length === 0 ? (
              <div className="py-8 text-center text-xs text-[#8C939D]">
                No files found matching &quot;{fileSearch}&quot;
              </div>
            ) : (
              <div className="space-y-1">
                {filteredFiles.map((file) => {
                  const isExpanded = expandedFile === file.file_path;
                  const badge = getFileBadgeColor(file.file_path);
                  const fileNameOnly = file.file_path.split("/").pop() || file.file_path;
                  const dirPath = file.file_path.includes("/")
                    ? file.file_path.substring(0, file.file_path.lastIndexOf("/"))
                    : "";

                  return (
                    <div
                      key={file.file_path}
                      className="border border-[#EAE8E2] rounded-xl overflow-hidden bg-white hover:border-[#D5D1C8] transition-all"
                    >
                      {/* File Item Row */}
                      <button
                        type="button"
                        onClick={() => setExpandedFile(isExpanded ? null : file.file_path)}
                        className="w-full px-2.5 py-2 flex items-center justify-between text-left hover:bg-[#FAF9F6] transition-colors cursor-pointer gap-2"
                      >
                        <div className="flex items-center gap-2 min-w-0">
                          <FileCode2 className={`w-4 h-4 flex-shrink-0 ${badge.text}`} />
                          <div className="min-w-0">
                            <div className="text-xs font-semibold text-[#1C2024] truncate">
                              {fileNameOnly}
                            </div>
                            {dirPath && (
                              <div className="text-[10px] text-[#8C939D] truncate font-mono">
                                {dirPath}
                              </div>
                            )}
                          </div>
                        </div>

                        <div className="flex items-center gap-1.5 flex-shrink-0">
                          {file.line_count > 0 && (
                            <span className="text-[10px] font-mono text-[#8C939D]">
                              {file.line_count}L
                            </span>
                          )}
                          {isExpanded ? (
                            <ChevronDown className="w-3.5 h-3.5 text-[#636A74]" />
                          ) : (
                            <ChevronRight className="w-3.5 h-3.5 text-[#8C939D]" />
                          )}
                        </div>
                      </button>

                      {/* Expandable Quick AI Action Drawer */}
                      {isExpanded && (
                        <div className="p-2 bg-[#F9F8F6] border-t border-[#EAE8E2] space-y-1">
                          <span className="text-[10px] font-bold uppercase tracking-wider text-[#636A74] px-1">
                            Ask DevMind about this file:
                          </span>

                          <button
                            type="button"
                            onClick={() =>
                              onSelectPrompt(
                                `Explain the role and architecture of \`${file.file_path}\` in detail.`
                              )
                            }
                            className="w-full flex items-center gap-2 px-2.5 py-1.5 rounded-lg bg-white border border-[#E5E2DB] hover:border-[#0B6E5F] hover:bg-[#E6F4F1]/30 text-xs text-[#1C2024] font-medium transition-all text-left cursor-pointer"
                          >
                            <FileSearch className="w-3.5 h-3.5 text-[#0B6E5F]" />
                            <span>Explain architecture</span>
                          </button>

                          <button
                            type="button"
                            onClick={() =>
                              onSelectPrompt(
                                `Review \`${file.file_path}\` for potential bugs, edge cases, and code improvements.`
                              )
                            }
                            className="w-full flex items-center gap-2 px-2.5 py-1.5 rounded-lg bg-white border border-[#E5E2DB] hover:border-[#0B6E5F] hover:bg-[#E6F4F1]/30 text-xs text-[#1C2024] font-medium transition-all text-left cursor-pointer"
                          >
                            <Bug className="w-3.5 h-3.5 text-amber-600" />
                            <span>Find bugs & edge cases</span>
                          </button>

                          <button
                            type="button"
                            onClick={() =>
                              onSelectPrompt(
                                `Perform a security review of \`${file.file_path}\`. Check for injection, insecure patterns, or vulnerabilities.`
                              )
                            }
                            className="w-full flex items-center gap-2 px-2.5 py-1.5 rounded-lg bg-white border border-[#E5E2DB] hover:border-[#0B6E5F] hover:bg-[#E6F4F1]/30 text-xs text-[#1C2024] font-medium transition-all text-left cursor-pointer"
                          >
                            <ShieldAlert className="w-3.5 h-3.5 text-rose-600" />
                            <span>Security audit</span>
                          </button>

                          <button
                            type="button"
                            onClick={() =>
                              onSelectPrompt(
                                `What functions, classes, and exported APIs are implemented inside \`${file.file_path}\`?`
                              )
                            }
                            className="w-full flex items-center gap-2 px-2.5 py-1.5 rounded-lg bg-white border border-[#E5E2DB] hover:border-[#0B6E5F] hover:bg-[#E6F4F1]/30 text-xs text-[#1C2024] font-medium transition-all text-left cursor-pointer"
                          >
                            <HelpCircle className="w-3.5 h-3.5 text-blue-600" />
                            <span>Show functions & symbols</span>
                          </button>
                        </div>
                      )}
                    </div>
                  );
                })}
              </div>
            )}
          </div>
        )}

        {/* ============================================================== */}
        {/* TAB 2: AI TOOLS & SUPERPOWER LAUNCHERS                         */}
        {/* ============================================================== */}
        {activeTab === "tools" && (
          <div className="space-y-4">
            {/* AI Agent Superpower Cards */}
            <div className="space-y-2">
              <span className="text-[10px] font-bold uppercase tracking-wider text-[#636A74] px-1">
                AI Superpowers
              </span>

              {aiTools.map((tool) => {
                const Icon = tool.icon;
                const isVoice = tool.id === "voice";

                return (
                  <button
                    key={tool.id}
                    type="button"
                    onClick={tool.onClick}
                    className={`w-full text-left p-3 rounded-xl border transition-all cursor-pointer group flex items-start gap-3 shadow-2xs ${
                      isVoice
                        ? "bg-gradient-to-r from-[#0B6E5F] to-[#085247] text-white border-transparent hover:shadow-sm"
                        : "bg-white border-[#E5E2DB] hover:border-[#0B6E5F] hover:bg-[#FAF9F6]"
                    }`}
                  >
                    <div
                      className={`w-8 h-8 rounded-lg flex items-center justify-center flex-shrink-0 ${
                        isVoice ? "bg-white/20 text-white" : "bg-[#E6F4F1] text-[#0B6E5F]"
                      }`}
                    >
                      <Icon className={`w-4 h-4 ${isVoice ? "animate-pulse" : ""}`} />
                    </div>

                    <div className="flex-1 min-w-0">
                      <div className="flex items-center justify-between gap-1">
                        <span
                          className={`text-xs font-bold leading-tight truncate ${
                            isVoice ? "text-white" : "text-[#1C2024]"
                          }`}
                        >
                          {tool.title}
                        </span>
                        <span
                          className={`text-[9px] px-1.5 py-0.5 rounded-full font-semibold uppercase tracking-wider ${
                            isVoice ? "bg-white/20 text-white" : "bg-[#FAF9F6] border border-[#EAE8E2] text-[#636A74]"
                          }`}
                        >
                          {tool.badge}
                        </span>
                      </div>
                      <p
                        className={`text-[11px] leading-snug mt-1 ${
                          isVoice ? "text-white/80" : "text-[#636A74]"
                        }`}
                      >
                        {tool.desc}
                      </p>
                    </div>
                  </button>
                );
              })}
            </div>

            {/* Curated Codebase Quick Inquiries */}
            <div className="space-y-2 border-t border-[#EAE8E2] pt-3">
              <span className="text-[10px] font-bold uppercase tracking-wider text-[#636A74] px-1">
                Curated Quick Inquiries
              </span>

              <div className="space-y-1.5">
                {curatedPrompts.map((cp) => (
                  <button
                    key={cp.label}
                    type="button"
                    onClick={() => onSelectPrompt(cp.query)}
                    className="w-full text-left p-2.5 rounded-xl border border-[#E5E2DB] bg-white hover:border-[#0B6E5F] hover:bg-[#E6F4F1]/30 transition-all cursor-pointer group flex items-center justify-between gap-2"
                  >
                    <div>
                      <div className="text-xs font-semibold text-[#1C2024] group-hover:text-[#0B6E5F] transition-colors">
                        {cp.label}
                      </div>
                      <div className="text-[10px] text-[#8C939D] truncate max-w-[240px]">
                        {cp.query}
                      </div>
                    </div>
                    <ArrowRight className="w-3.5 h-3.5 text-[#A09D96] group-hover:text-[#0B6E5F] group-hover:translate-x-0.5 transition-all flex-shrink-0" />
                  </button>
                ))}
              </div>
            </div>
          </div>
        )}

        {/* ============================================================== */}
        {/* TAB 3: CHAT THREADS & RECENT PROMPTS                           */}
        {/* ============================================================== */}
        {activeTab === "chat" && (
          <div className="space-y-3">
            {/* New Chat Primary Action */}
            <button
              type="button"
              onClick={onNewChat}
              className="w-full flex items-center justify-center gap-2 py-2.5 px-3 rounded-xl bg-gradient-to-r from-[#0B6E5F] to-[#085247] hover:from-[#095b4e] hover:to-[#064239] text-white text-xs font-bold transition-all shadow-xs cursor-pointer"
            >
              <Plus className="w-4 h-4" />
              <span>Start New Chat Thread</span>
            </button>

            {/* Export action */}
            {onExportChat && (
              <button
                type="button"
                onClick={onExportChat}
                className="w-full flex items-center justify-center gap-2 py-2 px-3 rounded-xl border border-[#D6D2CA] hover:bg-[#F9F8F6] text-[#1C2024] text-xs font-semibold transition-colors cursor-pointer"
              >
                <Download className="w-3.5 h-3.5 text-[#636A74]" />
                <span>Export Current Conversation</span>
              </button>
            )}

            {/* Questions Asked in Current Thread */}
            <div className="space-y-2 border-t border-[#EAE8E2] pt-3">
              <span className="text-[10px] font-bold uppercase tracking-wider text-[#636A74] px-1">
                Inquiries in this Thread ({recentQuestions.length})
              </span>

              {recentQuestions.length === 0 ? (
                <div className="p-4 text-center rounded-xl bg-[#FAF9F6] border border-[#EAE8E2] text-xs text-[#8C939D]">
                  No messages yet. Ask a question or click a tool to begin!
                </div>
              ) : (
                <div className="space-y-1.5">
                  {recentQuestions.map((q, idx) => (
                    <button
                      key={idx}
                      type="button"
                      onClick={() => onSelectPrompt(q)}
                      className="w-full text-left p-2 rounded-lg bg-white border border-[#EAE8E2] hover:border-[#0B6E5F] text-xs text-[#1C2024] truncate transition-all cursor-pointer flex items-center gap-2"
                      title={q}
                    >
                      <MessageSquare className="w-3 h-3 text-[#0B6E5F] flex-shrink-0" />
                      <span className="truncate">{q}</span>
                    </button>
                  ))}
                </div>
              )}
            </div>
          </div>
        )}
      </div>

      {/* 4. Footer: Clean Grounding Guarantee Pill */}
      <div className="p-3 border-t border-[#EAE8E2] bg-[#FAF9F6] flex items-center justify-between text-[11px] text-[#636A74]">
        <div className="flex items-center gap-1.5">
          <Layers className="w-3.5 h-3.5 text-[#0B6E5F]" />
          <span className="font-medium text-[#1C2024]">DevMind RAG Engine</span>
        </div>
        <span className="text-[10px] text-emerald-700 bg-emerald-50 px-2 py-0.5 rounded-full font-semibold border border-emerald-200">
          Verified Citations
        </span>
      </div>
    </aside>
  );
};
