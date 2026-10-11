"use client";

import React, { useState } from "react";
import { FileArchive, GitBranch, AlertCircle, Sparkles, CheckCircle2 } from "lucide-react";
import { ZipDropzone } from "./ZipDropzone";
import { GitUrlInput } from "./GitUrlInput";
import { LimitsExplanation } from "./LimitsExplanation";
import { IngestResponse } from "@/lib/types";

interface UploadScreenProps {
  onIngestSuccess: (response: IngestResponse) => void;
}

export const UploadScreen: React.FC<UploadScreenProps> = ({ onIngestSuccess }) => {
  const [activeTab, setActiveTab] = useState<"zip" | "git">("zip");
  const [errorMessage, setErrorMessage] = useState<string | null>(null);
  const [recentSuccess, setRecentSuccess] = useState<IngestResponse | null>(null);

  const handleSuccess = (res: IngestResponse) => {
    setErrorMessage(null);
    setRecentSuccess(res);
    onIngestSuccess(res);
  };

  const handleError = (msg: string) => {
    setErrorMessage(msg);
  };

  return (
    <div className="w-full max-w-4xl mx-auto space-y-8 py-6">
      {/* Intro hero banner */}
      <div className="text-center space-y-3">
        <div className="inline-flex items-center gap-1.5 px-3 py-1 rounded-full bg-[#E6F4F1] text-[#0B6E5F] text-xs font-semibold border border-[#BDE3DC]">
          <Sparkles className="w-3.5 h-3.5" />
          <span>Step 1: Codebase Ingestion</span>
        </div>
        <h1 className="text-3xl sm:text-4xl font-bold tracking-tight text-[#1C2024]">
          Load your repository to begin
        </h1>
        <p className="text-sm text-[#636A74] max-w-xl mx-auto leading-relaxed">
          Upload a local source ZIP or provide a public Git HTTPS repository URL.
          DevMind parses, chunks, and indexes your code safely with zero script execution.
        </p>
      </div>

      {/* Main card container */}
      <div className="bg-white border border-[#E5E2DB] rounded-2xl shadow-sm overflow-hidden">
        {/* Navigation Tabs */}
        <div className="flex border-b border-[#E5E2DB] bg-[#FAF9F6]">
          <button
            type="button"
            onClick={() => {
              setActiveTab("zip");
              setErrorMessage(null);
            }}
            className={`flex-1 flex items-center justify-center gap-2.5 py-4 px-6 text-sm font-semibold transition-colors border-b-2 cursor-pointer ${
              activeTab === "zip"
                ? "border-[#0B6E5F] text-[#0B6E5F] bg-white shadow-xs"
                : "border-transparent text-[#636A74] hover:text-[#1C2024] hover:bg-[#F2EFEB]"
            }`}
          >
            <FileArchive className="w-4 h-4" />
            <span>Upload ZIP Archive</span>
          </button>

          <button
            type="button"
            onClick={() => {
              setActiveTab("git");
              setErrorMessage(null);
            }}
            className={`flex-1 flex items-center justify-center gap-2.5 py-4 px-6 text-sm font-semibold transition-colors border-b-2 cursor-pointer ${
              activeTab === "git"
                ? "border-[#0B6E5F] text-[#0B6E5F] bg-white shadow-xs"
                : "border-transparent text-[#636A74] hover:text-[#1C2024] hover:bg-[#F2EFEB]"
            }`}
          >
            <GitBranch className="w-4 h-4" />
            <span>Public Git URL</span>
          </button>
        </div>

        {/* Tab contents */}
        <div className="p-6 sm:p-8">
          {recentSuccess && (
            <div className="mb-6 p-4 rounded-xl bg-emerald-50 border border-emerald-200 text-emerald-800 text-sm flex items-start gap-3">
              <CheckCircle2 className="w-5 h-5 text-emerald-600 flex-shrink-0 mt-0.5" />
              <div>
                <p className="font-semibold">
                  Repository ready for indexing: {recentSuccess.repo_name}
                </p>
                <p className="text-xs text-emerald-700 mt-0.5">
                  ID: <code className="font-mono bg-emerald-100/70 px-1 py-0.5 rounded">{recentSuccess.repo_id}</code>. Advancing to indexing pipeline...
                </p>
              </div>
            </div>
          )}

          {errorMessage && (
            <div className="mb-6 p-4 rounded-xl bg-red-50 border border-red-200 text-red-800 text-sm flex items-start gap-3">
              <AlertCircle className="w-5 h-5 text-red-600 flex-shrink-0 mt-0.5" />
              <div>
                <p className="font-semibold">Ingestion Error</p>
                <p className="text-xs text-red-700 mt-0.5">{errorMessage}</p>
              </div>
            </div>
          )}

          {activeTab === "zip" ? (
            <ZipDropzone onSuccess={handleSuccess} onError={handleError} />
          ) : (
            <GitUrlInput onSuccess={handleSuccess} onError={handleError} />
          )}
        </div>
      </div>

      {/* Safety & Limits Explanation card */}
      <LimitsExplanation />
    </div>
  );
};
