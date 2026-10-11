"use client";

import React, { useEffect, useState } from "react";
import { Terminal, Shield, Sparkles, Wifi, WifiOff } from "lucide-react";
import { checkBackendHealth } from "@/lib/api";
import { BackendHealth } from "@/lib/types";

interface HeaderProps {
  currentStep?: 1 | 2 | 3;
}

export const Header: React.FC<HeaderProps> = ({ currentStep = 1 }) => {
  const [health, setHealth] = useState<BackendHealth | null>(null);

  useEffect(() => {
    let mounted = true;
    const fetchHealth = async () => {
      const h = await checkBackendHealth();
      if (mounted) setHealth(h);
    };

    fetchHealth();
    const interval = setInterval(fetchHealth, 15000); // Check every 15s
    return () => {
      mounted = false;
      clearInterval(interval);
    };
  }, []);

  return (
    <header className="border-b border-[#E5E2DB] bg-white/90 backdrop-blur-md sticky top-0 z-40">
      <div className="max-w-6xl mx-auto px-4 sm:px-6 h-16 flex items-center justify-between">
        {/* Brand */}
        <div className="flex items-center gap-3">
          <div className="w-10 h-10 rounded-xl bg-[#0B6E5F] text-white flex items-center justify-center shadow-sm">
            <Terminal className="w-5 h-5" />
          </div>
          <div>
            <div className="flex items-center gap-2">
              <span className="font-semibold text-lg text-[#1C2024] tracking-tight">
                DevMind AI
              </span>
              <span className="text-[11px] font-medium px-2 py-0.5 rounded-full bg-[#E6F4F1] text-[#0B6E5F] border border-[#BDE3DC]">
                RAG Code Assistant
              </span>
            </div>
            <p className="text-xs text-[#636A74] hidden sm:block">
              Evidence-grounded code intelligence with verified line citations
            </p>
          </div>
        </div>

        {/* Workflow Steps Indicator */}
        <div className="hidden md:flex items-center gap-2 text-xs font-medium text-[#636A74]">
          <div
            className={`flex items-center gap-1.5 px-2.5 py-1 rounded-md ${
              currentStep === 1
                ? "bg-[#1C2024] text-white"
                : "bg-[#F0EFEA] text-[#1C2024]"
            }`}
          >
            <span className="w-4 h-4 rounded-full bg-white/20 text-[10px] flex items-center justify-center font-bold">
              1
            </span>
            <span>Upload</span>
          </div>

          <span className="text-[#A09D96]">→</span>

          <div
            className={`flex items-center gap-1.5 px-2.5 py-1 rounded-md ${
              currentStep === 2
                ? "bg-[#1C2024] text-white"
                : "bg-[#F0EFEA] text-[#636A74]"
            }`}
          >
            <span className="w-4 h-4 rounded-full bg-white/20 text-[10px] flex items-center justify-center font-bold">
              2
            </span>
            <span>Indexing</span>
          </div>

          <span className="text-[#A09D96]">→</span>

          <div
            className={`flex items-center gap-1.5 px-2.5 py-1 rounded-md ${
              currentStep === 3
                ? "bg-[#1C2024] text-white"
                : "bg-[#F0EFEA] text-[#636A74]"
            }`}
          >
            <span className="w-4 h-4 rounded-full bg-white/20 text-[10px] flex items-center justify-center font-bold">
              3
            </span>
            <span>Chat Workspace</span>
          </div>
        </div>

        {/* Backend Status Badge */}
        <div className="flex items-center gap-2">
          {health?.status === "ok" ? (
            <div
              className="flex items-center gap-1.5 px-2.5 py-1 rounded-full bg-emerald-50 text-emerald-700 text-xs font-medium border border-emerald-200"
              title={`Backend online on port 8000 (LLM: ${health.llm_provider}, Embeddings: ${health.embedding_provider})`}
            >
              <span className="w-2 h-2 rounded-full bg-emerald-500 animate-pulse"></span>
              <span>Backend Ready</span>
            </div>
          ) : (
            <div
              className="flex items-center gap-1.5 px-2.5 py-1 rounded-full bg-amber-50 text-amber-700 text-xs font-medium border border-amber-200"
              title={health?.message || "Checking backend connection..."}
            >
              <WifiOff className="w-3.5 h-3.5 text-amber-600" />
              <span>Offline (Port 8000)</span>
            </div>
          )}
        </div>
      </div>
    </header>
  );
};
