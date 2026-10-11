"use client";

import React, { useState } from "react";
import { Header } from "@/components/common/Header";
import { UploadScreen } from "@/components/upload/UploadScreen";
import { IngestResponse } from "@/lib/types";
import { CheckCircle2, RotateCcw } from "lucide-react";

export default function Home() {
  const [currentStep, setCurrentStep] = useState<1 | 2 | 3>(1);
  const [activeRepo, setActiveRepo] = useState<IngestResponse | null>(null);

  const handleIngestSuccess = (res: IngestResponse) => {
    setActiveRepo(res);
    // Transition to indexing screen (Step 26)
    setCurrentStep(2);
  };

  const handleReset = () => {
    setActiveRepo(null);
    setCurrentStep(1);
  };

  return (
    <div className="min-h-screen flex flex-col bg-[#F7F6F3]">
      <Header currentStep={currentStep} />

      <main className="flex-1 px-4 sm:px-6 py-8">
        {currentStep === 1 && (
          <UploadScreen onIngestSuccess={handleIngestSuccess} />
        )}

        {currentStep === 2 && activeRepo && (
          <div className="w-full max-w-2xl mx-auto my-12 p-8 bg-white rounded-2xl border border-[#E5E2DB] shadow-sm text-center space-y-4">
            <div className="w-12 h-12 mx-auto rounded-full bg-[#E6F4F1] text-[#0B6E5F] flex items-center justify-center">
              <CheckCircle2 className="w-6 h-6" />
            </div>
            <h2 className="text-xl font-bold text-[#1C2024]">
              Repository Ingested: {activeRepo.repo_name}
            </h2>
            <p className="text-xs text-[#636A74]">
              Repository ID: <code className="font-mono bg-[#F0EFEA] px-1.5 py-0.5 rounded text-[#1C2024]">{activeRepo.repo_id}</code>
            </p>
            <p className="text-sm text-[#636A74] max-w-md mx-auto">
              Ready for real-time indexing pipeline (Stage tracking, AST parsing, chunking, and embedding will be managed in Step 26).
            </p>
            <div className="pt-4 flex justify-center gap-3">
              <button
                type="button"
                onClick={handleReset}
                className="inline-flex items-center gap-1.5 px-4 py-2 text-xs font-semibold rounded-lg border border-[#D6D2CA] text-[#1C2024] hover:bg-[#F9F8F6] transition-colors cursor-pointer"
              >
                <RotateCcw className="w-3.5 h-3.5" />
                <span>Upload Another Repository</span>
              </button>
            </div>
          </div>
        )}
      </main>

      <footer className="border-t border-[#E5E2DB] py-4 bg-white/50 text-center text-xs text-[#636A74]">
        DevMind AI • Evidence-Grounded Hybrid RAG Assistant • Max 100 MB / 3,000 files / 500,000 LOC
      </footer>
    </div>
  );
}
