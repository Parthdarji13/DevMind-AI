"use client";

import React, { useState } from "react";
import {
  Terminal,
  User,
  AlertTriangle,
  FileCode2,
  HelpCircle,
  ChevronDown,
  ChevronUp,
  ThumbsUp,
  ThumbsDown,
  Copy,
  Check,
  Loader2,
  Flag,
  X,
  Send,
  Volume2,
  VolumeX,
} from "lucide-react";
import { Citation } from "@/lib/types";
import { submitChatFeedback } from "@/lib/api";
import { SafeMarkdown } from "./SafeMarkdown";
import { CitationChip } from "./CitationChip";
import { SourceCard } from "./SourceCard";

export interface ChatMessageDisplay {
  id: string;
  role: "user" | "assistant";
  content: string;
  citations?: Citation[];
  abstained?: boolean;
  inference_detected?: boolean;
  timestamp?: string;
  isStreaming?: boolean;
}

interface MessageItemProps {
  message: ChatMessageDisplay;
  repoId?: string;
  sessionId?: string | null;
  onOpenDrawer?: (citations: Citation[], initialIndex?: number) => void;
}

export const MessageItem: React.FC<MessageItemProps> = ({
  message,
  repoId,
  sessionId,
  onOpenDrawer,
}) => {
  const isUser = message.role === "user";
  const [showInlineSources, setShowInlineSources] = useState(false);
  const [selectedCitationIndex, setSelectedCitationIndex] = useState<number | null>(null);

  // Feedback state (Feature 5)
  const [feedbackRating, setFeedbackRating] = useState<"up" | "down" | null>(null);
  const [showFeedbackModal, setShowFeedbackModal] = useState(false);
  const [selectedTag, setSelectedTag] = useState<string>("wrong_source");
  const [feedbackComment, setFeedbackComment] = useState("");
  const [isSubmittingFeedback, setIsSubmittingFeedback] = useState(false);
  const [feedbackSuccess, setFeedbackSuccess] = useState(false);
  const [copied, setCopied] = useState(false);
  const [isSpeaking, setIsSpeaking] = useState(false);

  if (isUser) {
    return (
      <div className="flex justify-end items-start gap-2.5 max-w-3xl ml-auto">
        <div className="bg-[#1C2024] text-white rounded-2xl rounded-tr-xs px-4 py-3 shadow-xs max-w-xl text-sm leading-relaxed">
          <p className="whitespace-pre-wrap">{message.content}</p>
        </div>
        <div className="w-8 h-8 rounded-full bg-[#E5E2DB] text-[#1C2024] flex items-center justify-center flex-shrink-0 mt-0.5">
          <User className="w-4 h-4" />
        </div>
      </div>
    );
  }

  const handleChipClick = (index: number) => {
    setSelectedCitationIndex(index);
    setShowInlineSources(true);
    if (onOpenDrawer && message.citations) {
      onOpenDrawer(message.citations, index);
    }
  };

  const handleCopy = async () => {
    try {
      await navigator.clipboard.writeText(message.content);
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    } catch (err) {
      console.warn("Failed to copy message:", err);
    }
  };

  const handleSpeakToggle = () => {
    if (typeof window === "undefined" || !("speechSynthesis" in window)) return;

    if (isSpeaking) {
      window.speechSynthesis.cancel();
      setIsSpeaking(false);
      return;
    }

    window.speechSynthesis.cancel();

    // Clean markdown before speaking
    const textToSpeak = message.content
      .replace(/```[\s\S]*?```/g, "Code block omitted.")
      .replace(/`([^`]+)`/g, "$1")
      .replace(/\[([^\]]+)\]\([^)]+\)/g, "$1")
      .replace(/[*#_~]/g, "")
      .trim();

    if (!textToSpeak) return;

    const utterance = new SpeechSynthesisUtterance(textToSpeak);
    utterance.rate = 1.0;
    utterance.pitch = 1.0;

    const voices = window.speechSynthesis.getVoices();
    const hiVoice = voices.find((v) => v.lang.includes("hi") || v.lang.includes("HI"));
    if (hiVoice) {
      utterance.voice = hiVoice;
    }

    utterance.onend = () => setIsSpeaking(false);
    utterance.onerror = () => setIsSpeaking(false);

    setIsSpeaking(true);
    window.speechSynthesis.speak(utterance);
  };

  const handleUpvote = async () => {
    if (feedbackSuccess || !repoId) return;
    setFeedbackRating("up");
    setShowFeedbackModal(false);
    try {
      await submitChatFeedback({
        repo_id: repoId,
        session_id: sessionId || undefined,
        message_id: message.id,
        rating: "up",
      });
      setFeedbackSuccess(true);
    } catch (err) {
      console.warn("Upvote feedback failed:", err);
    }
  };

  const handleDownvoteToggle = () => {
    if (feedbackSuccess) return;
    setFeedbackRating("down");
    setShowFeedbackModal(!showFeedbackModal);
  };

  const handleSubmitDetailedFeedback = async (e?: React.FormEvent) => {
    if (e) e.preventDefault();
    if (!repoId) return;
    setIsSubmittingFeedback(true);
    try {
      await submitChatFeedback({
        repo_id: repoId,
        session_id: sessionId || undefined,
        message_id: message.id,
        rating: "down",
        feedback_tag: selectedTag,
        comment: feedbackComment.trim() || undefined,
      });
      setFeedbackSuccess(true);
      setShowFeedbackModal(false);
    } catch (err) {
      console.warn("Feedback submission failed:", err);
    } finally {
      setIsSubmittingFeedback(false);
    }
  };

  const FEEDBACK_TAGS = [
    { id: "wrong_source", label: "Wrong Source / Bad Citation" },
    { id: "hallucination", label: "Hallucination / Speculative" },
    { id: "incomplete", label: "Incomplete Code" },
    { id: "incorrect_explanation", label: "Incorrect Explanation" },
  ];

  // Assistant message
  return (
    <div className="flex items-start gap-3.5 max-w-4xl mr-auto">
      {/* DevMind Assistant Avatar */}
      <div className="w-8 h-8 rounded-xl bg-[#0B6E5F] text-white flex items-center justify-center flex-shrink-0 mt-0.5 shadow-xs">
        <Terminal className="w-4 h-4" />
      </div>

      <div className="flex-1 space-y-3 min-w-0">
        {/* Author Label */}
        <div className="flex items-center gap-2">
          <span className="font-semibold text-xs text-[#1C2024]">DevMind AI</span>
          <span className="text-[10px] font-medium px-1.5 py-0.2 rounded bg-[#E6F4F1] text-[#0B6E5F] border border-[#BDE3DC]">
            Evidence-Grounded
          </span>
          {message.isStreaming && (
            <span className="text-[10px] font-semibold px-2 py-0.5 rounded-full bg-emerald-50 text-[#0B6E5F] border border-emerald-200 animate-pulse flex items-center gap-1">
              <span className="w-1.5 h-1.5 rounded-full bg-[#0B6E5F] animate-ping" />
              Streaming...
            </span>
          )}
          {message.timestamp && (
            <span className="text-[11px] text-[#A09D96]">{message.timestamp}</span>
          )}
        </div>

        {/* Insufficient Evidence Card */}
        {message.abstained && !message.isStreaming && (
          <div className="p-4 rounded-xl border border-amber-200 bg-[#FDF9F0] text-amber-900 text-xs space-y-1.5 shadow-xs">
            <div className="flex items-center gap-2 font-bold text-amber-800">
              <HelpCircle className="w-4 h-4 text-amber-600" />
              <span>Not enough evidence in the indexed codebase</span>
            </div>
            <p className="leading-relaxed text-amber-800/90">
              The retrieved code chunks did not contain definitive evidence to verify an answer without hallucination.
            </p>
          </div>
        )}

        {/* Inference Callout */}
        {message.inference_detected && !message.isStreaming && (
          <div className="p-3.5 rounded-xl border border-amber-300 bg-[#FBEFD9] text-[#6B3F00] text-xs space-y-1 shadow-xs">
            <div className="flex items-center gap-1.5 font-bold uppercase tracking-wider text-[11px]">
              <AlertTriangle className="w-3.5 h-3.5 text-[#B45309]" />
              <span>Inference Callout</span>
            </div>
            <p className="leading-relaxed">
              This response contains model inferences or deductions that extrapolate beyond literal source declarations.
            </p>
          </div>
        )}

        {/* Main Message Content */}
        <div className="bg-white border border-[#E5E2DB] rounded-2xl rounded-tl-xs p-5 shadow-xs">
          {message.isStreaming && !message.content ? (
            <div className="flex items-center gap-2.5 text-xs text-[#0B6E5F] font-medium py-1">
              <Loader2 className="w-4 h-4 animate-spin text-[#0B6E5F]" />
              <span>Synthesizing evidence-grounded answer...</span>
            </div>
          ) : (
            <div className="relative">
              <SafeMarkdown
                content={message.content}
                citations={message.citations}
                onCitationClick={(cit) => {
                  if (onOpenDrawer && message.citations) {
                    const idx = message.citations.findIndex(
                      (c) => c.file_path === cit.file_path && c.start_line === cit.start_line
                    );
                    onOpenDrawer(message.citations, idx >= 0 ? idx : 0);
                  }
                }}
              />
              {message.isStreaming && (
                <span
                  className="inline-block w-2 h-4 ml-1 bg-[#0B6E5F] rounded-xs animate-pulse align-middle"
                  title="Streaming"
                />
              )}
            </div>
          )}
        </div>

        {/* Verified Citations Row */}
        {!message.isStreaming && message.citations && message.citations.length > 0 && (
          <div className="space-y-3 pt-1">
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-1.5 text-xs font-semibold uppercase tracking-wider text-[#636A74]">
                <FileCode2 className="w-3.5 h-3.5 text-[#0B6E5F]" />
                <span>Verified Citations ({message.citations.length})</span>
              </div>

              <button
                type="button"
                onClick={() => setShowInlineSources(!showInlineSources)}
                className="inline-flex items-center gap-1 text-xs text-[#0B6E5F] hover:text-[#085449] font-medium transition-colors cursor-pointer"
              >
                <span>{showInlineSources ? "Hide Sources" : "View Sources"}</span>
                {showInlineSources ? (
                  <ChevronUp className="w-3.5 h-3.5" />
                ) : (
                  <ChevronDown className="w-3.5 h-3.5" />
                )}
              </button>
            </div>

            {/* Citation Chips */}
            <div className="flex flex-wrap gap-2">
              {message.citations.map((cite, cIdx) => (
                <CitationChip
                  key={cIdx}
                  index={cIdx + 1}
                  citation={cite}
                  isActive={selectedCitationIndex === cIdx + 1}
                  onClick={() => handleChipClick(cIdx + 1)}
                />
              ))}
            </div>

            {/* Expandable Inline Source Cards */}
            {showInlineSources && (
              <div className="space-y-3 pt-2">
                {message.citations.map((cite, cIdx) => (
                  <SourceCard
                    key={cIdx}
                    index={cIdx + 1}
                    citation={cite}
                    isHighlighted={selectedCitationIndex === cIdx + 1}
                  />
                ))}
              </div>
            )}
          </div>
        )}

        {/* Feature 5: Answer Feedback and Action Row */}
        {!message.isStreaming && message.content && (
          <div className="pt-1">
            <div className="flex items-center justify-between gap-3 text-xs text-[#636A74]">
              {/* Left Action Buttons */}
              <div className="flex items-center gap-1.5">
                {/* Thumbs Up Button */}
                <button
                  type="button"
                  onClick={handleUpvote}
                  title="Answer is accurate and helpful"
                  className={`inline-flex items-center gap-1.5 px-2.5 py-1 rounded-lg text-xs font-medium transition-colors border cursor-pointer ${
                    feedbackRating === "up"
                      ? "bg-emerald-50 text-[#0B6E5F] border-emerald-300 font-semibold shadow-xs"
                      : "bg-white text-[#636A74] border-[#E5E2DB] hover:bg-[#FAF9F6] hover:text-[#1C2024]"
                  }`}
                >
                  <ThumbsUp className="w-3.5 h-3.5" />
                  <span>Helpful</span>
                </button>

                {/* Thumbs Down Button */}
                <button
                  type="button"
                  onClick={handleDownvoteToggle}
                  title="Report citation or accuracy issues"
                  className={`inline-flex items-center gap-1.5 px-2.5 py-1 rounded-lg text-xs font-medium transition-colors border cursor-pointer ${
                    feedbackRating === "down"
                      ? "bg-rose-50 text-rose-700 border-rose-300 font-semibold shadow-xs"
                      : "bg-white text-[#636A74] border-[#E5E2DB] hover:bg-[#FAF9F6] hover:text-[#1C2024]"
                  }`}
                >
                  <ThumbsDown className="w-3.5 h-3.5" />
                  <span>Report issue</span>
                </button>

                {/* Copy Answer Button */}
                <button
                  type="button"
                  onClick={handleCopy}
                  title="Copy response markdown"
                  className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-lg text-xs font-medium text-[#636A74] bg-white border border-[#E5E2DB] hover:bg-[#FAF9F6] hover:text-[#1C2024] transition-colors cursor-pointer"
                >
                  {copied ? (
                    <>
                      <Check className="w-3.5 h-3.5 text-[#0B6E5F]" />
                      <span className="text-[#0B6E5F] font-semibold">Copied!</span>
                    </>
                  ) : (
                    <>
                      <Copy className="w-3.5 h-3.5" />
                      <span>Copy</span>
                    </>
                  )}
                </button>

                {/* Voice Read Aloud Button */}
                <button
                  type="button"
                  onClick={handleSpeakToggle}
                  title={isSpeaking ? "Stop reading aloud" : "Listen to answer (Read Aloud)"}
                  className={`inline-flex items-center gap-1.5 px-2.5 py-1 rounded-lg text-xs font-medium transition-colors border cursor-pointer ${
                    isSpeaking
                      ? "bg-rose-50 text-rose-700 border-rose-300 font-semibold shadow-xs animate-pulse"
                      : "bg-white text-[#636A74] border-[#E5E2DB] hover:bg-[#FAF9F6] hover:text-[#1C2024]"
                  }`}
                >
                  {isSpeaking ? (
                    <>
                      <VolumeX className="w-3.5 h-3.5 text-rose-600" />
                      <span>Stop</span>
                    </>
                  ) : (
                    <>
                      <Volume2 className="w-3.5 h-3.5 text-[#0B6E5F]" />
                      <span>Listen</span>
                    </>
                  )}
                </button>
              </div>

              {/* Status Indicator */}
              {feedbackSuccess && (
                <div className="flex items-center gap-1.5 text-xs text-[#0B6E5F] font-medium bg-[#E6F4F1] px-2.5 py-0.5 rounded-lg border border-[#BDE3DC]">
                  <Check className="w-3.5 h-3.5" />
                  <span>Feedback recorded in MongoDB</span>
                </div>
              )}
            </div>

            {/* Downvote / Wrong Source Feedback Form */}
            {showFeedbackModal && (
              <form
                onSubmit={handleSubmitDetailedFeedback}
                className="mt-3 p-4 rounded-xl border border-rose-200 bg-[#FFFDFD] space-y-3 shadow-xs animate-in fade-in duration-200"
              >
                <div className="flex items-center justify-between">
                  <div className="flex items-center gap-1.5 font-semibold text-xs text-[#1C2024]">
                    <Flag className="w-3.5 h-3.5 text-rose-600" />
                    <span>What was wrong with this answer?</span>
                  </div>
                  <button
                    type="button"
                    onClick={() => setShowFeedbackModal(false)}
                    className="text-[#A09D96] hover:text-[#1C2024] p-0.5 rounded transition-colors cursor-pointer"
                  >
                    <X className="w-3.5 h-3.5" />
                  </button>
                </div>

                {/* Category Pills */}
                <div className="flex flex-wrap gap-2">
                  {FEEDBACK_TAGS.map((tag) => (
                    <button
                      key={tag.id}
                      type="button"
                      onClick={() => setSelectedTag(tag.id)}
                      className={`text-xs px-2.5 py-1 rounded-lg border font-medium transition-all cursor-pointer ${
                        selectedTag === tag.id
                          ? "bg-rose-100 text-rose-800 border-rose-300 font-semibold"
                          : "bg-white text-[#636A74] border-[#E5E2DB] hover:bg-[#FAF9F6]"
                      }`}
                    >
                      {tag.label}
                    </button>
                  ))}
                </div>

                {/* Comment Input */}
                <div>
                  <input
                    type="text"
                    value={feedbackComment}
                    onChange={(e) => setFeedbackComment(e.target.value)}
                    placeholder="Optional details (e.g. line numbers don't match or function missing)..."
                    className="w-full text-xs px-3 py-2 rounded-lg border border-[#E5E2DB] bg-white text-[#1C2024] placeholder-[#A09D96] focus:outline-none focus:border-rose-400 focus:ring-1 focus:ring-rose-200"
                  />
                </div>

                {/* Submit & Cancel Buttons */}
                <div className="flex items-center justify-end gap-2 pt-1">
                  <button
                    type="button"
                    onClick={() => setShowFeedbackModal(false)}
                    className="px-3 py-1.5 text-xs text-[#636A74] hover:text-[#1C2024] font-medium transition-colors cursor-pointer"
                  >
                    Cancel
                  </button>
                  <button
                    type="submit"
                    disabled={isSubmittingFeedback}
                    className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-semibold bg-[#1C2024] text-white hover:bg-black transition-colors disabled:opacity-50 cursor-pointer shadow-xs"
                  >
                    {isSubmittingFeedback ? (
                      <>
                        <Loader2 className="w-3.5 h-3.5 animate-spin" />
                        <span>Submitting...</span>
                      </>
                    ) : (
                      <>
                        <Send className="w-3 h-3" />
                        <span>Submit Report</span>
                      </>
                    )}
                  </button>
                </div>
              </form>
            )}
          </div>
        )}
      </div>
    </div>
  );
};
