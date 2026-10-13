"use client";

import React, { useEffect, useState, useRef, useCallback } from "react";
import {
  ArrowRight,
  RotateCcw,
  AlertCircle,
  CheckCircle2,
  Loader2,
  FolderGit2,
} from "lucide-react";
import { IngestResponse, IngestionProgress } from "@/lib/types";
import { getIngestionProgress, triggerIndexing, ApiError } from "@/lib/api";
import { ProgressCard } from "./ProgressCard";
import { MetricsTiles } from "./MetricsTiles";
import { SkippedBreakdown } from "./SkippedBreakdown";

interface IndexingScreenProps {
  repo: IngestResponse;
  onOpenChat: () => void;
  onNewRepo: () => void;
}

export const IndexingScreen: React.FC<IndexingScreenProps> = ({
  repo,
  onOpenChat,
  onNewRepo,
}) => {
  const [progress, setProgress] = useState<IngestionProgress | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [isRetrying, setIsRetrying] = useState(false);
  const pollingRef = useRef<NodeJS.Timeout | null>(null);

  const fetchProgress = useCallback(async () => {
    try {
      const data = await getIngestionProgress(repo.repo_id);
      setProgress(data);
      if (data.overall_status === "failed") {
        setError(data.error_message || "Indexing pipeline failed.");
      } else {
        setError(null);
      }
      return data;
    } catch (err: unknown) {
      const msg = err instanceof ApiError ? err.message : "Failed to fetch indexing progress";
      setError(msg);
      return null;
    }
  }, [repo.repo_id]);

  const startPolling = useCallback(() => {
    if (pollingRef.current) {
      clearTimeout(pollingRef.current);
    }

    let consecutiveErrors = 0;

    const poll = async () => {
      const current = await fetchProgress();

      if (!current) {
        consecutiveErrors += 1;
        if (consecutiveErrors >= 6) {
          return;
        }
      } else {
        consecutiveErrors = 0;
      }

      // Stop polling once finished or failed
      if (current?.overall_status === "ready" || current?.overall_status === "failed") {
        return;
      }

      pollingRef.current = setTimeout(poll, 1200);
    };

    poll();
  }, [fetchProgress]);

  useEffect(() => {
    startPolling();

    return () => {
      if (pollingRef.current) {
        clearTimeout(pollingRef.current);
      }
    };
  }, [startPolling]);

  const handleRetry = async () => {
    setIsRetrying(true);
    setError(null);
    try {
      await triggerIndexing(repo.repo_id);
      setIsRetrying(false);
      startPolling();
    } catch (err: unknown) {
      setIsRetrying(false);
      const msg = err instanceof ApiError ? err.message : "Failed to trigger retry.";
      setError(msg);
    }
  };

  const isReady = progress?.overall_status === "ready";
  const isFailed = progress?.overall_status === "failed" || Boolean(error);

  return (
    <div className="w-full max-w-5xl mx-auto space-y-6 py-4">
      {/* Top Header Card */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 p-5 sm:p-6 rounded-2xl border border-[#E5E2DB] bg-white shadow-xs">
        <div className="space-y-1">
          <div className="flex items-center gap-2">
            <span className="text-xs font-semibold uppercase tracking-wider text-[#636A74]">
              Step 2: Processing & Indexing
            </span>
            {isReady ? (
              <span className="inline-flex items-center gap-1 px-2.5 py-0.5 rounded-full text-xs font-semibold bg-emerald-50 text-emerald-700 border border-emerald-200">
                <CheckCircle2 className="w-3.5 h-3.5" />
                <span>Ready</span>
              </span>
            ) : isFailed ? (
              <span className="inline-flex items-center gap-1 px-2.5 py-0.5 rounded-full text-xs font-semibold bg-red-50 text-red-700 border border-red-200">
                <AlertCircle className="w-3.5 h-3.5" />
                <span>Failed</span>
              </span>
            ) : (
              <span className="inline-flex items-center gap-1.5 px-2.5 py-0.5 rounded-full text-xs font-semibold bg-[#E6F4F1] text-[#0B6E5F] border border-[#BDE3DC]">
                <span className="w-2 h-2 rounded-full bg-[#0B6E5F] animate-pulse" />
                <span>Processing</span>
              </span>
            )}
          </div>

          <h1 className="text-2xl font-bold tracking-tight text-[#1C2024] flex items-center gap-2">
            <span>Indexing Codebase</span>
            <span className="font-mono text-sm font-semibold text-[#636A74] bg-[#F0EFEA] px-2 py-0.5 rounded-lg border border-[#E5E2DB] truncate max-w-xs">
              {repo.repo_name}
            </span>
          </h1>

          <p className="text-xs text-[#636A74]">
            Repository ID: <code className="font-mono text-[#1C2024]">{repo.repo_id}</code>
          </p>
        </div>

        {/* Action Button: New Repository */}
        <button
          type="button"
          onClick={onNewRepo}
          className="inline-flex items-center gap-1.5 px-4 py-2 text-xs font-semibold rounded-lg border border-[#D6D2CA] text-[#1C2024] hover:bg-[#F9F8F6] transition-colors cursor-pointer self-start sm:self-auto"
        >
          <FolderGit2 className="w-4 h-4 text-[#636A74]" />
          <span>New Repository</span>
        </button>
      </div>

      {/* Failed Alert Box */}
      {isFailed && (
        <div
          role="alert"
          className="p-5 rounded-2xl bg-red-50 border border-red-200 text-red-900 space-y-3"
        >
          <div className="flex items-start gap-3">
            <AlertCircle className="w-5 h-5 text-red-600 flex-shrink-0 mt-0.5" />
            <div className="space-y-1">
              <h3 className="text-sm font-bold">Indexing encountered an issue</h3>
              <p className="text-xs text-red-800 leading-relaxed">
                {progress?.error_message || error || "Failed to parse or index repository source files."}
              </p>
            </div>
          </div>

          <div className="flex items-center gap-3 pt-2">
            <button
              type="button"
              disabled={isRetrying}
              onClick={handleRetry}
              className="inline-flex items-center gap-1.5 px-4 py-2 text-xs font-semibold rounded-lg bg-red-700 hover:bg-red-800 text-white transition-colors cursor-pointer disabled:opacity-50"
            >
              {isRetrying ? (
                <>
                  <Loader2 className="w-3.5 h-3.5 animate-spin" />
                  <span>Retrying...</span>
                </>
              ) : (
                <>
                  <RotateCcw className="w-3.5 h-3.5" />
                  <span>Try Again</span>
                </>
              )}
            </button>

            <button
              type="button"
              onClick={onNewRepo}
              className="px-4 py-2 text-xs font-semibold rounded-lg border border-red-300 text-red-800 hover:bg-red-100/70 transition-colors cursor-pointer"
            >
              Back to Upload
            </button>
          </div>
        </div>
      )}

      {/* Main 5-Stage Progress Card */}
      {progress && (
        <ProgressCard
          currentStep={progress.current_step}
          percentage={progress.percentage}
          stages={progress.stages}
        />
      )}

      {/* 4 Counter Metrics */}
      {progress && <MetricsTiles metrics={progress.metrics} />}

      {/* Skipped and Languages Breakdown */}
      {progress && (
        <SkippedBreakdown
          skippedBreakdown={progress.skipped_breakdown}
          languages={progress.languages}
        />
      )}

      {/* Ready Action Bar */}
      {isReady && (
        <div className="p-6 rounded-2xl bg-white border border-[#E5E2DB] shadow-sm flex flex-col sm:flex-row items-center justify-between gap-4">
          <div className="space-y-0.5 text-center sm:text-left">
            <h4 className="text-sm font-bold text-[#1C2024]">
              Indexing complete and verified!
            </h4>
            <p className="text-xs text-[#636A74]">
              BM25 keyword indices and dense semantic vectors are ready for cited questions.
            </p>
          </div>

          <button
            type="button"
            onClick={onOpenChat}
            className="w-full sm:w-auto inline-flex items-center justify-center gap-2 px-6 py-3 rounded-xl bg-[#0B6E5F] hover:bg-[#085449] text-white font-semibold text-sm transition-colors shadow-sm cursor-pointer"
          >
            <span>Open Chat Workspace</span>
            <ArrowRight className="w-4 h-4" />
          </button>
        </div>
      )}
    </div>
  );
};
