"use client";

import React, { useState } from "react";
import {
  Package,
  Image as ImageIcon,
  FileCode,
  Zap,
  Cpu,
  ShieldCheck,
  ShieldAlert,
  HardDrive,
  FileQuestion,
  ChevronDown,
  ChevronUp,
  HelpCircle,
  CheckCircle2,
  FolderX,
  Binary,
  FileArchive,
  Database,
} from "lucide-react";

interface SkippedBreakdownProps {
  skippedBreakdown: Record<string, number>;
  languages?: Record<string, number>;
}

interface CategoryMeta {
  label: string;
  description: string;
  examples: string;
  icon: React.ElementType;
  iconBg: string;
  iconColor: string;
  isSecret?: boolean;
}

const CATEGORY_MAP: Record<string, CategoryMeta> = {
  dependency: {
    label: "Third-Party Libraries & Dependencies",
    description: "External packages skipped so the AI answers from your original code, not library code.",
    examples: "node_modules, venv, vendor",
    icon: Package,
    iconBg: "bg-emerald-50 text-emerald-700 border-emerald-200",
    iconColor: "text-emerald-700",
  },
  node_modules: {
    label: "Third-Party Libraries & Dependencies",
    description: "External packages skipped so the AI answers from your original code, not library code.",
    examples: "node_modules, venv, vendor",
    icon: Package,
    iconBg: "bg-emerald-50 text-emerald-700 border-emerald-200",
    iconColor: "text-emerald-700",
  },
  binary_media: {
    label: "Images, Icons & Media",
    description: "Graphic assets, media, and binary documents that do not contain readable code.",
    examples: ".png, .svg, .ico, .mp4, .pdf",
    icon: ImageIcon,
    iconBg: "bg-amber-50 text-amber-700 border-amber-200",
    iconColor: "text-amber-700",
  },
  binary_files: {
    label: "Images, Icons & Media",
    description: "Graphic assets, media, and binary documents that do not contain readable code.",
    examples: ".png, .svg, .ico, .mp4, .pdf",
    icon: Binary,
    iconBg: "bg-amber-50 text-amber-700 border-amber-200",
    iconColor: "text-amber-700",
  },
  minified_lockfile: {
    label: "Package Manager Lockfiles",
    description: "Auto-generated dependency trees with thousands of checksum hashes.",
    examples: "package-lock.json, yarn.lock, pnpm-lock",
    icon: FileCode,
    iconBg: "bg-blue-50 text-blue-700 border-blue-200",
    iconColor: "text-blue-700",
  },
  generated: {
    label: "Package Manager Lockfiles",
    description: "Auto-generated dependency trees with thousands of checksum hashes.",
    examples: "package-lock.json, yarn.lock, pnpm-lock",
    icon: FileArchive,
    iconBg: "bg-blue-50 text-blue-700 border-blue-200",
    iconColor: "text-blue-700",
  },
  cache_runtime: {
    label: "Build Caches & Temporary Files",
    description: "Temporary compiler output and runtime cache files generated during development.",
    examples: ".next/cache, __pycache__, .turbo",
    icon: Zap,
    iconBg: "bg-purple-50 text-purple-700 border-purple-200",
    iconColor: "text-purple-700",
  },
  build_artifact: {
    label: "Compiled Output Bundles",
    description: "Pre-compiled production bundles and minified distribution files.",
    examples: "dist/, build/, out/",
    icon: Cpu,
    iconBg: "bg-slate-50 text-slate-700 border-slate-200",
    iconColor: "text-slate-700",
  },
  build_dist: {
    label: "Compiled Output Bundles",
    description: "Pre-compiled production bundles and minified distribution files.",
    examples: "dist/, build/, out/",
    icon: Cpu,
    iconBg: "bg-slate-50 text-slate-700 border-slate-200",
    iconColor: "text-slate-700",
  },
  secret: {
    label: "Private Secrets & API Credentials",
    description: "Environment files and API keys protected and never read to protect your privacy.",
    examples: ".env, *.key, *.pem (zero data read)",
    icon: ShieldAlert,
    iconBg: "bg-red-50 text-red-700 border-red-200",
    iconColor: "text-red-700",
    isSecret: true,
  },
  secret_files: {
    label: "Private Secrets & API Credentials",
    description: "Environment files and API keys protected and never read to protect your privacy.",
    examples: ".env, *.key, *.pem (zero data read)",
    icon: ShieldAlert,
    iconBg: "bg-red-50 text-red-700 border-red-200",
    iconColor: "text-red-700",
    isSecret: true,
  },
  oversized: {
    label: "Oversized Data Files (>1 MB)",
    description: "Large data dumps or bundled assets exceeding the single-file size threshold.",
    examples: "Large SQL dumps, datasets",
    icon: HardDrive,
    iconBg: "bg-orange-50 text-orange-700 border-orange-200",
    iconColor: "text-orange-700",
  },
  large_files: {
    label: "Oversized Data Files (>1 MB)",
    description: "Large data dumps or bundled assets exceeding the single-file size threshold.",
    examples: "Large SQL dumps, datasets",
    icon: Database,
    iconBg: "bg-orange-50 text-orange-700 border-orange-200",
    iconColor: "text-orange-700",
  },
  unsupported: {
    label: "Unsupported File Formats",
    description: "Non-code files that cannot be parsed as programming languages.",
    examples: "Unknown binary formats",
    icon: FileQuestion,
    iconBg: "bg-gray-50 text-gray-700 border-gray-200",
    iconColor: "text-gray-700",
  },
  unsupported_ext: {
    label: "Unsupported File Formats",
    description: "Non-code files that cannot be parsed as programming languages.",
    examples: "Unknown binary formats",
    icon: FileQuestion,
    iconBg: "bg-gray-50 text-gray-700 border-gray-200",
    iconColor: "text-gray-700",
  },
};

