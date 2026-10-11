"use client";

import React, { useState } from "react";
import {
  Terminal,
  User,
  AlertTriangle,
  FileCode2,
  HelpCircle,
  ChevronDown,
  ChevronUp,
} from "lucide-react";
import { Citation } from "@/lib/types";
import { SafeMarkdown } from "./SafeMarkdown";
import { CitationChip } from "./CitationChip";
import { SourceCard } from "./SourceCard";

export interface ChatMessageDisplay {
  id: string;
  role: "user" | "assistant";
  content: string;
  citations?: Citation[];
  abstained?: boolean;
  inference_detected?: boolean;
  timestamp?: string;
}

interface MessageItemProps {
  message: ChatMessageDisplay;
  onOpenDrawer?: (citations: Citation[], initialIndex?: number) => void;
}

export const MessageItem: React.FC<MessageItemProps> = ({
  message,
  onOpenDrawer,
}) => {
  const isUser = message.role === "user";
  const [showInlineSources, setShowInlineSources] = useState(false);
  const [selectedCitationIndex, setSelectedCitationIndex] = useState<number | null>(null);

  if (isUser) {
    return (
      <div className="flex justify-end items-start gap-2.5 max-w-3xl ml-auto">
        <div className="bg-[#1C2024] text-white rounded-2xl rounded-tr-xs px-4 py-3 shadow-xs max-w-xl text-sm leading-relaxed">
          <p className="whitespace-pre-wrap">{message.content}</p>
        </div>
        <div className="w-8 h-8 rounded-full bg-[#E5E2DB] text-[#1C2024] flex items-center justify-center flex-shrink-0 mt-0.5">
          <User className="w-4 h-4" />
        </div>
      </div>
    );
  }

  const handleChipClick = (index: number) => {
    setSelectedCitationIndex(index);
    setShowInlineSources(true);
    if (onOpenDrawer && message.citations) {
      onOpenDrawer(message.citations, index);
    }
  };

  // Assistant message
  return (
    <div className="flex items-start gap-3.5 max-w-4xl mr-auto">
      {/* DevMind Assistant Avatar */}
      <div className="w-8 h-8 rounded-xl bg-[#0B6E5F] text-white flex items-center justify-center flex-shrink-0 mt-0.5 shadow-xs">
        <Terminal className="w-4 h-4" />
      </div>

      <div className="flex-1 space-y-3 min-w-0">
        {/* Author Label */}
        <div className="flex items-center gap-2">
          <span className="font-semibold text-xs text-[#1C2024]">DevMind AI</span>
          <span className="text-[10px] font-medium px-1.5 py-0.2 rounded bg-[#E6F4F1] text-[#0B6E5F] border border-[#BDE3DC]">
            Evidence-Grounded
          </span>
          {message.timestamp && (
            <span className="text-[11px] text-[#A09D96]">{message.timestamp}</span>
          )}
        </div>

        {/* Insufficient Evidence Card */}
        {message.abstained && (
          <div className="p-4 rounded-xl border border-amber-200 bg-[#FDF9F0] text-amber-900 text-xs space-y-1.5 shadow-xs">
            <div className="flex items-center gap-2 font-bold text-amber-800">
              <HelpCircle className="w-4 h-4 text-amber-600" />
              <span>Not enough evidence in the indexed codebase</span>
            </div>
            <p className="leading-relaxed text-amber-800/90">
              The retrieved code chunks did not contain definitive evidence to verify an answer without hallucination.
            </p>
          </div>
        )}

        {/* Inference Callout */}
        {message.inference_detected && (
          <div className="p-3.5 rounded-xl border border-amber-300 bg-[#FBEFD9] text-[#6B3F00] text-xs space-y-1 shadow-xs">
            <div className="flex items-center gap-1.5 font-bold uppercase tracking-wider text-[11px]">
              <AlertTriangle className="w-3.5 h-3.5 text-[#B45309]" />
              <span>Inference Callout</span>
            </div>
            <p className="leading-relaxed">
              This response contains model inferences or deductions that extrapolate beyond literal source declarations.
            </p>
          </div>
        )}

        {/* Main Message Content */}
        <div className="bg-white border border-[#E5E2DB] rounded-2xl rounded-tl-xs p-5 shadow-xs">
          <SafeMarkdown content={message.content} />
        </div>

        {/* Verified Citations Row */}
        {message.citations && message.citations.length > 0 && (
          <div className="space-y-3 pt-1">
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-1.5 text-xs font-semibold uppercase tracking-wider text-[#636A74]">
                <FileCode2 className="w-3.5 h-3.5 text-[#0B6E5F]" />
                <span>Verified Citations ({message.citations.length})</span>
              </div>

              <button
                type="button"
                onClick={() => setShowInlineSources(!showInlineSources)}
                className="inline-flex items-center gap-1 text-xs text-[#0B6E5F] hover:text-[#085449] font-medium transition-colors cursor-pointer"
              >
                <span>{showInlineSources ? "Hide Sources" : "View Sources"}</span>
                {showInlineSources ? (
                  <ChevronUp className="w-3.5 h-3.5" />
                ) : (
                  <ChevronDown className="w-3.5 h-3.5" />
                )}
              </button>
            </div>

            {/* Citation Chips */}
            <div className="flex flex-wrap gap-2">
              {message.citations.map((cite, cIdx) => (
                <CitationChip
                  key={cIdx}
                  index={cIdx + 1}
                  citation={cite}
                  isActive={selectedCitationIndex === cIdx + 1}
                  onClick={() => handleChipClick(cIdx + 1)}
                />
              ))}
            </div>

            {/* Expandable Inline Source Cards */}
            {showInlineSources && (
              <div className="space-y-3 pt-2">
                {message.citations.map((cite, cIdx) => (
                  <SourceCard
                    key={cIdx}
                    index={cIdx + 1}
                    citation={cite}
                    isHighlighted={selectedCitationIndex === cIdx + 1}
                  />
                ))}
              </div>
            )}
          </div>
        )}
      </div>
    </div>
  );
};
