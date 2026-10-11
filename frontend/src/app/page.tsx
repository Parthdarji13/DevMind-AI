"use client";

import React, { useState } from "react";
import { Header } from "@/components/common/Header";
import { UploadScreen } from "@/components/upload/UploadScreen";
import { IndexingScreen } from "@/components/indexing/IndexingScreen";
import { ChatWorkspace } from "@/components/chat/ChatWorkspace";
import { IngestResponse } from "@/lib/types";

export default function Home() {
  const [currentStep, setCurrentStep] = useState<1 | 2 | 3>(1);
  const [activeRepo, setActiveRepo] = useState<IngestResponse | null>(null);

  const handleIngestSuccess = (res: IngestResponse) => {
    setActiveRepo(res);
    setCurrentStep(2);
  };

  const handleReset = () => {
    setActiveRepo(null);
    setCurrentStep(1);
  };

  return (
    <div className="min-h-screen flex flex-col bg-[#F7F6F3]">
      <Header currentStep={currentStep} />

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
          />
        )}
      </main>

      <footer className="border-t border-[#E5E2DB] py-4 bg-white/50 text-center text-xs text-[#636A74]">
        DevMind AI • Evidence-Grounded Hybrid RAG Assistant • Max 100 MB / 3,000 files / 500,000 LOC
      </footer>
    </div>
  );
}
