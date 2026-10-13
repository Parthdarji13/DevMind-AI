"use client";

import React, { useState, useRef, useEffect, useCallback } from "react";
import {
  ArrowUp,
  Loader2,
  Mic,
  MicOff,
  Radio,
  Languages,
  AlertCircle,
  X,
} from "lucide-react";

interface ChatInputProps {
  onSendMessage: (question: string) => void;
  isLoading: boolean;
  onOpenVoiceCall?: () => void;
}

export const ChatInput: React.FC<ChatInputProps> = ({
  onSendMessage,
  isLoading,
  onOpenVoiceCall,
}) => {
  const [text, setText] = useState("");
  const [isListening, setIsListening] = useState(false);
  const [voiceLang, setVoiceLang] = useState<"hi-IN" | "en-IN">("hi-IN");
  const [voiceError, setVoiceError] = useState<string | null>(null);
  const [isSupported, setIsSupported] = useState(true);

  const textareaRef = useRef<HTMLTextAreaElement>(null);
  const recognitionRef = useRef<any>(null);
  const baseTextRef = useRef<string>("");

  // Check Web Speech API support on mount
  useEffect(() => {
    if (typeof window !== "undefined") {
      const SpeechRecognition =
        (window as any).SpeechRecognition ||
        (window as any).webkitSpeechRecognition;
      if (!SpeechRecognition) {
        setIsSupported(false);
      }
    }
  }, []);

  // Auto-resize textarea height
  useEffect(() => {
    if (textareaRef.current) {
      textareaRef.current.style.height = "auto";
      textareaRef.current.style.height = `${Math.min(textareaRef.current.scrollHeight, 160)}px`;
    }
  }, [text]);

  // Clean code technical phrases from spoken words
  const cleanSpokenTranscript = (rawText: string): string => {
    let cleaned = rawText;
    const replacements: [RegExp, string][] = [
      [/\bdot\s*py\b/gi, ".py"],
      [/\bdot\s*js\b/gi, ".js"],
      [/\bdot\s*ts\b/gi, ".ts"],
      [/\bdot\s*json\b/gi, ".json"],
      [/\bdot\s*jsx\b/gi, ".jsx"],
      [/\bdot\s*tsx\b/gi, ".tsx"],
      [/\bdot\s*html\b/gi, ".html"],
      [/\bdot\s*css\b/gi, ".css"],
      [/\bdot\s*env\b/gi, ".env"],
      [/\bforward\s*slash\b/gi, "/"],
      [/\bback\s*slash\b/gi, "\\"],
      [/\bunderscore\b/gi, "_"],
      [/\bhyphen\b/gi, "-"],
    ];

    for (const [pattern, replacement] of replacements) {
      cleaned = cleaned.replace(pattern, replacement);
    }
    return cleaned;
  };

  const stopListening = useCallback(() => {
    if (recognitionRef.current) {
      try {
        recognitionRef.current.stop();
      } catch {}
      recognitionRef.current = null;
    }
    baseTextRef.current = "";
    setIsListening(false);
  }, []);

  const startListening = () => {
    if (typeof window === "undefined") return;
    const SpeechRecognition =
      (window as any).SpeechRecognition ||
      (window as any).webkitSpeechRecognition;

    if (!SpeechRecognition) {
      setVoiceError("Voice chat is not supported by your browser. Please use Chrome or Edge.");
      return;
    }

    setVoiceError(null);
    baseTextRef.current = text.trim();

    try {
      const recognition = new SpeechRecognition();
      recognition.lang = voiceLang;
      recognition.continuous = true;
      recognition.interimResults = true;
      recognition.maxAlternatives = 1;

      recognition.onstart = () => {
        setIsListening(true);
      };

      recognition.onresult = (event: any) => {
        let finalTranscript = "";
        let interimTranscript = "";

        for (let i = 0; i < event.results.length; ++i) {
          const item = event.results[i];
          const transcriptText = item[0].transcript;
          if (item.isFinal) {
            finalTranscript += transcriptText;
          } else {
            interimTranscript += transcriptText;
          }
        }

        const currentSpoken = (finalTranscript + interimTranscript).trim();
        if (currentSpoken) {
          const processed = cleanSpokenTranscript(currentSpoken);
          const base = baseTextRef.current;
          setText(base ? `${base} ${processed}` : processed);
        }
      };

      recognition.onerror = (event: any) => {
        console.warn("Speech recognition error:", event.error);
        if (event.error === "network") {
          setVoiceError(
            "Brave / Network Blocked: Web Speech API Google servers use karta hai jo Brave Browser me by default OFF hota hai. Ise brave://settings/system me jaakar 'Use Google services for speech recognition' ON karein, ya Google Chrome / MS Edge use karein."
          );
        } else if (event.error === "not-allowed") {
          setVoiceError("Microphone permission was denied. Please allow microphone access in your browser address bar.");
        } else if (event.error === "no-speech") {
          // Ignore no-speech timeouts
        } else if (event.error === "audio-capture") {
          setVoiceError("No microphone detected. Please connect an audio input device.");
        } else {
          setVoiceError(`Voice input error (${event.error}). Please retry or type manually.`);
        }
        stopListening();
      };

      recognition.onend = () => {
        setIsListening(false);
      };

      recognitionRef.current = recognition;
      recognition.start();
    } catch (err: any) {
      console.warn("Could not start speech recognition:", err);
      setVoiceError("Could not start speech recognition. Please verify microphone settings.");
      setIsListening(false);
    }
  };

  const toggleListening = () => {
    if (isListening) {
      stopListening();
    } else {
      startListening();
    }
  };

  const handleSubmit = (e?: React.FormEvent) => {
    if (e) e.preventDefault();
    if (isListening) {
      stopListening();
    }
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
      {/* Listening Status Banner */}
      {isListening && (
        <div className="flex items-center justify-between px-3.5 py-2 rounded-xl bg-emerald-50 border border-emerald-200 text-xs text-emerald-900 animate-in fade-in slide-in-from-bottom-2 duration-200">
          <div className="flex items-center gap-2">
            <span className="relative flex h-2.5 w-2.5">
              <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-emerald-400 opacity-75" />
              <span className="relative inline-flex rounded-full h-2.5 w-2.5 bg-[#0B6E5F]" />
            </span>
            <span className="font-semibold">
              Listening ({voiceLang === "hi-IN" ? "Hindi / Hinglish" : "English"})...
            </span>
            <span className="text-[#636A74] text-[11px] hidden sm:inline">
              Speak code questions naturally
            </span>
          </div>

          <div className="flex items-center gap-1.5">
            <button
              type="button"
              onClick={() => {
                stopListening();
                handleSubmit();
              }}
              className="text-[11px] font-semibold px-2 py-0.5 rounded-md bg-[#0B6E5F] text-white hover:bg-[#085449] transition-colors cursor-pointer"
            >
              Done & Ask
            </button>
            <button
              type="button"
              onClick={stopListening}
              className="p-1 rounded-md text-[#636A74] hover:text-[#1C2024] hover:bg-black/5 transition-colors cursor-pointer"
            >
              <X className="w-3.5 h-3.5" />
            </button>
          </div>
        </div>
      )}

      {/* Voice Error Notification */}
      {voiceError && (
        <div className="flex items-center justify-between px-3 py-1.5 rounded-xl bg-amber-50 border border-amber-200 text-xs text-amber-900 animate-in fade-in duration-150">
          <div className="flex items-center gap-1.5">
            <AlertCircle className="w-3.5 h-3.5 text-amber-600 flex-shrink-0" />
            <span>{voiceError}</span>
          </div>
          <button
            type="button"
            onClick={() => setVoiceError(null)}
            className="p-0.5 rounded text-amber-700 hover:text-amber-900 cursor-pointer"
          >
            <X className="w-3 h-3" />
          </button>
        </div>
      )}

      {/* Main Input Form */}
      <form
        onSubmit={handleSubmit}
        className={`relative rounded-2xl border transition-all shadow-xs overflow-hidden ${
          isListening
            ? "border-[#0B6E5F] ring-2 ring-[#0B6E5F]/20 bg-emerald-50/20"
            : "border-[#D6D2CA] bg-white focus-within:border-[#0B6E5F] focus-within:ring-2 focus-within:ring-[#0B6E5F]/15"
        }`}
      >
        <textarea
          ref={textareaRef}
          value={text}
          onChange={(e) => setText(e.target.value)}
          onKeyDown={handleKeyDown}
          placeholder={
            isListening
              ? "Listening to your voice... (words will appear here automatically)"
              : "Ask in English, Hinglish, or Hindi... (e.g., Authentication kaise handle hota hai?)"
          }
          disabled={isLoading}
          rows={2}
          className="w-full resize-none px-4 pt-3.5 pb-12 text-sm text-[#1C2024] placeholder-[#A09D96] outline-none bg-transparent leading-relaxed"
        />

        {/* Bottom Toolbar inside Textarea */}
        <div className="absolute right-3 bottom-2.5 flex items-center gap-2">
          {/* Voice Language Toggle */}
          <div className="flex items-center bg-[#FAF9F6] border border-[#EAE8E2] rounded-xl p-0.5 text-[11px]">
            <button
              type="button"
              onClick={() => {
                setVoiceLang("hi-IN");
                if (isListening) {
                  stopListening();
                }
              }}
              title="Hindi & Hinglish voice input (hi-IN)"
              className={`px-2 py-0.5 rounded-lg font-medium transition-colors cursor-pointer ${
                voiceLang === "hi-IN"
                  ? "bg-[#0B6E5F] text-white shadow-xs"
                  : "text-[#636A74] hover:text-[#1C2024]"
              }`}
            >
              हिन्दी / Hinglish
            </button>
            <button
              type="button"
              onClick={() => {
                setVoiceLang("en-IN");
                if (isListening) {
                  stopListening();
                }
              }}
              title="English voice input (en-IN)"
              className={`px-2 py-0.5 rounded-lg font-medium transition-colors cursor-pointer ${
                voiceLang === "en-IN"
                  ? "bg-[#0B6E5F] text-white shadow-xs"
                  : "text-[#636A74] hover:text-[#1C2024]"
              }`}
            >
              English
            </button>
          </div>

          {/* Dedicated Voice Call Screen Button */}
          {onOpenVoiceCall && (
            <button
              type="button"
              onClick={onOpenVoiceCall}
              disabled={isLoading}
              className="inline-flex items-center gap-1 px-2.5 py-1 text-xs font-semibold rounded-xl text-white bg-gradient-to-r from-[#0B6E5F] to-[#085247] hover:from-[#095b4e] hover:to-[#064239] transition-all cursor-pointer shadow-xs disabled:opacity-50"
              title="Open Dedicated Hands-Free Voice Call"
            >
              <Radio className="w-3.5 h-3.5 text-white animate-pulse" />
              <span className="hidden sm:inline">Voice Call</span>
            </button>
          )}

          {/* Voice Input Microphone Button */}
          {isSupported && (
            <button
              type="button"
              onClick={toggleListening}
              disabled={isLoading}
              className={`w-8 h-8 rounded-xl flex items-center justify-center transition-all cursor-pointer shadow-xs ${
                isListening
                  ? "bg-rose-500 hover:bg-rose-600 text-white animate-pulse ring-2 ring-rose-400/40"
                  : "bg-white hover:bg-[#F2EFE9] border border-[#E5E2DB] text-[#0B6E5F]"
              }`}
              title={
                isListening
                  ? "Stop listening"
                  : `Voice Typing into box (${voiceLang === "hi-IN" ? "Hindi/Hinglish" : "English"})`
              }
            >
              {isListening ? (
                <MicOff className="w-4 h-4" />
              ) : (
                <Mic className="w-4 h-4" />
              )}
            </button>
          )}

          {/* Send Button */}
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
          Web Speech API • Real-time Speech-to-Text
        </span>
      </div>
    </div>
  );
};
