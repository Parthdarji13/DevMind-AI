"use client";

import React from "react";
import { CheckCircle2, Loader2, Circle, AlertCircle } from "lucide-react";
import { StageDetail, StageStatus } from "@/lib/types";

interface ProgressCardProps {
  currentStep: number;
  percentage: number;
  stages: StageDetail[];
}

export const ProgressCard: React.FC<ProgressCardProps> = ({
  currentStep,
  percentage,
  stages,
}) => {
  const getStatusBadge = (status: StageStatus) => {
    switch (status) {
      case "done":
        return (
          <span className="text-[11px] font-semibold px-2 py-0.5 rounded-full bg-[#E6F4F1] text-[#0B6E5F] border border-[#BDE3DC]">
            Done
          </span>
        );
      case "in_progress":
        return (
          <span className="text-[11px] font-semibold px-2 py-0.5 rounded-full bg-amber-50 text-amber-800 border border-amber-200 flex items-center gap-1">
            <span className="w-1.5 h-1.5 rounded-full bg-amber-500 animate-pulse" />
            In progress
          </span>
        );
      case "failed":
        return (
          <span className="text-[11px] font-semibold px-2 py-0.5 rounded-full bg-red-50 text-red-700 border border-red-200">
            Failed
          </span>
        );
      default:
        return (
          <span className="text-[11px] font-medium px-2 py-0.5 rounded-full bg-[#F0EFEA] text-[#636A74]">
            Waiting
          </span>
        );
    }
  };

  const getStatusIcon = (status: StageStatus) => {
    switch (status) {
      case "done":
        return <CheckCircle2 className="w-5 h-5 text-[#0B6E5F] flex-shrink-0" />;
      case "in_progress":
        return <Loader2 className="w-5 h-5 text-[#0B6E5F] animate-spin flex-shrink-0" />;
      case "failed":
        return <AlertCircle className="w-5 h-5 text-red-600 flex-shrink-0" />;
      default:
        return <Circle className="w-5 h-5 text-[#D6D2CA] flex-shrink-0" />;
    }
  };

  return (
    <div className="rounded-2xl border border-[#E5E2DB] bg-white p-6 sm:p-7 shadow-sm space-y-6">
      {/* Top progress bar header */}
      <div>
        <div className="flex items-center justify-between mb-2.5">
          <span className="text-xs font-semibold uppercase tracking-wider text-[#636A74]">
            Step {Math.min(5, Math.max(1, currentStep))} of 5
          </span>
          <span className="text-sm font-bold font-mono text-[#1C2024]">
            {percentage}%
          </span>
        </div>

        {/* Progress bar */}
        <div
          role="progressbar"
          aria-valuenow={percentage}
          aria-valuemin={0}
          aria-valuemax={100}
          className="w-full h-2.5 rounded-full bg-[#ECE9E3] overflow-hidden"
        >
          <div
            className="h-full bg-[#0B6E5F] transition-all duration-300 ease-out rounded-full"
            style={{ width: `${Math.min(100, Math.max(0, percentage))}%` }}
          />
        </div>
      </div>

      {/* Ordered list of 5 pipeline stages */}
      <div className="divide-y divide-[#EAE8E2]">
        {stages.map((stage) => {
          const isActive = stage.status === "in_progress";
          const isDone = stage.status === "done";
          const isFailed = stage.status === "failed";

          return (
            <div
              key={stage.step_number}
              className={`py-3.5 first:pt-0 last:pb-0 flex items-start justify-between gap-4 transition-colors ${
                isActive ? "bg-[#FAF9F6] -mx-4 px-4 rounded-xl" : ""
              }`}
            >
              <div className="flex items-start gap-3 min-w-0">
                <div className="mt-0.5">{getStatusIcon(stage.status)}</div>
                <div className="min-w-0">
                  <div className="flex items-center gap-2">
                    <span
                      className={`text-sm font-semibold truncate ${
                        isDone || isActive
                          ? "text-[#1C2024]"
                          : isFailed
                          ? "text-red-700"
                          : "text-[#636A74]"
                      }`}
                    >
                      {stage.name}
                    </span>

                    {/* Live counter if available */}
                    {typeof stage.total_count === "number" && stage.total_count > 0 && (
                      <span className="font-mono text-xs font-semibold text-[#0B6E5F] bg-[#E6F4F1] px-2 py-0.5 rounded-md border border-[#BDE3DC] inline-flex items-center gap-1">
                        <span>
                          {stage.status === "done"
                            ? `${stage.total_count} of ${stage.total_count}`
                            : `${stage.current_count ?? 0} of ${stage.total_count}`}
                        </span>
                        <span className="text-[10px] text-[#0B6E5F]/70">
                          ({stage.status === "done" ? 100 : Math.round(((stage.current_count ?? 0) / stage.total_count) * 100)}%)
                        </span>
                      </span>
                    )}
                  </div>

                  <p className="text-xs text-[#636A74] mt-0.5 leading-relaxed">
                    {stage.detail}
                  </p>
                </div>
              </div>

              <div className="flex-shrink-0">{getStatusBadge(stage.status)}</div>
            </div>
          );
        })}
      </div>
    </div>
  );
};
