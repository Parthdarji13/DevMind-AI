"use client";

import React, { useState } from "react";
import { Copy, Check, FileCode2, AlertCircle } from "lucide-react";
import { Citation } from "@/lib/types";

interface SourceCardProps {
  index: number;
  citation: Citation;
  isHighlighted?: boolean;
}

export const SourceCard: React.FC<SourceCardProps> = ({
  index,
  citation,
  isHighlighted = false,
}) => {
  const [copied, setCopied] = useState(false);

  const handleCopy = () => {
    if (!citation.snippet) return;
    navigator.clipboard.writeText(citation.snippet);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  const lines = citation.snippet ? citation.snippet.split("\n") : [];
  const startLine = citation.start_line || 1;

  return (
    <div
      id={`src-${index}`}
      className={`rounded-xl border transition-all duration-200 overflow-hidden shadow-xs ${
        isHighlighted
          ? "border-[#0B6E5F] ring-2 ring-[#0B6E5F]/20 bg-white"
          : "border-[#E5E2DB] bg-white hover:border-[#D6D2CA]"
      }`}
    >
      {/* Subtle Header Row */}
      <div className="flex items-center justify-between px-4 py-2.5 bg-[#FAF9F6] border-b border-[#EAE8E2] text-xs">
        <div className="flex items-center gap-2.5 min-w-0">
          <span className="font-mono font-bold text-[11px] px-2 py-0.5 rounded-md bg-[#E6F4F1] text-[#08493F] border border-[#BDE3DC] flex-shrink-0">
            [{index}]
          </span>
          <FileCode2 className="w-4 h-4 text-[#0B6E5F] flex-shrink-0" />
          <span
            className="font-mono text-xs font-semibold text-[#1C2024] truncate max-w-sm sm:max-w-md"
            title={citation.file_path}
          >
            {citation.file_path}
          </span>
        </div>

        <div className="flex items-center gap-3 flex-shrink-0">
          {citation.start_line && citation.end_line ? (
            <span className="text-[11px] font-mono text-[#636A74] bg-[#ECE9E3] px-2 py-0.5 rounded">
              Lines {citation.start_line}–{citation.end_line}
            </span>
          ) : (
            <span className="text-[11px] text-[#A09D96] italic">
              Line range unverified
            </span>
          )}

          {citation.snippet && (
            <button
              type="button"
              onClick={handleCopy}
              className="flex items-center gap-1 px-2 py-1 rounded text-[#636A74] hover:text-[#1C2024] hover:bg-[#EAE8E2] transition-colors cursor-pointer text-xs"
              title="Copy snippet"
            >
              {copied ? (
                <>
                  <Check className="w-3.5 h-3.5 text-emerald-600" />
                  <span className="text-[11px] text-emerald-700 font-medium">Copied</span>
                </>
              ) : (
                <>
                  <Copy className="w-3.5 h-3.5" />
                  <span className="text-[11px]">Copy</span>
                </>
              )}
            </button>
          )}
        </div>
      </div>

      {/* Dark Code Block Body */}
      {lines.length > 0 ? (
        <div className="bg-[#14171C] text-[#E6E8EB] p-3.5 overflow-x-auto text-xs font-mono leading-relaxed">
          <table className="w-full border-collapse">
            <tbody>
              {lines.map((line, lIdx) => {
                const currentLineNumber = startLine + lIdx;
                return (
                  <tr key={lIdx} className="hover:bg-white/[0.04]">
                    <td className="pr-4 select-none text-right text-[#8B93A0] w-8 align-top font-mono text-[11px]">
                      {currentLineNumber}
                    </td>
                    <td className="whitespace-pre font-mono text-[#E6E8EB] pr-4">
                      {line}
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      ) : (
        <div className="p-4 bg-[#FAF9F6] text-xs text-[#636A74] flex items-center gap-2 italic">
          <AlertCircle className="w-4 h-4 text-amber-600 flex-shrink-0" />
          <span>Verbatim snippet text was not returned by the API for this citation.</span>
        </div>
      )}
    </div>
  );
};
