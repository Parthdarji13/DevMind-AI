"use client";

import React from "react";
import { FileCode, ExternalLink } from "lucide-react";
import { Citation } from "@/lib/types";

interface CitationChipProps {
  index: number;
  citation: Citation;
  onClick: () => void;
  isActive?: boolean;
}

export const CitationChip: React.FC<CitationChipProps> = ({
  index,
  citation,
  onClick,
  isActive = false,
}) => {
  const fileName = citation.file_path.split("/").pop() || citation.file_path;
  const lineRangeText =
    citation.start_line && citation.end_line
      ? `L${citation.start_line}-${citation.end_line}`
      : "File";

  return (
    <button
      type="button"
      onClick={onClick}
      className={`inline-flex items-center gap-1.5 px-2.5 py-1 rounded-lg text-xs font-mono font-medium transition-all shadow-xs cursor-pointer border ${
        isActive
          ? "bg-[#0B6E5F] text-white border-[#08493F] ring-2 ring-[#0B6E5F]/30"
          : "bg-[#E6F4F1] hover:bg-[#D5EFEA] text-[#08493F] border-[#BDE3DC]"
      }`}
      title={`${citation.file_path} (Lines ${citation.start_line}-${citation.end_line})`}
    >
      <span className="font-bold text-[11px] bg-black/10 px-1 py-0.2 rounded">
        [{index}]
      </span>
      <FileCode className="w-3.5 h-3.5 opacity-80" />
      <span className="truncate max-w-[140px] sm:max-w-[200px]" title={citation.file_path}>
        {fileName}
      </span>
      <span className="text-[10px] opacity-75 font-sans">
        ({lineRangeText})
      </span>
      <ExternalLink className="w-3 h-3 opacity-60 ml-0.5" />
    </button>
  );
};
