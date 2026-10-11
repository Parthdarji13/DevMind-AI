"use client";

import React, { useState, useRef, useEffect } from "react";
import { ArrowUp, Loader2 } from "lucide-react";

interface ChatInputProps {
  onSendMessage: (question: string) => void;
  isLoading: boolean;
}

export const ChatInput: React.FC<ChatInputProps> = ({
  onSendMessage,
  isLoading,
}) => {
  const [text, setText] = useState("");
  const textareaRef = useRef<HTMLTextAreaElement>(null);

  // Auto-resize textarea height
  useEffect(() => {
    if (textareaRef.current) {
      textareaRef.current.style.height = "auto";
      textareaRef.current.style.height = `${Math.min(textareaRef.current.scrollHeight, 160)}px`;
    }
  }, [text]);

  const handleSubmit = (e?: React.FormEvent) => {
    if (e) e.preventDefault();
    const clean = text.trim();
    if (!clean || isLoading) return;

    onSendMessage(clean);
    setText("");
    if (textareaRef.current) {
      textareaRef.current.style.height = "auto";
    }
  };

  const handleKeyDown = (e: React.KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      handleSubmit();
    }
  };

  return (
    <div className="space-y-2">
      <form
        onSubmit={handleSubmit}
        className="relative rounded-2xl border border-[#D6D2CA] bg-white focus-within:border-[#0B6E5F] focus-within:ring-2 focus-within:ring-[#0B6E5F]/15 transition-all shadow-xs overflow-hidden"
      >
        <textarea
          ref={textareaRef}
          value={text}
          onChange={(e) => setText(e.target.value)}
          onKeyDown={handleKeyDown}
          placeholder="Ask in English, Hinglish, or Hindi... (e.g., Authentication kaise handle hota hai?)"
          disabled={isLoading}
          rows={2}
          className="w-full resize-none px-4 pt-3.5 pb-12 text-sm text-[#1C2024] placeholder-[#A09D96] outline-none bg-transparent leading-relaxed"
        />

        <div className="absolute right-3 bottom-3 flex items-center gap-2">
          <button
            type="submit"
            disabled={isLoading || !text.trim()}
            className="w-8 h-8 rounded-xl bg-[#0B6E5F] hover:bg-[#085449] disabled:bg-[#ECE9E3] text-white disabled:text-[#A09D96] flex items-center justify-center transition-all cursor-pointer disabled:cursor-not-allowed shadow-xs"
            title="Send question (Enter)"
          >
            {isLoading ? (
              <Loader2 className="w-4 h-4 animate-spin" />
            ) : (
              <ArrowUp className="w-4 h-4" />
            )}
          </button>
        </div>
      </form>

      {/* Privacy and Multi-Turn Helper Note */}
      <div className="flex items-center justify-between text-[11px] text-[#636A74] px-1">
        <span>
          Press <kbd className="px-1 py-0.5 rounded bg-[#ECE9E3] font-mono text-[10px]">Enter</kbd> to ask, <kbd className="px-1 py-0.5 rounded bg-[#ECE9E3] font-mono text-[10px]">Shift+Enter</kbd> for newline
        </span>
        <span className="hidden sm:inline text-[#636A74] flex items-center gap-1.5">
          <span className="inline-block w-1.5 h-1.5 rounded-full bg-emerald-500" />
          English • Hinglish • हिन्दी supported
        </span>
      </div>
    </div>
  );
};
