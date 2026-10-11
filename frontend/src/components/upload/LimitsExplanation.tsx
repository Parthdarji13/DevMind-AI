"use client";

import React from "react";
import { ShieldCheck, HardDrive, FileCode, Ban, Lock, Cpu } from "lucide-react";

export const LimitsExplanation: React.FC = () => {
  const cards = [
    {
      icon: HardDrive,
      title: "Archive & Size Limits",
      detail: "Up to 100 MB archive size and up to 500,000 LOC across repositories.",
      badge: "Max 100 MB",
    },
    {
      icon: FileCode,
      title: "File Capacity",
      detail: "Indexes up to 3,000 source files per repository with AST-bounded chunking.",
      badge: "3,000 files",
    },
    {
      icon: Ban,
      title: "Smart Filtering",
      detail: "Automatically skips node_modules, lockfiles, dist/build, binaries, and minified bundles.",
      badge: "Auto-pruned",
    },
    {
      icon: Lock,
      title: "Zero Code Execution",
      detail: "No code or scripts are ever executed. Repositories are analyzed purely via static analysis & AST.",
      badge: "Safe sandbox",
    },
    {
      icon: ShieldCheck,
      title: "Secret Redaction",
      detail: "Integrated Shannon entropy scanner redacts API keys, credentials, and tokens prior to indexing.",
      badge: "Automated scan",
    },
    {
      icon: Cpu,
      title: "Hybrid Retrieval",
      detail: "Combines Okapi BM25 keyword matching with dense semantic embeddings via Reciprocal Rank Fusion.",
      badge: "BM25 + Dense",
    },
  ];

  return (
    <div className="rounded-2xl border border-[#E5E2DB] bg-white p-6 shadow-sm">
      <div className="mb-4">
        <h3 className="text-sm font-semibold uppercase tracking-wider text-[#1C2024]">
          Repository Capabilities & Guardrails
        </h3>
        <p className="text-xs text-[#636A74] mt-0.5">
          DevMind AI operates safely within predictable resource boundaries.
        </p>
      </div>

      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-3.5">
        {cards.map((item, idx) => {
          const Icon = item.icon;
          return (
            <div
              key={idx}
              className="p-3.5 rounded-xl border border-[#EAE8E2] bg-[#FAF9F6] hover:border-[#D6D2CA] transition-colors flex flex-col justify-between"
            >
              <div>
                <div className="flex items-center justify-between mb-2">
                  <div className="w-7 h-7 rounded-lg bg-[#E6F4F1] text-[#0B6E5F] flex items-center justify-center">
                    <Icon className="w-4 h-4" />
                  </div>
                  <span className="text-[10px] font-semibold px-2 py-0.5 rounded-full bg-white text-[#636A74] border border-[#E5E2DB]">
                    {item.badge}
                  </span>
                </div>
                <h4 className="text-xs font-semibold text-[#1C2024] mb-1">
                  {item.title}
                </h4>
                <p className="text-[11px] leading-relaxed text-[#636A74]">
                  {item.detail}
                </p>
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
};
