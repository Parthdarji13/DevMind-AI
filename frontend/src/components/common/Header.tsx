"use client";

import React, { useEffect, useState } from "react";
import { Terminal, WifiOff, FolderGit2, User as UserIcon } from "lucide-react";
import { checkBackendHealth } from "@/lib/api";

import { BackendHealth } from "@/lib/types";
import { useAuth } from "@/lib/auth";

interface HeaderProps {
  currentStep?: 1 | 2 | 3;
  onOpenDrawer?: () => void;
  onOpenAuth?: () => void;
  repoCount?: number;
}

export const Header: React.FC<HeaderProps> = ({
  currentStep = 1,
  onOpenDrawer,
  onOpenAuth,
  repoCount,
}) => {
  const [health, setHealth] = useState<BackendHealth | null>(null);
  const { user, isAuthenticated } = useAuth();


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

        {/* Actions & Status */}
        <div className="flex items-center gap-2.5">
          {/* My Repositories Drawer Trigger */}
          {onOpenDrawer && (
            <button
              onClick={onOpenDrawer}
              className="flex items-center gap-1.5 px-3 py-1.5 rounded-xl border border-[#D0CFC8] bg-white hover:bg-[#FAF9F6] text-[#1C2024] text-xs font-semibold transition-all shadow-sm active:scale-95 group"
            >
              <FolderGit2 className="w-3.5 h-3.5 text-[#0B6E5F]" />
              <span>Repositories</span>
              {typeof repoCount === "number" && repoCount > 0 && (
                <span className="w-4 h-4 rounded-full bg-[#E6F4F1] text-[#0B6E5F] text-[10px] flex items-center justify-center font-bold">
                  {repoCount}
                </span>
              )}
            </button>
          )}

          {/* User Profile / Sign In */}
          {isAuthenticated && user ? (
            <button
              onClick={onOpenDrawer}
              className="flex items-center gap-1.5 px-2.5 py-1.5 rounded-xl border border-[#D0CFC8] bg-white hover:bg-[#FAF9F6] text-xs font-medium text-[#1C2024] transition-all"
              title={`${user.name} (${user.email})`}
            >
              <div className="w-5 h-5 rounded-full bg-[#0B6E5F] text-white text-[10px] font-bold flex items-center justify-center">
                {user.name.charAt(0).toUpperCase()}
              </div>
              <span className="hidden sm:inline max-w-[80px] truncate">{user.name.split(" ")[0]}</span>
            </button>
          ) : (
            onOpenAuth && (
              <button
                onClick={onOpenAuth}
                className="flex items-center gap-1.5 px-3 py-1.5 rounded-xl bg-[#1C2024] hover:bg-[#2C3136] text-white text-xs font-medium transition-all shadow-sm"
              >
                <UserIcon className="w-3.5 h-3.5" />
                <span>Sign In</span>
              </button>
            )
          )}

          {/* Backend Status Badge */}
          {health?.status === "ok" ? (
            <div
              className="hidden sm:flex items-center gap-1.5 px-2.5 py-1 rounded-full bg-emerald-50 text-emerald-700 text-xs font-medium border border-emerald-200"
              title={`Backend online on port 8000 (LLM: ${health.llm_provider}, Embeddings: ${health.embedding_provider})`}
            >
              <span className="w-2 h-2 rounded-full bg-emerald-500 animate-pulse"></span>
              <span>Backend Ready</span>
            </div>
          ) : (
            <div
              className="hidden sm:flex items-center gap-1.5 px-2.5 py-1 rounded-full bg-amber-50 text-amber-700 text-xs font-medium border border-amber-200"
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
