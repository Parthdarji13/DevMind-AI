"use client";

import React, { useState } from "react";
import {
  GitMerge,
  X,
  Search,
  Loader2,
  FileCode2,
  ArrowRight,
  Copy,
  Check,
  AlertCircle,
  Sparkles,
} from "lucide-react";
import { FlowTraceResponse, FlowTraceStep } from "@/lib/types";
import { getFlowTrace } from "@/lib/api";

interface FlowTraceModalProps {
  repoId: string;
  isOpen: boolean;
  onClose: () => void;
  onSelectQuery?: (q: string) => void;
}

export const FlowTraceModal: React.FC<FlowTraceModalProps> = ({
  repoId,
  isOpen,
  onClose,
  onSelectQuery,
}) => {
  const [query, setQuery] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [traceResult, setTraceResult] = useState<FlowTraceResponse | null>(null);
  const [copiedDiagram, setCopiedDiagram] = useState(false);

  if (!isOpen) return null;

  const SAMPLE_FLOWS = [
    "User authentication and JWT token flow",
    "Repository ingestion and AST chunking pipeline",
    "Vector search and hybrid RRF retrieval flow",
    "MongoDB chat history and feedback recording",
  ];

  const handleTrace = async (flowQuery: string) => {
    const q = flowQuery.trim();
    if (!q) return;
    setLoading(true);
    setError(null);
    try {
      const res = await getFlowTrace(repoId, q);
      setTraceResult(res);
    } catch (err: any) {
      setError(err?.message || "Failed to trace execution flow.");
    } finally {
      setLoading(false);
    }
  };

  const handleCopyDiagram = async () => {
    if (!traceResult?.mermaid_diagram) return;
    try {
      await navigator.clipboard.writeText(traceResult.mermaid_diagram);
      setCopiedDiagram(true);
      setTimeout(() => setCopiedDiagram(false), 2000);
    } catch {}
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 backdrop-blur-xs p-4 overflow-y-auto">
      <div className="bg-white rounded-2xl max-w-4xl w-full max-h-[90vh] shadow-2xl border border-[#E5E2DB] flex flex-col overflow-hidden animate-in fade-in zoom-in-95 duration-200">
        {/* Header */}
        <div className="px-6 py-4 border-b border-[#EAE8E2] bg-[#FAF9F6] flex items-center justify-between">
          <div className="flex items-center gap-2.5">
            <div className="w-8 h-8 rounded-xl bg-[#E6F4F1] text-[#0B6E5F] flex items-center justify-center shadow-xs">
              <GitMerge className="w-4 h-4" />
            </div>
            <div>
              <h2 className="text-base font-bold text-[#1C2024] leading-tight">
                Execution Flow Tracer
              </h2>
              <p className="text-xs text-[#636A74]">
                Trace multi-step code paths with exact line numbers and sequence diagrams
              </p>
            </div>
          </div>
          <button
            type="button"
            onClick={onClose}
            className="p-1 rounded-lg text-[#636A74] hover:text-[#1C2024] hover:bg-black/5 transition-colors cursor-pointer"
          >
            <X className="w-5 h-5" />
          </button>
        </div>

        {/* Search Bar & Sample Prompts */}
        <div className="p-6 border-b border-[#EAE8E2] bg-white space-y-3">
          <form
            onSubmit={(e) => {
              e.preventDefault();
              handleTrace(query);
            }}
            className="flex gap-2"
          >
            <div className="relative flex-1">
              <Search className="w-4 h-4 absolute left-3.5 top-1/2 -translate-y-1/2 text-[#A09D96]" />
              <input
                type="text"
                value={query}
                onChange={(e) => setQuery(e.target.value)}
                placeholder="Enter a flow to trace (e.g. 'user login', 'zip ingestion', 'vector search')..."
                className="w-full text-xs pl-10 pr-4 py-2.5 rounded-xl border border-[#E5E2DB] bg-white text-[#1C2024] placeholder-[#A09D96] focus:outline-none focus:border-[#0B6E5F] focus:ring-1 focus:ring-[#0B6E5F]"
              />
            </div>
            <button
              type="submit"
              disabled={loading || !query.trim()}
              className="inline-flex items-center gap-1.5 px-4 py-2.5 rounded-xl text-xs font-semibold bg-[#0B6E5F] text-white hover:bg-[#085449] disabled:opacity-50 transition-colors cursor-pointer shadow-xs"
            >
              {loading ? (
                <>
                  <Loader2 className="w-3.5 h-3.5 animate-spin" />
                  <span>Tracing...</span>
                </>
              ) : (
                <>
                  <Sparkles className="w-3.5 h-3.5" />
                  <span>Trace Flow</span>
                </>
              )}
            </button>
          </form>

          {/* Sample Chips */}
          <div className="flex flex-wrap items-center gap-1.5 text-xs text-[#636A74]">
            <span className="font-medium text-[11px] text-[#A09D96]">Quick suggestions:</span>
            {SAMPLE_FLOWS.map((sf, idx) => (
              <button
                key={idx}
                type="button"
                onClick={() => {
                  setQuery(sf);
                  handleTrace(sf);
                }}
                className="text-[11px] px-2.5 py-1 rounded-lg bg-[#FAF9F6] border border-[#EAE8E2] hover:bg-[#F2EFE9] text-[#1C2024] transition-colors cursor-pointer"
              >
                {sf}
              </button>
            ))}
          </div>
        </div>

        {/* Content Body */}
        <div className="flex-1 overflow-y-auto p-6 space-y-6">
          {error && (
            <div className="flex items-center gap-2 p-3.5 rounded-xl bg-red-50 border border-red-200 text-xs text-red-800">
              <AlertCircle className="w-4 h-4 text-red-600 flex-shrink-0" />
              <span>{error}</span>
            </div>
          )}

          {traceResult ? (
            <div className="space-y-6 animate-in fade-in duration-200">
              {/* Overview Card */}
              <div className="p-4 rounded-xl border border-[#BDE3DC] bg-[#E6F4F1] space-y-1.5">
                <h3 className="text-sm font-bold text-[#0B6E5F]">
                  {traceResult.flow_title}
                </h3>
                <p className="text-xs text-[#1C2024] leading-relaxed">
                  {traceResult.summary}
                </p>
              </div>

              {/* Step-by-Step Execution Path */}
              <div className="space-y-3">
                <div className="flex items-center gap-2 text-xs font-bold uppercase tracking-wider text-[#636A74]">
                  <span>Step-by-Step Execution Steps ({traceResult.steps.length})</span>
                </div>

                <div className="relative pl-6 space-y-4 before:absolute before:left-2.5 before:top-3 before:bottom-3 before:w-0.5 before:bg-[#EAE8E2]">
                  {traceResult.steps.map((st: FlowTraceStep) => (
                    <div key={st.step_number} className="relative bg-white border border-[#E5E2DB] rounded-xl p-4 shadow-xs space-y-2">
                      <div className="absolute -left-[27px] top-4 w-5 h-5 rounded-full bg-[#0B6E5F] text-white text-[11px] font-bold flex items-center justify-center shadow-xs">
                        {st.step_number}
                      </div>

                      <div className="flex items-center justify-between gap-2 flex-wrap">
                        <h4 className="text-xs font-bold text-[#1C2024] flex items-center gap-1.5">
                          <span>{st.title}</span>
                          {st.function_or_symbol && (
                            <span className="font-mono text-[10px] px-1.5 py-0.5 rounded bg-[#FAF9F6] border border-[#E5E2DB] text-[#0B6E5F]">
                              {st.function_or_symbol}()
                            </span>
                          )}
                        </h4>

                        <span className="inline-flex items-center gap-1 text-[11px] font-mono font-medium text-[#636A74] bg-[#FAF9F6] px-2 py-0.5 rounded border border-[#EAE8E2]">
                          <FileCode2 className="w-3 h-3 text-[#0B6E5F]" />
                          <span>{st.file_path}:{st.start_line}-{st.end_line}</span>
                        </span>
                      </div>

                      <p className="text-xs text-[#636A74] leading-relaxed">
                        {st.description}
                      </p>
                    </div>
                  ))}
                </div>
              </div>

              {/* Sequence Diagram Card */}
              {traceResult.mermaid_diagram && (
                <div className="space-y-2 pt-2">
                  <div className="flex items-center justify-between">
                    <span className="text-xs font-bold uppercase tracking-wider text-[#636A74]">
                      Sequence Flow Diagram
                    </span>
                    <button
                      type="button"
                      onClick={handleCopyDiagram}
                      className="inline-flex items-center gap-1 text-xs text-[#0B6E5F] hover:text-[#085449] font-medium transition-colors cursor-pointer"
                    >
                      {copiedDiagram ? <Check className="w-3.5 h-3.5" /> : <Copy className="w-3.5 h-3.5" />}
                      <span>{copiedDiagram ? "Copied" : "Copy Diagram"}</span>
                    </button>
                  </div>

                  <pre className="p-4 rounded-xl bg-[#1C2024] text-emerald-400 font-mono text-xs overflow-x-auto leading-relaxed shadow-xs">
                    <code>{traceResult.mermaid_diagram}</code>
                  </pre>
                </div>
              )}
            </div>
          ) : (
            /* Empty prompt state */
            !loading && (
              <div className="py-12 flex flex-col items-center justify-center text-center space-y-2 text-[#636A74]">
                <GitMerge className="w-10 h-10 text-[#0B6E5F]/40" />
                <h4 className="text-sm font-semibold text-[#1C2024]">Trace any flow in your codebase</h4>
                <p className="text-xs max-w-md">
                  Choose a suggestion above or enter any execution flow to trace functions, calls, and line-level files.
                </p>
              </div>
            )
          )}
        </div>
      </div>
    </div>
  );
};
