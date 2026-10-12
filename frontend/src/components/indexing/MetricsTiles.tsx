"use client";

import React from "react";
import { Files, FileCheck, FileX, AlertTriangle } from "lucide-react";
import { IngestionMetrics } from "@/lib/types";

interface MetricsTilesProps {
  metrics: IngestionMetrics;
}

export const MetricsTiles: React.FC<MetricsTilesProps> = ({ metrics }) => {
  const tiles = [
    {
      label: "Files Discovered",
      value: metrics.discovered_files,
      icon: Files,
      color: "text-[#1C2024]",
      bg: "bg-[#FAF9F6]",
      subtext: "Total files in archive/clone",
    },
    {
      label: "Indexed So Far",
      value: metrics.indexed_files,
      icon: FileCheck,
      color: "text-[#0B6E5F]",
      bg: "bg-[#E6F4F1]/60",
      subtext: `${metrics.total_lines > 0 ? metrics.total_lines.toLocaleString() : "0"} lines parsed`,
      highlight: true,
    },
    {
      label: "Non-Code Excluded",
      value: metrics.skipped_files,
      icon: FileX,
      color: "text-[#636A74]",
      bg: "bg-[#FAF9F6]",
      subtext: "Packages, media & temp caches",
    },
    {
      label: "Failed to Parse",
      value: metrics.failed_files,
      icon: AlertTriangle,
      color: metrics.failed_files > 0 ? "text-red-600" : "text-[#636A74]",
      bg: metrics.failed_files > 0 ? "bg-red-50" : "bg-[#FAF9F6]",
      subtext: metrics.failed_files > 0 ? "Encoding or syntax errors" : "Zero errors encountered",
    },
  ];

  return (
    <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
      {tiles.map((tile, idx) => {
        const Icon = tile.icon;
        return (
          <div
            key={idx}
            className={`p-4 sm:p-5 rounded-2xl border transition-all ${
              tile.highlight
                ? "border-[#0B6E5F]/30 bg-[#E6F4F1]/40 shadow-xs"
                : "border-[#E5E2DB] bg-white shadow-xs"
            }`}
          >
            <div className="flex items-center justify-between mb-3">
              <span className="text-xs font-semibold uppercase tracking-wider text-[#636A74]">
                {tile.label}
              </span>
              <div className={`p-1.5 rounded-lg ${tile.bg}`}>
                <Icon className={`w-4 h-4 ${tile.color}`} />
              </div>
            </div>

            <div className={`text-2xl sm:text-3xl font-bold font-mono ${tile.color} tracking-tight`}>
              {tile.value.toLocaleString()}
            </div>

            <p className="text-[11px] text-[#636A74] mt-1 truncate">
              {tile.subtext}
            </p>
          </div>
        );
      })}
    </div>
  );
};
