"use client";

import React, { useState } from "react";
import {
  FileCode2,
  X,
  Copy,
  Check,
  ChevronDown,
  ChevronUp,
  Search,
} from "lucide-react";
import { Citation } from "@/lib/types";
import { SourceCard } from "./SourceCard";

interface EvidenceDrawerProps {
  citations: Citation[];
  isOpen: boolean;
  onClose: () => void;
  activeCitationIndex?: number | null;
}

export const EvidenceDrawer: React.FC<EvidenceDrawerProps> = ({
  citations,
  isOpen,
  onClose,
  activeCitationIndex = null,
}) => {
  const [searchFilter, setSearchFilter] = useState("");
  const [copiedAll, setCopiedAll] = useState(false);

  if (!isOpen) return null;

  const filteredCitations = citations.filter((c) =>
    c.file_path.toLowerCase().includes(searchFilter.toLowerCase())
  );

  const handleCopyAll = () => {
    const formatted = citations
      .map(
        (c, idx) =>
          `[${idx + 1}] File: ${c.file_path} (Lines ${c.start_line}-${c.end_line})\n${c.snippet || ""}\n`
      )
      .join("\n---\n\n");
    navigator.clipboard.writeText(formatted);
    setCopiedAll(true);
    setTimeout(() => setCopiedAll(false), 2000);
  };

  return (
    <div
      role="dialog"
      aria-modal="true"
      className="fixed inset-0 z-50 bg-black/40 backdrop-blur-xs flex items-center justify-center p-3 sm:p-6"
    >
      <div className="bg-[#F7F6F3] rounded-2xl border border-[#E5E2DB] shadow-2xl w-full max-w-4xl flex flex-col max-h-[90vh] overflow-hidden">
        {/* Header Bar */}
        <div className="p-4 sm:p-5 border-b border-[#E5E2DB] bg-white flex items-center justify-between gap-3">
          <div className="flex items-center gap-2.5">
            <div className="w-8 h-8 rounded-xl bg-[#E6F4F1] text-[#0B6E5F] flex items-center justify-center">
              <FileCode2 className="w-4 h-4" />
            </div>
            <div>
              <h3 className="text-base font-bold text-[#1C2024]">
                Retrieved Evidence Sources
              </h3>
              <p className="text-xs text-[#636A74]">
                {citations.length} verified code chunk{citations.length === 1 ? "" : "s"} ground this answer
              </p>
            </div>
          </div>

          <div className="flex items-center gap-2">
            <button
              type="button"
              onClick={handleCopyAll}
              className="inline-flex items-center gap-1.5 px-3 py-1.5 text-xs font-semibold rounded-lg border border-[#D6D2CA] text-[#1C2024] hover:bg-[#F9F8F6] transition-colors cursor-pointer"
            >
              {copiedAll ? (
                <>
                  <Check className="w-3.5 h-3.5 text-emerald-600" />
                  <span className="text-emerald-700">Copied All</span>
                </>
              ) : (
                <>
                  <Copy className="w-3.5 h-3.5" />
                  <span>Copy Citations</span>
                </>
              )}
            </button>

            <button
              type="button"
              onClick={onClose}
              className="p-1.5 rounded-lg text-[#636A74] hover:text-[#1C2024] hover:bg-[#EAE8E2] transition-colors cursor-pointer"
              title="Close drawer"
            >
              <X className="w-5 h-5" />
            </button>
          </div>
        </div>

        {/* Search / Filter Sub-bar */}
        {citations.length > 3 && (
          <div className="px-5 py-2.5 border-b border-[#E5E2DB] bg-white">
            <div className="relative">
              <Search className="w-3.5 h-3.5 text-[#636A74] absolute left-3 top-1/2 -translate-y-1/2" />
              <input
                type="text"
                value={searchFilter}
                onChange={(e) => setSearchFilter(e.target.value)}
                placeholder="Filter by file path..."
                className="w-full pl-9 pr-3 py-1.5 text-xs rounded-lg border border-[#D6D2CA] focus:border-[#0B6E5F] outline-none bg-[#FAF9F6]"
              />
            </div>
          </div>
        )}

        {/* Scrollable Cards Container */}
        <div className="p-5 overflow-y-auto space-y-4 flex-1">
          {filteredCitations.map((citation, idx) => {
            const actualIndex = citations.indexOf(citation) + 1;
            const isHighlighted = activeCitationIndex === actualIndex;

            return (
              <SourceCard
                key={actualIndex}
                index={actualIndex}
                citation={citation}
                isHighlighted={isHighlighted}
              />
            );
          })}

          {filteredCitations.length === 0 && (
            <p className="text-center text-xs text-[#636A74] py-8">
              No citations matching filter &quot;{searchFilter}&quot;
            </p>
          )}
        </div>

        {/* Footer */}
        <div className="p-3.5 border-t border-[#E5E2DB] bg-white flex items-center justify-between text-xs text-[#636A74]">
          <span>
            Line numbers reflect 1-indexed source files in repository index.
          </span>
          <button
            type="button"
            onClick={onClose}
            className="px-4 py-1.5 rounded-lg bg-[#1C2024] text-white hover:bg-black font-semibold transition-colors cursor-pointer"
          >
            Done
          </button>
        </div>
      </div>
    </div>
  );
};
