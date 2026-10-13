"use client";

import React, { useState, useEffect } from "react";
import { Header } from "@/components/common/Header";
import { UploadScreen } from "@/components/upload/UploadScreen";
import { IndexingScreen } from "@/components/indexing/IndexingScreen";
import { ChatWorkspace } from "@/components/chat/ChatWorkspace";
import { ChatHistoryDrawer } from "@/components/chat/ChatHistoryDrawer";
import { AuthModal } from "@/components/auth/AuthModal";
import { IngestResponse } from "@/lib/types";
import { getAllHomeChatSessions } from "@/lib/chatStorage";

export default function Home() {
  const [currentStep, setCurrentStep] = useState<1 | 2 | 3>(1);
  const [activeRepo, setActiveRepo] = useState<IngestResponse | null>(null);
  const [activeSessionId, setActiveSessionId] = useState<string | null>(null);
  const [isAuthModalOpen, setIsAuthModalOpen] = useState(false);
  const [isChatHistoryOpen, setIsChatHistoryOpen] = useState(false);
  const [chatCount, setChatCount] = useState<number>(0);

  // Keep chat count updated for navbar badge
  useEffect(() => {
    try {
      const list = getAllHomeChatSessions();
      setChatCount(list.length);
    } catch {
      setChatCount(0);
    }
  }, [isChatHistoryOpen, currentStep]);

  const handleIngestSuccess = (res: IngestResponse) => {
    setActiveRepo(res);
    setActiveSessionId(null);
    setCurrentStep(2);
  };

  const handleReset = () => {
    setActiveRepo(null);
    setActiveSessionId(null);
    setCurrentStep(1);
  };

  const handleSelectChatFromHistory = (repo: IngestResponse, sessionId?: string) => {
    setActiveRepo(repo);
    setActiveSessionId(sessionId || null);
    setIsChatHistoryOpen(false);
    setCurrentStep(3); // Direct jump to Chat Workspace with this session
  };

  return (
    <div className="min-h-screen flex flex-col bg-[#F7F6F3]">
      <Header
        currentStep={currentStep}
        onOpenAuth={() => setIsAuthModalOpen(true)}
        onGoHome={handleReset}
        onOpenChatHistory={() => setIsChatHistoryOpen(true)}
        chatCount={chatCount}
      />

      <main className="flex-1 px-4 sm:px-6 py-6 sm:py-8">
        {currentStep === 1 && (
          <UploadScreen onIngestSuccess={handleIngestSuccess} />
        )}

        {currentStep === 2 && activeRepo && (
          <IndexingScreen
            repo={activeRepo}
            onOpenChat={() => setCurrentStep(3)}
            onNewRepo={handleReset}
          />
        )}

        {currentStep === 3 && activeRepo && (
          <ChatWorkspace
            repo={activeRepo}
            onNewRepo={handleReset}
            initialSessionId={activeSessionId}
          />
        )}
      </main>

      {/* Slide-over Chat History Drawer triggered from Navbar */}
      <ChatHistoryDrawer
        isOpen={isChatHistoryOpen}
        onClose={() => setIsChatHistoryOpen(false)}
        onSelectChat={handleSelectChatFromHistory}
        onOpenAuth={() => setIsAuthModalOpen(true)}
        onGoHome={handleReset}
      />

      {/* Authentication Modal */}
      <AuthModal
        isOpen={isAuthModalOpen}
        onClose={() => setIsAuthModalOpen(false)}
      />

      <footer className="border-t border-[#E5E2DB] py-4 bg-white/50 text-center text-xs text-[#636A74]">
        DevMind AI • Evidence-Grounded Hybrid RAG Assistant • Max 100 MB / 3,000 files / 500,000 LOC
      </footer>
    </div>
  );
}
