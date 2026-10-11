"use client";

import React, { useState } from "react";
import { GitBranch, Globe, ArrowRight, Loader2, AlertCircle, CheckCircle2 } from "lucide-react";
import { importGitRepository, ApiError } from "@/lib/api";
import { IngestResponse } from "@/lib/types";

interface GitUrlInputProps {
  onSuccess: (response: IngestResponse) => void;
  onError: (errorMessage: string) => void;
}

export const GitUrlInput: React.FC<GitUrlInputProps> = ({ onSuccess, onError }) => {
  const [url, setUrl] = useState("");
  const [isLoading, setIsLoading] = useState(false);
  const [validationError, setValidationError] = useState<string | null>(null);

  const sampleRepos = [
    { name: "FastAPI", url: "https://github.com/fastapi/fastapi" },
    { name: "Express", url: "https://github.com/expressjs/express" },
    { name: "Redux", url: "https://github.com/reduxjs/redux" },
  ];

  const validateUrl = (input: string): boolean => {
    setValidationError(null);
    const clean = input.trim();

    if (!clean) {
      setValidationError("Please enter a public Git repository URL.");
      return false;
    }

    if (!clean.startsWith("https://")) {
      setValidationError("Only HTTPS URLs are permitted (e.g., https://github.com/owner/repo).");
      return false;
    }

    if (clean.includes("@") || clean.includes("://") && clean.split("://")[1]?.includes(":")) {
      setValidationError("Credentials inside URLs are strictly forbidden for security reasons.");
      return false;
    }

    return true;
  };

  const handleSubmit = async (e?: React.FormEvent) => {
    if (e) e.preventDefault();
    if (!validateUrl(url)) {
      onError(validationError || "Invalid URL");
      return;
    }

    setIsLoading(true);
    setValidationError(null);

    try {
      const response = await importGitRepository(url.trim());
      onSuccess(response);
    } catch (err: unknown) {
      const msg = err instanceof ApiError ? err.message : "Failed to import Git repository.";
      onError(msg);
    } finally {
      setIsLoading(false);
    }
  };

  return (
    <div className="space-y-4">
      <form onSubmit={handleSubmit} className="space-y-4">
        <div className="space-y-1.5">
          <label
            htmlFor="git-repo-url"
            className="block text-xs font-semibold text-[#1C2024] uppercase tracking-wider"
          >
            Public Git Repository URL
          </label>
          <div className="relative">
            <div className="absolute inset-y-0 left-0 pl-3.5 flex items-center pointer-events-none text-[#636A74]">
              <Globe className="w-4 h-4" />
            </div>
            <input
              id="git-repo-url"
              type="url"
              value={url}
              onChange={(e) => {
                setUrl(e.target.value);
                setValidationError(null);
              }}
              placeholder="https://github.com/owner/repository"
              disabled={isLoading}
              className="w-full pl-10 pr-4 py-2.5 bg-white border border-[#D6D2CA] focus:border-[#0B6E5F] focus:ring-2 focus:ring-[#0B6E5F]/15 rounded-xl text-sm text-[#1C2024] placeholder-[#A09D96] transition-all outline-none"
            />
          </div>
        </div>

        {/* Quick sample repositories */}
        <div className="flex items-center gap-2 text-xs text-[#636A74]">
          <span className="font-medium">Try example:</span>
          {sampleRepos.map((sample) => (
            <button
              key={sample.name}
              type="button"
              disabled={isLoading}
              onClick={() => {
                setUrl(sample.url);
                setValidationError(null);
              }}
              className="px-2.5 py-1 rounded-md bg-[#F0EFEA] hover:bg-[#E5E2DB] text-[#1C2024] font-medium transition-colors"
            >
              {sample.name}
            </button>
          ))}
        </div>

        {/* Submit button */}
        <button
          type="submit"
          disabled={isLoading || !url.trim()}
          className="w-full flex items-center justify-center gap-2 py-2.5 px-4 rounded-lg bg-[#0B6E5F] hover:bg-[#085449] disabled:bg-[#0B6E5F]/50 text-white font-medium text-sm transition-colors shadow-sm cursor-pointer disabled:cursor-not-allowed"
        >
          {isLoading ? (
            <>
              <Loader2 className="w-4 h-4 animate-spin" />
              <span>Cloning & Validating Repository...</span>
            </>
          ) : (
            <>
              <span>Import & Start Indexing</span>
              <ArrowRight className="w-4 h-4" />
            </>
          )}
        </button>
      </form>

      {/* Validation error */}
      {validationError && (
        <div className="flex items-center gap-2 p-3 text-xs text-red-700 bg-red-50 border border-red-200 rounded-lg">
          <AlertCircle className="w-4 h-4 flex-shrink-0" />
          <span>{validationError}</span>
        </div>
      )}

      {/* Security note */}
      <div className="flex items-start gap-2 p-3 bg-[#F9F8F6] border border-[#E5E2DB] rounded-lg text-xs text-[#636A74]">
        <CheckCircle2 className="w-4 h-4 text-[#0B6E5F] flex-shrink-0 mt-0.5" />
        <span>
          DevMind AI performs shallow, single-commit clones (<code className="bg-[#EAE8E2] px-1 rounded text-[#1C2024]">--depth 1</code>) and completely deletes all <code className="bg-[#EAE8E2] px-1 rounded text-[#1C2024]">.git</code> internal history for safety.
        </span>
      </div>
    </div>
  );
};
