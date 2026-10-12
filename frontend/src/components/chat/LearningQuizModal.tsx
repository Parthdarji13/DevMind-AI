"use client";

import React, { useState, useEffect } from "react";
import {
  GraduationCap,
  X,
  Loader2,
  AlertCircle,
  CheckCircle2,
  XCircle,
  HelpCircle,
  ArrowRight,
  RotateCcw,
  FileCode2,
  Sparkles,
  Trophy,
} from "lucide-react";
import { QuizResponse, QuizQuestion } from "@/lib/types";
import { getLearningQuiz } from "@/lib/api";

interface LearningQuizModalProps {
  repoId: string;
  repoName: string;
  isOpen: boolean;
  onClose: () => void;
  onSelectQuestion?: (q: string) => void;
}

export const LearningQuizModal: React.FC<LearningQuizModalProps> = ({
  repoId,
  repoName,
  isOpen,
  onClose,
  onSelectQuestion,
}) => {
  const [quizData, setQuizData] = useState<QuizResponse | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [currentIndex, setCurrentIndex] = useState(0);
  const [selectedAnswers, setSelectedAnswers] = useState<Record<number, number>>({});
  const [revealedHints, setRevealedHints] = useState<Record<number, boolean>>({});
  const [quizFinished, setQuizFinished] = useState(false);

  const fetchQuiz = () => {
    setLoading(true);
    setError(null);
    setCurrentIndex(0);
    setSelectedAnswers({});
    setRevealedHints({});
    setQuizFinished(false);

    getLearningQuiz(repoId)
      .then((res) => setQuizData(res))
      .catch((err) => setError(err?.message || "Failed to generate codebase quiz."))
      .finally(() => setLoading(false));
  };

  useEffect(() => {
    if (isOpen && !quizData) {
      fetchQuiz();
    }
  }, [isOpen, repoId, quizData]);

  if (!isOpen) return null;

  const questions = quizData?.questions || [];
  const currentQ = questions[currentIndex];
  const hasAnsweredCurrent = currentQ ? selectedAnswers[currentIndex] !== undefined : false;
  const selectedCurrentOption = currentQ ? selectedAnswers[currentIndex] : undefined;

  const handleSelectOption = (optionIndex: number) => {
    if (hasAnsweredCurrent) return;
    setSelectedAnswers((prev) => ({
      ...prev,
      [currentIndex]: optionIndex,
    }));
  };

  const handleNext = () => {
    if (currentIndex < questions.length - 1) {
      setCurrentIndex((prev) => prev + 1);
    } else {
      setQuizFinished(true);
    }
  };

  const calculateScore = () => {
    let score = 0;
    questions.forEach((q, idx) => {
      if (selectedAnswers[idx] === q.correct_index) {
        score += 1;
      }
    });
    return score;
  };

  const toggleHint = (idx: number) => {
    setRevealedHints((prev) => ({
      ...prev,
      [idx]: !prev[idx],
    }));
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 backdrop-blur-xs p-4 overflow-y-auto">
      <div className="bg-white rounded-2xl max-w-2xl w-full max-h-[90vh] shadow-2xl border border-[#E5E2DB] flex flex-col overflow-hidden animate-in fade-in zoom-in-95 duration-200">
        {/* Header */}
        <div className="px-6 py-4 border-b border-[#EAE8E2] bg-[#FAF9F6] flex items-center justify-between">
          <div className="flex items-center gap-2.5">
            <div className="w-8 h-8 rounded-xl bg-[#E6F4F1] text-[#0B6E5F] flex items-center justify-center shadow-xs">
              <GraduationCap className="w-4 h-4" />
            </div>
            <div>
              <h2 className="text-base font-bold text-[#1C2024] leading-tight">
                Learning Mode & Code Quiz
              </h2>
              <p className="text-xs text-[#636A74]">
                Interactive code comprehension questions for {repoName}
              </p>
            </div>
          </div>

          <button
            type="button"
            onClick={onClose}
            className="p-1 rounded-lg text-[#636A74] hover:text-[#1C2024] hover:bg-black/5 transition-colors cursor-pointer"
          >
            <X className="w-5 h-5" />
          </button>
        </div>

        {/* Modal Body */}
        <div className="flex-1 overflow-y-auto p-6 space-y-6">
          {loading && (
            <div className="py-20 flex flex-col items-center justify-center space-y-3 text-[#0B6E5F]">
              <Loader2 className="w-8 h-8 animate-spin" />
              <p className="text-sm font-semibold text-[#1C2024]">Synthesizing codebase quiz...</p>
              <p className="text-xs text-[#636A74]">Analyzing classes, functions, and core routines</p>
            </div>
          )}

          {error && (
            <div className="flex items-center gap-2 p-4 rounded-xl bg-red-50 border border-red-200 text-xs text-red-800">
              <AlertCircle className="w-4 h-4 text-red-600 flex-shrink-0" />
              <span>{error}</span>
            </div>
          )}

          {quizData && !quizFinished && currentQ && (
            <div className="space-y-6">
              {/* Stepper Progress */}
              <div className="space-y-1.5">
                <div className="flex items-center justify-between text-xs font-semibold text-[#636A74]">
                  <span>
                    Question {currentIndex + 1} of {questions.length}
                  </span>
                  <span>
                    {Math.round(((currentIndex + 1) / questions.length) * 100)}% Completed
                  </span>
                </div>
                <div className="w-full h-1.5 rounded-full bg-[#EAE8E2] overflow-hidden">
                  <div
                    className="h-full bg-[#0B6E5F] transition-all duration-300"
                    style={{ width: `${((currentIndex + 1) / questions.length) * 100}%` }}
                  />
                </div>
              </div>

              {/* Question Card */}
              <div className="space-y-3">
                <div className="flex items-start justify-between gap-3">
                  <h3 className="text-sm font-bold text-[#1C2024] leading-snug">
                    {currentQ.question}
                  </h3>
                </div>

                <div className="flex items-center gap-1.5 text-[11px] font-mono text-[#636A74] bg-[#FAF9F6] px-2.5 py-1 rounded-lg border border-[#EAE8E2] w-fit">
                  <FileCode2 className="w-3.5 h-3.5 text-[#0B6E5F]" />
                  <span>
                    {currentQ.file_path}:{currentQ.start_line}-{currentQ.end_line}
                  </span>
                </div>
              </div>

              {/* Options */}
              <div className="space-y-2.5">
                {currentQ.options.map((opt, oIdx) => {
                  const isSelected = selectedCurrentOption === oIdx;
                  const isCorrect = currentQ.correct_index === oIdx;

                  let cardStyle = "bg-[#FAF9F6] border-[#EAE8E2] text-[#1C2024] hover:bg-white hover:border-[#BDE3DC]";
                  if (hasAnsweredCurrent) {
                    if (isCorrect) {
                      cardStyle = "bg-emerald-50 border-emerald-500 text-emerald-900 ring-1 ring-emerald-500 font-medium";
                    } else if (isSelected && !isCorrect) {
                      cardStyle = "bg-red-50 border-red-500 text-red-900 ring-1 ring-red-500 font-medium";
                    } else {
                      cardStyle = "bg-gray-50 border-gray-200 text-gray-400 opacity-60";
                    }
                  }

                  const optionLabels = ["A", "B", "C", "D"];

                  return (
                    <button
                      key={oIdx}
                      type="button"
                      disabled={hasAnsweredCurrent}
                      onClick={() => handleSelectOption(oIdx)}
                      className={`w-full text-left p-3.5 rounded-xl border transition-all flex items-center justify-between gap-3 text-xs cursor-pointer shadow-xs ${cardStyle}`}
                    >
                      <div className="flex items-center gap-2.5">
                        <span className="w-6 h-6 rounded-lg bg-white border border-[#E5E2DB] text-[#636A74] flex items-center justify-center font-bold text-[11px] flex-shrink-0">
                          {optionLabels[oIdx] || oIdx + 1}
                        </span>
                        <span className="leading-relaxed">{opt}</span>
                      </div>

                      {hasAnsweredCurrent && (
                        <div>
                          {isCorrect && <CheckCircle2 className="w-4 h-4 text-emerald-600 flex-shrink-0" />}
                          {isSelected && !isCorrect && <XCircle className="w-4 h-4 text-red-600 flex-shrink-0" />}
                        </div>
                      )}
                    </button>
                  );
                })}
              </div>

              {/* Hint Accordion */}
              {currentQ.hint && (
                <div className="pt-1">
                  <button
                    type="button"
                    onClick={() => toggleHint(currentIndex)}
                    className="inline-flex items-center gap-1.5 text-xs text-[#0B6E5F] hover:text-[#085449] font-medium transition-colors cursor-pointer"
                  >
                    <HelpCircle className="w-3.5 h-3.5" />
                    <span>{revealedHints[currentIndex] ? "Hide Hint" : "Need a hint?"}</span>
                  </button>

                  {revealedHints[currentIndex] && (
                    <div className="mt-2 p-3 rounded-xl bg-amber-50/70 border border-amber-200 text-xs text-amber-900 leading-relaxed animate-in fade-in duration-150">
                      💡 {currentQ.hint}
                    </div>
                  )}
                </div>
              )}

              {/* Explanation (Shown after answering) */}
              {hasAnsweredCurrent && (
                <div className="p-4 rounded-xl bg-[#E6F4F1] border border-[#BDE3DC] space-y-1.5 animate-in fade-in duration-200">
                  <div className="flex items-center gap-1.5 text-xs font-bold text-[#0B6E5F]">
                    <Sparkles className="w-3.5 h-3.5" />
                    <span>Code Explanation</span>
                  </div>
                  <p className="text-xs text-[#1C2024] leading-relaxed">
                    {currentQ.explanation}
                  </p>
                </div>
              )}

              {/* Next Button */}
              {hasAnsweredCurrent && (
                <div className="flex justify-end pt-2">
                  <button
                    type="button"
                    onClick={handleNext}
                    className="inline-flex items-center gap-1.5 px-4 py-2.5 rounded-xl text-xs font-semibold bg-[#0B6E5F] text-white hover:bg-[#085449] transition-colors cursor-pointer shadow-xs"
                  >
                    <span>{currentIndex === questions.length - 1 ? "Finish Quiz" : "Next Question"}</span>
                    <ArrowRight className="w-3.5 h-3.5" />
                  </button>
                </div>
              )}
            </div>
          )}

          {/* Quiz Completion Screen */}
          {quizFinished && (
            <div className="py-10 text-center space-y-6 animate-in fade-in zoom-in-95 duration-200">
              <div className="w-14 h-14 rounded-2xl bg-amber-50 border border-amber-200 text-amber-600 flex items-center justify-center mx-auto shadow-xs">
                <Trophy className="w-7 h-7" />
              </div>

              <div className="space-y-2">
                <h3 className="text-lg font-bold text-[#1C2024]">
                  Quiz Completed!
                </h3>
                <p className="text-xs text-[#636A74]">
                  You scored <span className="font-bold text-[#0B6E5F]">{calculateScore()}</span> out of <span className="font-bold text-[#1C2024]">{questions.length}</span> questions correctly.
                </p>
              </div>

              <div className="flex items-center justify-center gap-3 pt-2">
                <button
                  type="button"
                  onClick={fetchQuiz}
                  className="inline-flex items-center gap-1.5 px-4 py-2.5 rounded-xl text-xs font-medium text-[#1C2024] bg-white border border-[#E5E2DB] hover:bg-[#FAF9F6] transition-colors cursor-pointer"
                >
                  <RotateCcw className="w-3.5 h-3.5" />
                  <span>Retry Quiz</span>
                </button>

                {onSelectQuestion && (
                  <button
                    type="button"
                    onClick={() => {
                      onSelectQuestion(`Give me a detailed tutorial explaining the main components in this codebase.`);
                      onClose();
                    }}
                    className="inline-flex items-center gap-1.5 px-4 py-2.5 rounded-xl text-xs font-semibold text-white bg-[#0B6E5F] hover:bg-[#085449] transition-colors cursor-pointer shadow-xs"
                  >
                    <span>Ask For Detailed Tutorial</span>
                    <ArrowRight className="w-3.5 h-3.5" />
                  </button>
                )}
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  );
};
