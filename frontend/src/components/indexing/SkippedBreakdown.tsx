"use client";

import React from "react";
import { FolderX, ShieldAlert, Cpu, Database, Binary, FileArchive } from "lucide-react";

interface SkippedBreakdownProps {
  skippedBreakdown: Record<string, number>;
  languages?: Record<string, number>;
}

export const SkippedBreakdown: React.FC<SkippedBreakdownProps> = ({
  skippedBreakdown,
  languages = {},
}) => {
  const categoryLabels: Record<
    string,
    { label: string; icon: React.ElementType; isSecret?: boolean }
  > = {
    node_modules: { label: "node_modules & Dependencies", icon: FolderX },
    build_dist: { label: "Build & Dist Artifacts", icon: Cpu },
    binary_files: { label: "Binary & Media Files", icon: Binary },
    generated: { label: "Generated & Lockfiles", icon: FileArchive },
    secret_files: { label: "Secrets & API Credentials (Redacted)", icon: ShieldAlert, isSecret: true },
    large_files: { label: "Oversized Files (>1MB)", icon: Database },
    unsupported_ext: { label: "Unsupported Extensions", icon: FolderX },
  };

  const hasSkipped = Object.keys(skippedBreakdown).length > 0;
  const langEntries = Object.entries(languages).sort((a, b) => b[1] - a[1]);

  return (
    <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
      {/* What was skipped card */}
      <div className="rounded-2xl border border-[#E5E2DB] bg-white p-5 sm:p-6 shadow-xs">
        <div className="mb-4">
          <h3 className="text-xs font-semibold uppercase tracking-wider text-[#1C2024]">
            Files Skipped by Filter Policy
          </h3>
          <p className="text-xs text-[#636A74] mt-0.5">
            Automated pruning keeps indexing fast, secure, and accurate.
          </p>
        </div>

        {hasSkipped ? (
          <div className="space-y-2.5">
            {Object.entries(skippedBreakdown).map(([key, count]) => {
              const meta = categoryLabels[key] || {
                label: key.replace(/_/g, " "),
                icon: FolderX,
              };
              const Icon = meta.icon;
              const isSecret = meta.isSecret;

              return (
                <div
                  key={key}
                  className={`flex items-center justify-between p-2.5 rounded-xl border text-xs transition-colors ${
                    isSecret
                      ? "border-red-200 bg-red-50/60 text-red-900"
                      : "border-[#EAE8E2] bg-[#FAF9F6] text-[#1C2024]"
                  }`}
                >
                  <div className="flex items-center gap-2.5 min-w-0">
                    <Icon
                      className={`w-4 h-4 flex-shrink-0 ${
                        isSecret ? "text-red-600" : "text-[#636A74]"
                      }`}
                    />
                    <span className="font-medium truncate">{meta.label}</span>
                  </div>

                  <span
                    className={`font-mono font-semibold px-2 py-0.5 rounded-full ${
                      isSecret
                        ? "bg-red-100 text-red-800"
                        : "bg-white text-[#636A74] border border-[#E5E2DB]"
                    }`}
                  >
                    {count.toLocaleString()}
                  </span>
                </div>
              );
            })}
          </div>
        ) : (
          <p className="text-xs text-[#636A74] italic py-4">
            No files were skipped in this repository.
          </p>
        )}
      </div>

      {/* Languages detected card */}
      <div className="rounded-2xl border border-[#E5E2DB] bg-white p-5 sm:p-6 shadow-xs">
        <div className="mb-4">
          <h3 className="text-xs font-semibold uppercase tracking-wider text-[#1C2024]">
            Detected Languages in Codebase
          </h3>
          <p className="text-xs text-[#636A74] mt-0.5">
            Breakdown of source files parsed for AST and text indexing.
          </p>
        </div>

        {langEntries.length > 0 ? (
          <div className="space-y-2.5">
            {langEntries.map(([lang, count]) => {
              const total = langEntries.reduce((sum, item) => sum + item[1], 0);
              const percentage = Math.round((count / (total || 1)) * 100);

              return (
                <div key={lang} className="space-y-1">
                  <div className="flex items-center justify-between text-xs">
                    <span className="font-medium text-[#1C2024]">{lang}</span>
                    <span className="text-[#636A74] font-mono">
                      {count} files ({percentage}%)
                    </span>
                  </div>
                  <div className="w-full h-1.5 rounded-full bg-[#ECE9E3] overflow-hidden">
                    <div
                      className="h-full bg-[#0B6E5F] rounded-full transition-all duration-300"
                      style={{ width: `${percentage}%` }}
                    />
                  </div>
                </div>
              );
            })}
          </div>
        ) : (
          <p className="text-xs text-[#636A74] italic py-4">
            Analyzing source language distribution...
          </p>
        )}
      </div>
    </div>
  );
};
