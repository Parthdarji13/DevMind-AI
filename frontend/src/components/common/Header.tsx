"use client";

import React, { useEffect, useState } from "react";
import { Terminal, WifiOff, User as UserIcon, LogOut, History, Home } from "lucide-react";
import { checkBackendHealth } from "@/lib/api";

import { BackendHealth } from "@/lib/types";
import { useAuth } from "@/lib/auth";

interface HeaderProps {
  currentStep?: 1 | 2 | 3;
  onOpenAuth?: () => void;
  onGoHome?: () => void;
  onOpenChatHistory?: () => void;
  chatCount?: number;
}

export const Header: React.FC<HeaderProps> = ({
  currentStep = 1,
  onOpenAuth,
  onGoHome,
  onOpenChatHistory,
  chatCount,
}) => {
  const [health, setHealth] = useState<BackendHealth | null>(null);
  const { user, isAuthenticated, logout } = useAuth();

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
    <header className="border-b border-[#E5E2DB] bg-white/95 backdrop-blur-md sticky top-0 z-40">
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 h-16 flex items-center justify-between gap-4">
        {/* Brand */}
        <div
          onClick={onGoHome}
          className={`flex items-center gap-3 flex-shrink-0 ${onGoHome ? "cursor-pointer group" : ""}`}
          title="Return to Home Screen"
        >
          <div className="w-10 h-10 rounded-xl bg-[#0B6E5F] text-white flex items-center justify-center shadow-xs group-hover:scale-105 transition-transform">
            <Terminal className="w-5 h-5" />
          </div>
          <div>
            <div className="flex items-center gap-2">
              <span className="font-bold text-lg text-[#1C2024] tracking-tight group-hover:text-[#0B6E5F] transition-colors whitespace-nowrap">
                DevMind AI
              </span>
              <span className="text-[10px] font-semibold px-2 py-0.5 rounded-full bg-[#E6F4F1] text-[#0B6E5F] border border-[#BDE3DC] whitespace-nowrap">
                RAG Assistant
              </span>
            </div>
            <p className="text-[11px] text-[#636A74] hidden md:block leading-none mt-0.5">
              Evidence-grounded code intelligence
            </p>
          </div>
        </div>

        {/* Workflow Segmented Stepper */}
        <div className="hidden md:flex items-center gap-1 p-1 rounded-xl bg-[#F4F2EC] border border-[#E8E5DD] text-xs font-medium text-[#636A74]">
          <button
            type="button"
            onClick={onGoHome}
            className={`flex items-center gap-1.5 px-3 py-1 rounded-lg transition-all cursor-pointer ${
              currentStep === 1
                ? "bg-white text-[#1C2024] font-semibold shadow-xs"
                : "text-[#636A74] hover:text-[#1C2024]"
            }`}
            title="Go to Home"
          >
            <Home className="w-3.5 h-3.5 text-[#0B6E5F]" />
            <span className="whitespace-nowrap">Home</span>
          </button>

          <span className="text-[#C5C1B8] text-xs font-mono">/</span>

          <div
            className={`flex items-center gap-1.5 px-3 py-1 rounded-lg transition-all ${
              currentStep === 2
                ? "bg-white text-[#1C2024] font-semibold shadow-xs"
                : "text-[#636A74] hover:text-[#1C2024]"
            }`}
          >
            <span
              className={`w-4 h-4 rounded-full text-[10px] flex items-center justify-center font-bold ${
                currentStep === 2 ? "bg-[#0B6E5F] text-white" : "bg-[#E0DDD5] text-[#636A74]"
              }`}
            >
              2
            </span>
            <span className="whitespace-nowrap">Indexing</span>
          </div>

          <span className="text-[#C5C1B8] text-xs font-mono">/</span>

          <div
            className={`flex items-center gap-1.5 px-3 py-1 rounded-lg transition-all ${
              currentStep === 3
                ? "bg-white text-[#1C2024] font-semibold shadow-xs"
                : "text-[#636A74] hover:text-[#1C2024]"
            }`}
          >
            <span
              className={`w-4 h-4 rounded-full text-[10px] flex items-center justify-center font-bold ${
                currentStep === 3 ? "bg-[#0B6E5F] text-white" : "bg-[#E0DDD5] text-[#636A74]"
              }`}
            >
              3
            </span>
            <span className="whitespace-nowrap">Workspace</span>
          </div>
        </div>

        {/* Actions & Status */}
        <div className="flex items-center gap-2.5 flex-shrink-0">
          {/* Chat History Button (placed in navbar next to account) */}
          {onOpenChatHistory && (
            <button
              type="button"
              onClick={onOpenChatHistory}
              className="inline-flex items-center gap-2 h-9 px-3.5 rounded-xl border border-[#D5D1C8] bg-white hover:bg-[#FAF9F6] hover:border-[#0B6E5F]/50 text-[#1C2024] text-xs font-semibold whitespace-nowrap shadow-xs active:scale-95 transition-all cursor-pointer group"
              title="Open Chat History"
            >
              <History className="w-4 h-4 text-[#0B6E5F] group-hover:rotate-[-20deg] transition-transform" />
              <span className="font-semibold text-xs tracking-tight">Chat History</span>
              {typeof chatCount === "number" && chatCount > 0 && (
                <span className="px-1.5 py-0.2 rounded-full bg-[#E6F4F1] text-[#0B6E5F] text-[10px] font-bold border border-[#BDE3DC]">
                  {chatCount}
                </span>
              )}
            </button>
          )}

          {/* Unified User Profile Pill with Integrated Logout */}
          {isAuthenticated && user ? (
            <div className="flex items-center gap-2 h-9 pl-2 pr-2.5 rounded-xl border border-[#D5D1C8] bg-white shadow-xs">
              <div className="w-5 h-5 rounded-full bg-[#0B6E5F] text-white text-[10px] font-bold flex items-center justify-center shadow-xs flex-shrink-0">
                {user.name.charAt(0).toUpperCase()}
              </div>
              <span className="text-xs font-semibold text-[#1C2024] max-w-[85px] truncate">
                {user.name.split(" ")[0]}
              </span>
              <div className="w-px h-3.5 bg-[#E5E2DB]" />
              <button
                type="button"
                onClick={logout}
                className="text-[#8C939D] hover:text-red-600 transition-colors p-0.5 rounded hover:bg-red-50 cursor-pointer flex items-center"
                title="Log out"
              >
                <LogOut className="w-3.5 h-3.5" />
              </button>
            </div>
          ) : (
            onOpenAuth && (
              <button
                type="button"
                onClick={onOpenAuth}
                className="inline-flex items-center gap-1.5 h-9 px-3.5 rounded-xl bg-[#1C2024] hover:bg-[#2C3136] text-white text-xs font-semibold whitespace-nowrap shadow-xs active:scale-95 transition-all cursor-pointer"
              >
                <UserIcon className="w-3.5 h-3.5" />
                <span>Sign In</span>
              </button>
            )
          )}

          {/* Compact Backend Ready Pulse Indicator */}
          {health?.status === "ok" ? (
            <div
              className="hidden lg:flex items-center gap-1.5 h-9 px-2.5 rounded-xl bg-emerald-50 text-emerald-700 text-xs font-medium border border-emerald-200 whitespace-nowrap"
              title={`Backend online on port 8000 (LLM: ${health.llm_provider})`}
            >
              <span className="w-2 h-2 rounded-full bg-emerald-500 animate-pulse"></span>
              <span className="text-[11px] font-semibold">Ready</span>
            </div>
          ) : (
            <div
              className="hidden lg:flex items-center gap-1.5 h-9 px-2.5 rounded-xl bg-amber-50 text-amber-700 text-xs font-medium border border-amber-200 whitespace-nowrap"
              title={health?.message || "Checking backend connection..."}
            >
              <WifiOff className="w-3.5 h-3.5 text-amber-600" />
              <span className="text-[11px] font-semibold">Offline</span>
            </div>
          )}
        </div>
      </div>
    </header>
  );
};
