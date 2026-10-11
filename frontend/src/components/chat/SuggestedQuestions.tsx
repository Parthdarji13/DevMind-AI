"use client";

import React from "react";
import { Sparkles, ArrowRight, Code2, ShieldAlert, Database, Network, Cpu, FileCode2 } from "lucide-react";
import { SuggestedQuestion } from "@/lib/types";

interface SuggestedQuestionsProps {
  suggestions: SuggestedQuestion[];
  isLoading: boolean;
  onSelectQuestion: (question: string) => void;
}

export const SuggestedQuestions: React.FC<SuggestedQuestionsProps> = ({
  suggestions,
  isLoading,
  onSelectQuestion,
}) => {
  const getCategoryBadge = (category: string) => {
    switch (category) {
      case "Architecture":
        return {
          icon: Cpu,
          bg: "bg-indigo-50 text-indigo-700 border-indigo-200/60",
        };
      case "API & Routing":
        return {
          icon: Network,
          bg: "bg-emerald-50 text-[#0B6E5F] border-emerald-200/60",
        };
      case "Data & Models":
        return {
          icon: Database,
          bg: "bg-amber-50 text-amber-800 border-amber-200/60",
        };
      case "Security & Auth":
        return {
          icon: ShieldAlert,
          bg: "bg-rose-50 text-rose-700 border-rose-200/60",
        };
      default:
        return {
          icon: Code2,
          bg: "bg-cyan-50 text-cyan-800 border-cyan-200/60",
        };
    }
  };

  if (isLoading) {
    return (
      <div className="w-full space-y-3 pt-2">
        <div className="flex items-center justify-between">
          <div className="h-4 w-36 bg-[#EAE8E2] rounded animate-pulse" />
          <div className="h-3 w-48 bg-[#EAE8E2] rounded animate-pulse" />
        </div>
        <div className="grid grid-cols-1 md:grid-cols-2 gap-2.5">
          {[1, 2, 3, 4].map((i) => (
            <div
              key={i}
              className="p-3.5 rounded-xl border border-[#EAE8E2] bg-[#FAF9F6] space-y-2 animate-pulse"
            >
              <div className="flex items-center gap-2">
                <div className="h-4 w-20 bg-[#E5E3DC] rounded-full" />
                <div className="h-3 w-28 bg-[#E5E3DC] rounded" />
              </div>
              <div className="h-4 w-full bg-[#E5E3DC] rounded" />
            </div>
          ))}
        </div>
      </div>
    );
  }

  if (suggestions.length === 0) {
    return null;
  }

  return (
    <div className="w-full space-y-3 pt-2">
      {/* Header with explicit verification notice */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-1.5 px-0.5">
        <div className="flex items-center gap-1.5">
          <Sparkles className="w-3.5 h-3.5 text-[#0B6E5F]" />
          <span className="text-[11px] font-semibold uppercase tracking-wider text-[#1C2024]">
            Repository-Derived Inquiries
          </span>
        </div>
        <span className="text-[10px] text-[#636A74] flex items-center gap-1">
          <span className="inline-block w-1.5 h-1.5 rounded-full bg-amber-500/80" />
          Derived from codebase structure • Answers verified upon retrieval
        </span>
      </div>

      {/* Suggested Questions Grid */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-2.5">
        {suggestions.map((item, idx) => {
          const badge = getCategoryBadge(item.category);
          const Icon = badge.icon;

          return (
            <button
              key={idx}
              type="button"
              onClick={() => onSelectQuestion(item.question)}
              className="group text-left p-3.5 rounded-xl border border-[#EAE8E2] hover:border-[#0B6E5F] bg-[#FAF9F6] hover:bg-[#E6F4F1]/30 transition-all cursor-pointer flex flex-col justify-between gap-2.5 shadow-sm hover:shadow relative overflow-hidden"
            >
              <div className="space-y-2 w-full">
                {/* Meta row: Category pill + source file reference */}
                <div className="flex items-center justify-between gap-2 text-[11px]">
                  <span
                    className={`inline-flex items-center gap-1 px-2 py-0.5 rounded-full border text-[10px] font-semibold tracking-wide ${badge.bg}`}
                  >
                    <Icon className="w-2.5 h-2.5" />
                    {item.category}
                  </span>

                  <span
                    className="font-mono text-[10px] text-[#636A74] truncate max-w-[190px] flex items-center gap-1"
                    title={`Derived from ${item.derived_from}`}
                  >
                    <FileCode2 className="w-3 h-3 text-[#878E99] shrink-0" />
                    <span className="truncate">{item.derived_from}</span>
                  </span>
                </div>

                {/* Question title */}
                <p className="text-xs font-semibold text-[#1C2024] group-hover:text-[#0B6E5F] transition-colors leading-relaxed line-clamp-2">
                  {item.question}
                </p>
              </div>

              {/* Bottom hint row */}
              <div className="flex items-center justify-end w-full pt-1 border-t border-[#F0EFEA]">
                <span className="text-[11px] font-semibold text-[#0B6E5F] opacity-0 group-hover:opacity-100 transition-opacity flex items-center gap-1">
                  <span>Ask Question</span>
                  <ArrowRight className="w-3 h-3" />
                </span>
              </div>
            </button>
          );
        })}
      </div>
    </div>
  );
};
