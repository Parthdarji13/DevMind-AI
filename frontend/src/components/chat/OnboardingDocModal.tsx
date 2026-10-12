"use client";

import React, { useState, useEffect } from "react";
import {
  FileText,
  X,
  Download,
  Copy,
  Check,
  Loader2,
  AlertCircle,
  FileCode,
  Layers,
} from "lucide-react";
import { OnboardingDocResponse } from "@/lib/types";
import { getOnboardingDoc } from "@/lib/api";
import { SafeMarkdown } from "./SafeMarkdown";

interface OnboardingDocModalProps {
  repoId: string;
  repoName: string;
  isOpen: boolean;
  onClose: () => void;
}

export const OnboardingDocModal: React.FC<OnboardingDocModalProps> = ({
  repoId,
  repoName,
  isOpen,
  onClose,
}) => {
  const [doc, setDoc] = useState<OnboardingDocResponse | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [copied, setCopied] = useState(false);

  useEffect(() => {
    if (isOpen && !doc) {
      setLoading(true);
      setError(null);
      getOnboardingDoc(repoId)
        .then((res) => setDoc(res))
        .catch((err) => setError(err?.message || "Failed to generate onboarding guide."))
        .finally(() => setLoading(false));
    }
  }, [isOpen, repoId, doc]);

  if (!isOpen) return null;

  const handleDownload = () => {
    if (!doc) return;
    const blob = new Blob([doc.content], { type: "text/markdown;charset=utf-8" });
    const url = URL.createObjectURL(blob);
    const link = document.createElement("a");
    const safeName = repoName.replace(/[^a-zA-Z0-9_-]/g, "_");
    link.href = url;
    link.download = `${safeName}_ONBOARDING_GUIDE.md`;
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
    URL.revokeObjectURL(url);
  };

  const handleCopy = async () => {
    if (!doc) return;
    try {
      await navigator.clipboard.writeText(doc.content);
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    } catch {}
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 backdrop-blur-xs p-4 overflow-y-auto">
      <div className="bg-white rounded-2xl max-w-4xl w-full max-h-[90vh] shadow-2xl border border-[#E5E2DB] flex flex-col overflow-hidden animate-in fade-in zoom-in-95 duration-200">
        {/* Header */}
        <div className="px-6 py-4 border-b border-[#EAE8E2] bg-[#FAF9F6] flex items-center justify-between">
          <div className="flex items-center gap-2.5">
            <div className="w-8 h-8 rounded-xl bg-[#E6F4F1] text-[#0B6E5F] flex items-center justify-center shadow-xs">
              <FileText className="w-4 h-4" />
            </div>
            <div>
              <h2 className="text-base font-bold text-[#1C2024] leading-tight">
                Developer Onboarding & Architecture Guide
              </h2>
              <p className="text-xs text-[#636A74]">
                1-Click evidence-grounded architecture overview for {repoName}
              </p>
            </div>
          </div>

          <div className="flex items-center gap-2">
            {doc && (
              <>
                <button
                  type="button"
                  onClick={handleCopy}
                  className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-medium text-[#636A74] bg-white border border-[#E5E2DB] hover:bg-[#FAF9F6] transition-colors cursor-pointer"
                >
                  {copied ? <Check className="w-3.5 h-3.5 text-[#0B6E5F]" /> : <Copy className="w-3.5 h-3.5" />}
                  <span>{copied ? "Copied" : "Copy"}</span>
                </button>

                <button
                  type="button"
                  onClick={handleDownload}
                  className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-semibold text-white bg-[#0B6E5F] hover:bg-[#085449] transition-colors cursor-pointer shadow-xs"
                >
                  <Download className="w-3.5 h-3.5" />
                  <span>Download .md</span>
                </button>
              </>
            )}

            <button
              type="button"
              onClick={onClose}
              className="p-1 rounded-lg text-[#636A74] hover:text-[#1C2024] hover:bg-black/5 transition-colors cursor-pointer ml-2"
            >
              <X className="w-5 h-5" />
            </button>
          </div>
        </div>

        {/* Badges Bar */}
        {doc && (
          <div className="px-6 py-2.5 border-b border-[#EAE8E2] bg-white flex flex-wrap items-center gap-3 text-xs text-[#636A74]">
            <span className="flex items-center gap-1 font-medium">
              <FileCode className="w-3.5 h-3.5 text-[#0B6E5F]" />
              <span>{doc.file_count} files analyzed</span>
            </span>
            <span className="flex items-center gap-1 font-medium">
              <Layers className="w-3.5 h-3.5 text-[#0B6E5F]" />
              <span>Languages: {doc.languages.join(", ") || "General"}</span>
            </span>
            <span className="text-[11px] text-[#A09D96]">
              • Cited line-level evidence grounded
            </span>
          </div>
        )}

        {/* Content Area */}
        <div className="flex-1 overflow-y-auto p-6 sm:p-8 space-y-4">
          {loading && (
            <div className="py-20 flex flex-col items-center justify-center space-y-3 text-[#0B6E5F]">
              <Loader2 className="w-8 h-8 animate-spin" />
              <p className="text-sm font-semibold text-[#1C2024]">Synthesizing Developer Onboarding Guide...</p>
              <p className="text-xs text-[#636A74]">Analyzing directory architecture, entrypoints, and service contracts</p>
            </div>
          )}

          {error && (
            <div className="flex items-center gap-2 p-4 rounded-xl bg-red-50 border border-red-200 text-xs text-red-800">
              <AlertCircle className="w-4 h-4 text-red-600 flex-shrink-0" />
              <span>{error}</span>
            </div>
          )}

          {doc && (
            <div className="bg-white border border-[#E5E2DB] rounded-2xl p-6 sm:p-8 shadow-xs">
              <SafeMarkdown content={doc.content} />
            </div>
          )}
        </div>
      </div>
    </div>
  );
};