export const SkippedBreakdown: React.FC<SkippedBreakdownProps> = ({
  skippedBreakdown,
  languages = {},
}) => {
  const [showFaq, setShowFaq] = useState(false);
  const [showZeroCounts, setShowZeroCounts] = useState(false);

  // Group into active (count > 0) vs clean/zero (count === 0)
  const allEntries = Object.entries(skippedBreakdown);
  const activeEntries = allEntries.filter(([, count]) => count > 0);
  const zeroEntries = allEntries.filter(([, count]) => count === 0);

  const totalSkipped = allEntries.reduce((sum, [, count]) => sum + count, 0);
  const langEntries = Object.entries(languages).sort((a, b) => b[1] - a[1]);

  return (
    <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
      {/* What was excluded card */}
      <div className="rounded-2xl border border-[#E5E2DB] bg-white p-5 sm:p-6 shadow-xs flex flex-col justify-between">
        <div>
          {/* Header with clear title and friendly explanation */}
          <div className="mb-4">
            <div className="flex items-center justify-between gap-2">
              <h3 className="text-xs font-bold uppercase tracking-wider text-[#1C2024] flex items-center gap-1.5">
                <span>Non-Code Files Excluded</span>
                <span className="text-[10px] font-medium font-mono px-2 py-0.5 rounded-full bg-[#FAF9F6] border border-[#E5E2DB] text-[#636A74] normal-case">
                  {totalSkipped.toLocaleString()} total
                </span>
              </h3>
              <button
                type="button"
                onClick={() => setShowFaq(!showFaq)}
                className="inline-flex items-center gap-1 text-[11px] font-medium text-[#0B6E5F] hover:underline cursor-pointer"
                title="Why does DevMind filter files?"
              >
                <HelpCircle className="w-3.5 h-3.5" />
                <span>Why excluded?</span>
              </button>
            </div>
            <p className="text-xs text-[#636A74] mt-1 leading-relaxed">
              To keep answers fast, accurate, and secure, DevMind indexes only your source code. External packages, media, and temporary caches are filtered out automatically.
            </p>
          </div>

          {/* Collapsible Easy FAQ */}
          {showFaq && (
            <div className="mb-4 p-3.5 rounded-xl bg-[#F0FAF7] border border-[#BCE3DB] text-xs space-y-2 text-[#085449] animate-fadeIn">
              <div className="font-semibold flex items-center gap-1.5">
                <CheckCircle2 className="w-4 h-4 text-[#0B6E5F]" />
                <span>Why are these files excluded?</span>
              </div>
              <ul className="space-y-1.5 pl-4 list-disc text-[11px] leading-relaxed text-[#1D4E44]">
                <li>
                  <strong>Focus on your code:</strong> Skipping <code className="bg-white/80 px-1 py-0.5 rounded border border-[#BCE3DB]">node_modules</code> ensures AI citations reference the code <em>you</em> wrote, not thousands of third-party dependencies.
                </li>
                <li>
                  <strong>Better performance:</strong> Ignoring images, compiled binaries, and lockfiles keeps search lightning-fast and responsive.
                </li>
                <li>
                  <strong>Privacy & Security:</strong> Sensitive credentials (like <code className="bg-white/80 px-1 py-0.5 rounded border border-[#BCE3DB]">.env</code>) are identified by name and immediately excluded without ever being read.
                </li>
              </ul>
            </div>
          )}

          {/* Active Categories (count > 0) */}
          {activeEntries.length > 0 ? (
            <div className="space-y-2.5">
              {activeEntries.map(([key, count]) => {
                const meta: CategoryMeta = CATEGORY_MAP[key] || {
                  label: key.replace(/_/g, " "),
                  description: "Non-source files excluded during repository filtering.",
                  examples: "",
                  icon: FolderX,
                  iconBg: "bg-gray-50 text-gray-700 border-gray-200",
                  iconColor: "text-gray-700",
                };
                const Icon = meta.icon;
                const isSecret = meta.isSecret;

                return (
                  <div
                    key={key}
                    className={`p-3 rounded-xl border text-xs transition-all ${
                      isSecret
                        ? "border-red-200 bg-red-50/60 text-red-900"
                        : "border-[#EAE8E2] bg-[#FAF9F6] text-[#1C2024] hover:border-[#D6D2CA]"
                    }`}
                  >
                    <div className="flex items-start justify-between gap-3">
                      <div className="flex items-start gap-3 min-w-0">
                        <div
                          className={`w-7 h-7 rounded-lg border flex items-center justify-center flex-shrink-0 mt-0.5 ${meta.iconBg}`}
                        >
                          <Icon className="w-4 h-4" />
                        </div>
                        <div className="min-w-0">
                          <div className="flex items-center gap-1.5 flex-wrap">
                            <span className="font-semibold text-[#1C2024]">
                              {meta.label}
                            </span>
                          </div>
                          <p className="text-[11px] text-[#636A74] mt-0.5 leading-normal">
                            {meta.description}
                          </p>
                          {meta.examples && (
                            <span className="inline-block mt-1 font-mono text-[10px] text-[#868E96] bg-white px-1.5 py-0.5 rounded border border-[#E5E2DB]">
                              e.g. {meta.examples}
                            </span>
                          )}
                        </div>
                      </div>

                      <div className="flex-shrink-0">
                        <span
                          className={`font-mono font-bold text-xs px-2.5 py-1 rounded-full border shadow-2xs ${
                            isSecret
                              ? "bg-red-100 text-red-800 border-red-300"
                              : "bg-white text-[#1C2024] border-[#E5E2DB]"
                          }`}
                        >
                          {count.toLocaleString()}
                        </span>
                      </div>
                    </div>
                  </div>
                );
              })}
            </div>
          ) : (
            <div className="p-4 rounded-xl bg-[#FAF9F6] border border-[#EAE8E2] text-center text-xs text-[#636A74]">
              No files were skipped in this repository. All discovered files were indexed!
            </div>
          )}

          {/* Zero-count categories checklist (Passed Security & Health) */}
          {zeroEntries.length > 0 && (
            <div className="mt-4 pt-3 border-t border-[#EAE8E2]">
              <button
                type="button"
                onClick={() => setShowZeroCounts(!showZeroCounts)}
                className="w-full flex items-center justify-between text-xs text-[#636A74] hover:text-[#1C2024] py-1 transition-colors cursor-pointer"
              >
                <span className="flex items-center gap-1.5 text-[11px] font-medium">
                  <ShieldCheck className="w-3.5 h-3.5 text-emerald-600" />
                  <span>
                    Clean Checks: {zeroEntries.length} categories with 0 files excluded
                  </span>
                </span>
                {showZeroCounts ? (
                  <ChevronUp className="w-3.5 h-3.5 text-[#868E96]" />
                ) : (
                  <ChevronDown className="w-3.5 h-3.5 text-[#868E96]" />
                )}
              </button>

              {showZeroCounts && (
                <div className="mt-2 grid grid-cols-1 sm:grid-cols-2 gap-1.5 animate-fadeIn">
                  {zeroEntries.map(([key]) => {
                    const meta = CATEGORY_MAP[key] || {
                      label: key.replace(/_/g, " "),
                    };
                    return (
                      <div
                        key={key}
                        className="flex items-center justify-between px-2.5 py-1.5 rounded-lg bg-[#FAF9F6] border border-[#EAE8E2] text-[11px] text-[#636A74]"
                      >
                        <span className="truncate">{meta.label}</span>
                        <span className="font-mono text-[10px] text-emerald-700 font-semibold bg-emerald-50 px-1.5 py-0.2 rounded border border-emerald-200">
                          0
                        </span>
                      </div>
                    );
                  })}
                </div>
              )}
            </div>
          )}
        </div>

        {/* Bottom reassurance banner */}
        <div className="mt-4 p-2.5 rounded-xl bg-[#F8F7F4] border border-[#EAE8E2] text-[11px] text-[#636A74] flex items-center gap-2">
          <CheckCircle2 className="w-4 h-4 text-[#0B6E5F] flex-shrink-0" />
          <span>
            <strong>Your source code is 100% indexed.</strong> These exclusions only remove third-party dependencies and clutter.
          </span>
        </div>
      </div>

      {/* Languages detected card */}
      <div className="rounded-2xl border border-[#E5E2DB] bg-white p-5 sm:p-6 shadow-xs flex flex-col justify-between">
        <div>
          <div className="mb-4">
            <h3 className="text-xs font-bold uppercase tracking-wider text-[#1C2024]">
              Detected Source Code Languages
            </h3>
            <p className="text-xs text-[#636A74] mt-1 leading-relaxed">
              Breakdown of your active codebase files parsed into AST chunks and indexed for search.
            </p>
          </div>

          {langEntries.length > 0 ? (
            <div className="space-y-3">
              {langEntries.map(([lang, count]) => {
                const total = langEntries.reduce((sum, item) => sum + item[1], 0);
                const percentage = Math.round((count / (total || 1)) * 100);

                return (
                  <div key={lang} className="space-y-1">
                    <div className="flex items-center justify-between text-xs">
                      <span className="font-semibold text-[#1C2024]">{lang}</span>
                      <span className="text-[#636A74] font-mono text-[11px]">
                        {count.toLocaleString()} {count === 1 ? "file" : "files"} ({percentage}%)
                      </span>
                    </div>
                    <div className="w-full h-2 rounded-full bg-[#ECE9E3] overflow-hidden">
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

        <div className="mt-4 p-2.5 rounded-xl bg-[#F8F7F4] border border-[#EAE8E2] text-[11px] text-[#636A74] flex items-center justify-between">
          <span>
            Total indexed source files:
          </span>
          <span className="font-mono font-bold text-[#1C2024]">
            {langEntries.reduce((sum, item) => sum + item[1], 0).toLocaleString()} files
          </span>
        </div>
      </div>
    </div>
  );
};
