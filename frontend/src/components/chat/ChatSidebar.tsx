"use client";

import React from "react";
import {
  FolderGit2,
  FileCode2,
  CheckCircle2,
  Layers,
  RotateCcw,
  Clock,
  ShieldCheck,
} from "lucide-react";
import { IngestionProgress, IngestResponse } from "@/lib/types";

interface ChatSidebarProps {
  repo: IngestResponse;
  progress: IngestionProgress | null;
  onNewRepo: () => void;
}

export const ChatSidebar: React.FC<ChatSidebarProps> = ({
  repo,
  progress,
  onNewRepo,
}) => {
  const metrics = progress?.metrics;
  const languages = progress?.languages || {};
  const langEntries = Object.entries(languages).sort((a, b) => b[1] - a[1]);

  const totalFiles = metrics?.indexed_files || 0;
  const totalLines = metrics?.total_lines || 0;
  const skippedCount = metrics?.skipped_files || 0;

  return (
    <aside className="w-full lg:w-80 flex-shrink-0 space-y-4">
      {/* Repository Overview Card */}
      <div className="rounded-2xl border border-[#E5E2DB] bg-white p-5 shadow-xs space-y-4">
        {/* Header */}
        <div className="space-y-1.5 border-b border-[#EAE8E2] pb-4">
          <div className="flex items-center justify-between">
            <span className="text-[10px] font-bold uppercase tracking-wider text-[#636A74]">
              Repository
            </span>
            <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-[11px] font-semibold bg-emerald-50 text-emerald-700 border border-emerald-200">
              <CheckCircle2 className="w-3 h-3" />
              <span>Ready</span>
            </span>
          </div>

          <h2 className="text-base font-bold text-[#1C2024] truncate" title={repo.repo_name}>
            {repo.repo_name}
          </h2>

          <p className="text-[11px] font-mono text-[#636A74] truncate">
            ID: {repo.repo_id}
          </p>
        </div>

        {/* 2 Stat Tiles */}
        <div className="grid grid-cols-2 gap-2.5">
          <div className="p-3 rounded-xl bg-[#FAF9F6] border border-[#EAE8E2]">
            <div className="flex items-center gap-1.5 text-[11px] font-semibold text-[#636A74]">
              <FileCode2 className="w-3.5 h-3.5 text-[#0B6E5F]" />
              <span>Indexed</span>
            </div>
            <div className="text-lg font-bold font-mono text-[#1C2024] mt-1">
              {totalFiles.toLocaleString()}
            </div>
            <div className="text-[10px] text-[#636A74]">source files</div>
          </div>

          <div className="p-3 rounded-xl bg-[#FAF9F6] border border-[#EAE8E2]">
            <div className="flex items-center gap-1.5 text-[11px] font-semibold text-[#636A74]">
              <Layers className="w-3.5 h-3.5 text-[#0B6E5F]" />
              <span>Lines</span>
            </div>
            <div className="text-lg font-bold font-mono text-[#1C2024] mt-1">
              {totalLines > 0 ? totalLines.toLocaleString() : "--"}
            </div>
            <div className="text-[10px] text-[#636A74]">total parsed</div>
          </div>
        </div>

        {/* Language Breakdown */}
        {langEntries.length > 0 && (
          <div className="space-y-2 border-t border-[#EAE8E2] pt-3">
            <span className="text-[11px] font-semibold uppercase tracking-wider text-[#636A74]">
              Languages
            </span>
            <div className="space-y-2">
              {langEntries.slice(0, 5).map(([lang, count]) => {
                const total = langEntries.reduce((acc, curr) => acc + curr[1], 0);
                const pct = Math.round((count / (total || 1)) * 100);

                return (
                  <div key={lang} className="space-y-0.5">
                    <div className="flex justify-between text-xs text-[#1C2024]">
                      <span className="font-medium truncate">{lang}</span>
                      <span className="font-mono text-[#636A74] text-[11px]">
                        {count} ({pct}%)
                      </span>
                    </div>
                    <div className="w-full h-1 rounded-full bg-[#ECE9E3] overflow-hidden">
                      <div
                        className="h-full bg-[#0B6E5F] rounded-full"
                        style={{ width: `${pct}%` }}
                      />
                    </div>
                  </div>
                );
              })}
            </div>
          </div>
        )}

        {/* Skipped Summary */}
        <div className="border-t border-[#EAE8E2] pt-3 text-xs text-[#636A74] space-y-1.5">
          <div className="flex items-center justify-between">
            <span>Skipped files:</span>
            <span className="font-mono font-semibold text-[#1C2024]">{skippedCount.toLocaleString()}</span>
          </div>
          <div className="flex items-center gap-1.5 text-[11px] text-[#636A74]">
            <Clock className="w-3 h-3 text-[#A09D96]" />
            <span>Index retained for 7 days</span>
          </div>
        </div>

        {/* New Repository Button */}
        <button
          type="button"
          onClick={onNewRepo}
          className="w-full flex items-center justify-center gap-2 py-2 px-3 rounded-lg border border-[#D6D2CA] hover:bg-[#F9F8F6] text-[#1C2024] text-xs font-semibold transition-colors cursor-pointer"
        >
          <RotateCcw className="w-3.5 h-3.5 text-[#636A74]" />
          <span>Switch Repository</span>
        </button>
      </div>

      {/* Grounded RAG Guarantee Badge */}
      <div className="p-3.5 rounded-xl border border-[#BDE3DC] bg-[#E6F4F1]/60 text-xs text-[#0B6E5F] space-y-1">
        <div className="flex items-center gap-1.5 font-semibold">
          <ShieldCheck className="w-4 h-4 text-[#0B6E5F]" />
          <span>Strict Citation Grounding</span>
        </div>
        <p className="text-[11px] leading-relaxed text-[#085449]">
          Every factual answer links to real line numbers. The assistant will abstain rather than invent unverified code.
        </p>
      </div>
    </aside>
  );
};
