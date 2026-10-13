"use client";

import React, { useState, useEffect, useRef, useCallback } from "react";
import {
  Mic,
  MicOff,
  Volume2,
  VolumeX,
  PhoneOff,
  Sparkles,
  RotateCcw,
  Radio,
  FileCode,
  X,
  Send,
  Globe,
  AlertCircle,
  Play,
  CheckCircle2,
} from "lucide-react";
import { IngestResponse, ChatMessage } from "@/lib/types";
import { askVoiceQuestion, ApiError } from "@/lib/api";
import { getStoredUser } from "@/lib/auth";

interface VoiceConversationModalProps {
  repo: IngestResponse;
  history: ChatMessage[];
  isOpen: boolean;
  onClose: () => void;
  onSyncTurn?: (question: string, spokenAnswer: string, citedFiles: string[]) => void;
}

type CallPhase = "idle" | "listening" | "thinking" | "speaking" | "cooldown";
type LanguageOption = "hi-IN" | "en-IN" | "en-US";

// Removes glued identical halves like "hellohello" -> "hello", "testtest" -> "test"
export function fixGluedDuplicate(word: string): string {
  const trimmed = word.trim();
  if (trimmed.length >= 4 && trimmed.length % 2 === 0) {
    const half = trimmed.length / 2;
    const firstHalf = trimmed.slice(0, half);
    const secondHalf = trimmed.slice(half);
    if (firstHalf.toLowerCase() === secondHalf.toLowerCase()) {
      return firstHalf;
    }
  }
  return trimmed;
}

// Utility to remove repeated stutter phrases (e.g. "Tell Tell me Tell me about") and glued duplicates
export function deduplicateSpokenText(text: string): string {
  const rawWords = text.trim().split(/\s+/).filter(Boolean);
  if (rawWords.length === 0) return "";
  const fixedWords = rawWords.map(fixGluedDuplicate);
  const cleaned: string[] = [];
  for (let i = 0; i < fixedWords.length; i++) {
    if (i === 0 || fixedWords[i].toLowerCase() !== fixedWords[i - 1].toLowerCase()) {
      cleaned.push(fixedWords[i]);
    }
  }
  return cleaned.join(" ");
}

// Global helper to unlock AudioContext and SpeechSynthesis on mobile user touch/click gestures
export function unlockMobileAudio() {
  if (typeof window === "undefined") return;

  // 1. Resume / Prime Web Audio Context
  const AudioCtx = window.AudioContext || (window as any).webkitAudioContext;
  if (AudioCtx) {
    try {
      const dummyCtx = new AudioCtx();
      if (dummyCtx.state === "suspended") {
        dummyCtx.resume();
      }
      const buffer = dummyCtx.createBuffer(1, 1, 22050);
      const source = dummyCtx.createBufferSource();
      source.buffer = buffer;
      source.connect(dummyCtx.destination);
      source.start(0);
      setTimeout(() => {
        try {
          dummyCtx.close();
        } catch {}
      }, 500);
    } catch {}
  }

  // 2. Prime Speech Synthesis
  if ("speechSynthesis" in window) {
    try {
      window.speechSynthesis.resume();
      const dummyUtterance = new SpeechSynthesisUtterance("");
      dummyUtterance.volume = 0;
      window.speechSynthesis.speak(dummyUtterance);
    } catch {}
  }
}

export const VoiceConversationModal: React.FC<VoiceConversationModalProps> = ({
  repo,
  history,
  isOpen,
  onClose,
  onSyncTurn,
}) => {
  const [callPhase, setCallPhase] = useState<CallPhase>("idle");
  const [language, setLanguage] = useState<LanguageOption>("en-IN");
  const [userTranscript, setUserTranscript] = useState<string>("");
  const [aiAnswer, setAiAnswer] = useState<string>("");
  const [citedFiles, setCitedFiles] = useState<string[]>([]);
  const [isMuted, setIsMuted] = useState<boolean>(false);
  const [networkErrorNotice, setNetworkErrorNotice] = useState<string | null>(null);
  const [audioLevel, setAudioLevel] = useState<number>(0);
  const [lastAudioBase64, setLastAudioBase64] = useState<string | null>(null);
  const [voiceHistory, setVoiceHistory] = useState<ChatMessage[]>([]);

  // Authoritative Phase Reference to prevent race conditions
  const callPhaseRef = useRef<CallPhase>("idle");
  const recognitionRef = useRef<any>(null);
  const silenceTimerRef = useRef<NodeJS.Timeout | null>(null);
  const cooldownTimerRef = useRef<NodeJS.Timeout | null>(null);
  const animFrameRef = useRef<number | null>(null);
  const sessionIdRef = useRef<string | null>(null);
  const audioPlayerRef = useRef<HTMLAudioElement | null>(null);
  const activeUtteranceRef = useRef<SpeechSynthesisUtterance | null>(null);
  const latestTranscriptRef = useRef<string>("");
  const initialHistoryRef = useRef<ChatMessage[]>([]);
  const sessionTurnsRef = useRef<ChatMessage[]>([]);
  const submitVoiceQueryRef = useRef<(q: string) => void>(() => {});

  const updatePhase = useCallback((newPhase: CallPhase) => {
    callPhaseRef.current = newPhase;
    setCallPhase(newPhase);
  }, []);

  // Stop any ongoing audio playback or speech synthesis
  const stopAllAudio = useCallback(() => {
    if (audioPlayerRef.current) {
      try {
        audioPlayerRef.current.pause();
        audioPlayerRef.current.currentTime = 0;
      } catch {}
      audioPlayerRef.current = null;
    }

    if (typeof window !== "undefined" && "speechSynthesis" in window) {
      try {
        window.speechSynthesis.cancel();
      } catch {}
    }
    activeUtteranceRef.current = null;
  }, []);

  // Stop speech recognition completely
  const stopListening = useCallback(() => {
    if (silenceTimerRef.current) {
      clearTimeout(silenceTimerRef.current);
      silenceTimerRef.current = null;
    }
    if (recognitionRef.current) {
      try {
        recognitionRef.current.onresult = null;
        recognitionRef.current.onend = null;
        recognitionRef.current.onerror = null;
        recognitionRef.current.abort();
      } catch {}
      recognitionRef.current = null;
    }
  }, []);

  // Start speech recognition cleanly (mobile-optimized)
  const startListening = useCallback(() => {
    if (typeof window === "undefined") return;
    const SpeechRecognition =
      (window as any).SpeechRecognition || (window as any).webkitSpeechRecognition;

    if (!SpeechRecognition) {
      setNetworkErrorNotice("Web Speech recognition is not supported in this browser. Please use Chrome, Edge, or Safari.");
      return;
    }

    // Safety guard: NEVER listen while thinking or speaking
    if (callPhaseRef.current === "thinking" || callPhaseRef.current === "speaking") {
      return;
    }

    try {
      stopListening();
      updatePhase("listening");

      const isMobile =
        typeof navigator !== "undefined" &&
        /Android|webOS|iPhone|iPad|iPod|BlackBerry|IEMobile|Opera Mini/i.test(navigator.userAgent);

      const recognition = new SpeechRecognition();
      // On mobile browsers, continuous = true causes speech doubling ("hellohello") and instant timeouts
      recognition.continuous = !isMobile;
      recognition.interimResults = true;
      recognition.maxAlternatives = 1;
      recognition.lang = language; // 'en-IN', 'hi-IN', or 'en-US'

      recognition.onstart = () => {
        updatePhase("listening");
        setNetworkErrorNotice(null);
      };

      recognition.onresult = (event: any) => {
        // Safety guard: if phase changed, ignore results
        if (callPhaseRef.current !== "listening") return;

        const finalParts: string[] = [];
        const interimParts: string[] = [];

        for (let i = 0; i < event.results.length; i++) {
          const item = event.results[i];
          const transcriptText = item[0]?.transcript?.trim() || "";
          if (!transcriptText) continue;
          if (item.isFinal) {
            finalParts.push(transcriptText);
          } else {
            interimParts.push(transcriptText);
          }
        }

        const finalJoined = finalParts.join(" ").trim();
        const interimJoined = interimParts.join(" ").trim();

        let combined = finalJoined;
        if (interimJoined) {
          if (!combined) {
            combined = interimJoined;
          } else if (!combined.toLowerCase().endsWith(interimJoined.toLowerCase())) {
            combined = `${combined} ${interimJoined}`;
          }
        }

        combined = deduplicateSpokenText(combined);

        if (combined) {
          setUserTranscript(combined);
          latestTranscriptRef.current = combined;

          // Hands-free VAD: Fast 650ms debounce for final sentence, 850ms for interim
          if (silenceTimerRef.current) clearTimeout(silenceTimerRef.current);
          const debounceDelay = finalParts.length > 0 ? 650 : 850;
          silenceTimerRef.current = setTimeout(() => {
            const queryToSend = latestTranscriptRef.current.trim();
            if (queryToSend.length >= 2) {
              latestTranscriptRef.current = "";
              submitVoiceQueryRef.current(queryToSend);
            }
          }, debounceDelay);
        }
      };

      recognition.onerror = (event: any) => {
        console.warn("Speech recognition error:", event.error);
        if (event.error === "network") {
          setNetworkErrorNotice(
            "Speech recognition network blocked. In Brave Browser, enable Google Speech Services under brave://settings/system, or use Google Chrome / Safari."
          );
        } else if (event.error === "not-allowed") {
          setNetworkErrorNotice("Microphone permission was denied. Please allow microphone access in your browser settings.");
        } else if (event.error === "audio-capture") {
          setNetworkErrorNotice("Microphone could not be accessed. Please ensure no other app is using your mic.");
        }

        // If no speech detected in this turn, keep listening ready for next utterance
        if (event.error === "no-speech") {
          return;
        }

        if (callPhaseRef.current === "listening") {
          updatePhase("idle");
        }
      };

      recognition.onend = () => {
        // ONLY restart if still in listening phase and not muted/closed
        if (callPhaseRef.current === "listening" && isOpen && !isMuted) {
          try {
            recognition.start();
          } catch {}
        }
      };

      recognitionRef.current = recognition;
      recognition.start();
    } catch (err) {
      console.warn("Could not start recognition:", err);
      // If recognition threw because already active, retry once cleanly
      setTimeout(() => {
        if (callPhaseRef.current === "listening" && isOpen && !isMuted) {
          try {
            if (recognitionRef.current) recognitionRef.current.start();
          } catch {}
        }
      }, 200);
    }
  }, [language, isOpen, isMuted, stopListening, updatePhase]);

  // Web Speech Fallback for browsers if MP3 audio fails
  const speakWithWebSpeechFallback = useCallback(
    (textToSpeak: string) => {
      if (typeof window === "undefined" || !("speechSynthesis" in window)) {
        updatePhase("idle");
        return;
      }

      try {
        window.speechSynthesis.cancel();
        window.speechSynthesis.resume();

        const utterance = new SpeechSynthesisUtterance(textToSpeak);
        activeUtteranceRef.current = utterance;
        utterance.rate = 1.0;
        utterance.pitch = 1.0;

        const voices = window.speechSynthesis.getVoices();
        if (voices && voices.length > 0) {
          if (language === "hi-IN" || /[\u0900-\u097F]/.test(textToSpeak)) {
            const hiVoice =
              voices.find((v) => v.lang === "hi-IN") ||
              voices.find((v) => v.lang === "en-IN") ||
              voices.find((v) => v.name.toLowerCase().includes("india"));
            if (hiVoice) utterance.voice = hiVoice;
          } else {
            const naturalVoice =
              voices.find((v) => v.lang === "en-IN") ||
              voices.find((v) => v.name.includes("Google") && v.lang.startsWith("en")) ||
              voices.find((v) => v.lang === "en-US") ||
              voices.find((v) => v.lang.startsWith("en"));
            if (naturalVoice) utterance.voice = naturalVoice;
          }
        }

        utterance.onstart = () => {
          updatePhase("speaking");
        };

        utterance.onend = () => {
          activeUtteranceRef.current = null;
          // Echo prevention cooldown: 400ms before auto-listening for next follow-up question
          updatePhase("cooldown");
          if (cooldownTimerRef.current) clearTimeout(cooldownTimerRef.current);
          cooldownTimerRef.current = setTimeout(() => {
            if (isOpen && !isMuted) {
              setUserTranscript(""); // Clear transcript for next question
              startListening();
            } else {
              updatePhase("idle");
            }
          }, 400);
        };

        utterance.onerror = (e) => {
          console.warn("Speech synthesis fallback error:", e);
          activeUtteranceRef.current = null;
          updatePhase("idle");
        };

        window.speechSynthesis.speak(utterance);
      } catch (err) {
        console.warn("Speech synthesis call failed:", err);
        updatePhase("idle");
      }
    },
    [language, isOpen, isMuted, updatePhase, startListening]
  );

  // Play Neural MP3 Spoken Audio from backend
  const playNeuralAudio = useCallback(
    (audioBase64: string | null | undefined, fallbackText: string) => {
      // 1. Strictly stop speech recognition so mic CANNOT hear DevMind speak
      stopListening();
      stopAllAudio();
      updatePhase("speaking");

      if (audioBase64 && audioBase64.length > 50) {
        try {
          const audio = new Audio(`data:audio/mp3;base64,${audioBase64}`);
          audioPlayerRef.current = audio;

          audio.onplay = () => {
            updatePhase("speaking");
          };

          audio.onended = () => {
            audioPlayerRef.current = null;
            // Echo prevention cooldown: 400ms room silence before opening mic for follow-up
            updatePhase("cooldown");
            if (cooldownTimerRef.current) clearTimeout(cooldownTimerRef.current);
            cooldownTimerRef.current = setTimeout(() => {
              if (isOpen && !isMuted) {
                setUserTranscript(""); // Clear transcript for follow-up question
                startListening(); // Auto-listen for next question!
              } else {
                updatePhase("idle");
              }
            }, 400);
          };

          audio.onerror = (err) => {
            console.warn("Audio element error, falling back to Web Speech:", err);
            audioPlayerRef.current = null;
            speakWithWebSpeechFallback(fallbackText);
          };

          const playPromise = audio.play();
          if (playPromise !== undefined) {
            playPromise.catch((playErr) => {
              console.warn("Audio play rejected, falling back to Web Speech:", playErr);
              speakWithWebSpeechFallback(fallbackText);
            });
          }
          return;
        } catch (audioErr) {
          console.warn("Audio creation failed:", audioErr);
        }
      }

      // If no MP3 generated, fall back to browser Web Speech
      speakWithWebSpeechFallback(fallbackText);
    },
    [stopListening, stopAllAudio, updatePhase, isOpen, isMuted, startListening, speakWithWebSpeechFallback]
  );

  // Submit voice inquiry to backend (maintains conversation history for follow-ups!)
  const submitVoiceQuery = useCallback(
    async (spokenQuestion: string) => {
      const q = spokenQuestion.trim();
      if (!q) return;

      // 1. Immediately kill the mic so it cannot pick up anything
      stopListening();
      stopAllAudio();

      updatePhase("thinking");
      setUserTranscript(q);

      try {
        // Combine initial workspace history + turns from this live voice call for follow-up context!
        const fullHistory = [...initialHistoryRef.current, ...sessionTurnsRef.current];

        const currentUser = getStoredUser();
        const res = await askVoiceQuestion({
          repo_id: repo.repo_id,
          question: q,
          history: fullHistory,
          session_id: sessionIdRef.current,
          user_name: currentUser?.name || currentUser?.id || "Parth",
        });

        if (res.session_id) sessionIdRef.current = res.session_id;

        setAiAnswer(res.answer);
        setCitedFiles(res.cited_files || []);
        if (res.audio_base64) {
          setLastAudioBase64(res.audio_base64);
        }

        // Add to voice session memory so follow-up questions understand context!
        const newTurns = [
          { role: "user" as const, content: q },
          { role: "assistant" as const, content: res.answer },
        ];
        sessionTurnsRef.current.push(...newTurns);
        setVoiceHistory([...sessionTurnsRef.current]);

        // Sync turn back to chat workspace thread
        if (onSyncTurn) {
          onSyncTurn(q, res.answer, res.cited_files || []);
        }

        // Play the neural audio response
        playNeuralAudio(res.audio_base64, res.answer);
      } catch (err: any) {
        console.error("Voice inquiry error:", err);
        let errorMsg =
          "I ran into an issue retrieving that from the codebase. Please try speaking your question again.";
        if (err instanceof ApiError) {
          if (err.status === 401) {
            errorMsg = "Authentication required. Please sign in or use guest login to use voice call.";
          } else if (err.status === 403) {
            errorMsg = "Access denied. You do not have permission to access this repository.";
          } else if (err.status === 404) {
            errorMsg = "Repository index not found on server. Please re-index the repository or return home.";
          } else if (err.status === 429) {
            errorMsg = "AI rate limit reached. Please wait a few moments and try again.";
          } else if (err.status === 502 || err.status === 503 || err.status === 504) {
            errorMsg = "The backend server is currently waking up or busy. Please retry in a few moments.";
          } else if (err.message && !err.message.includes("status")) {
            errorMsg = err.message;
          }
        } else if (err instanceof Error && err.message) {
          if (err.message.includes("Failed to fetch") || err.message.includes("Network")) {
            errorMsg = "Connecting to backend server... If server is waking up, please retry in 10 seconds.";
          } else {
            errorMsg = err.message;
          }
        }
        setAiAnswer(errorMsg);
        playNeuralAudio(null, errorMsg);
      }
    },
    [repo.repo_id, onSyncTurn, stopListening, stopAllAudio, updatePhase, playNeuralAudio]
  );

  // Keep submitVoiceQueryRef updated
  submitVoiceQueryRef.current = submitVoiceQuery;

  // Smooth reactive orb animation based on call phase (No getUserMedia mic locking!)
  const startAudioVisualizer = useCallback(() => {
    let phaseAngle = 0;

    const animateVisualizer = () => {
      phaseAngle += 0.08;
      const currentPhase = callPhaseRef.current;

      let targetLevel = 0;
      if (currentPhase === "listening") {
        const base = 25 + Math.sin(phaseAngle) * 15;
        const speechBoost = latestTranscriptRef.current ? 35 : 0;
        targetLevel = Math.min(100, Math.round(base + speechBoost));
      } else if (currentPhase === "speaking") {
        const voicePulse = 55 + Math.sin(phaseAngle * 2) * 25 + Math.cos(phaseAngle * 3.3) * 10;
        targetLevel = Math.min(100, Math.round(voicePulse));
      } else if (currentPhase === "thinking") {
        targetLevel = Math.round(20 + Math.sin(phaseAngle * 1.5) * 12);
      } else if (currentPhase === "cooldown") {
        targetLevel = Math.round(15 + Math.sin(phaseAngle) * 8);
      } else {
        targetLevel = 0;
      }

      setAudioLevel(targetLevel);
      animFrameRef.current = requestAnimationFrame(animateVisualizer);
    };

    if (animFrameRef.current) {
      cancelAnimationFrame(animFrameRef.current);
    }
    animFrameRef.current = requestAnimationFrame(animateVisualizer);
  }, []);

  const cleanupAudioVisualizer = useCallback(() => {
    if (animFrameRef.current) {
      cancelAnimationFrame(animFrameRef.current);
      animFrameRef.current = null;
    }
    setAudioLevel(0);
  }, []);

  // Controls: Mute/Unmute
  const handleToggleMute = () => {
    if (isMuted) {
      setIsMuted(false);
      startListening();
    } else {
      setIsMuted(true);
      stopListening();
      stopAllAudio();
      updatePhase("idle");
    }
  };

  // User Interrupt Button (stops DevMind speaking and starts listening immediately)
  const handleInterrupt = () => {
    stopAllAudio();
    if (!isMuted) {
      setUserTranscript("");
      startListening();
    } else {
      updatePhase("idle");
    }
  };

  // Click Central Orb to manually trigger listening anytime
  const handleOrbClick = () => {
    unlockMobileAudio();
    if (callPhase === "speaking") {
      handleInterrupt();
    } else if (callPhase === "listening") {
      // Toggle off to idle
      stopListening();
      updatePhase("idle");
    } else {
      // Start listening
      setIsMuted(false);
      setUserTranscript("");
      startListening();
    }
  };

  // Replay last answer audio
  const handleReplayAnswer = () => {
    if (aiAnswer) {
      playNeuralAudio(lastAudioBase64, aiAnswer);
    }
  };

  // Manual Send Button (submit transcript immediately without waiting 1.8s)
  const handleManualSend = () => {
    if (userTranscript.trim()) {
      submitVoiceQuery(userTranscript.trim());
    }
  };

  // Modal open / close lifecycle
  useEffect(() => {
    if (isOpen) {
      initialHistoryRef.current = [...history];
      sessionTurnsRef.current = [];
      setVoiceHistory([]);
      startAudioVisualizer();
      if (!isMuted) {
        startListening();
      }
    } else {
      stopListening();
      stopAllAudio();
      cleanupAudioVisualizer();
      if (cooldownTimerRef.current) clearTimeout(cooldownTimerRef.current);
      setUserTranscript("");
      setAiAnswer("");
      setLastAudioBase64(null);
      sessionTurnsRef.current = [];
      setVoiceHistory([]);
      updatePhase("idle");
    }

    return () => {
      stopListening();
      stopAllAudio();
      cleanupAudioVisualizer();
      if (cooldownTimerRef.current) clearTimeout(cooldownTimerRef.current);
    };
  }, [isOpen, startAudioVisualizer, cleanupAudioVisualizer, startListening, stopListening, stopAllAudio, updatePhase, isMuted, history]);

  if (!isOpen) return null;

  const quickPrompts = [
    "Explain this project architecture",
    "Where are the main API endpoints defined?",
    "How does authentication work in this app?",
    "What database or storage does this project use?",
  ];

  return (
    <div
      role="dialog"
      aria-modal="true"
      aria-labelledby="voice-modal-title"
      className="fixed inset-0 z-50 bg-[#070A10]/95 backdrop-blur-2xl flex flex-col justify-between overflow-y-auto select-none animate-fadeIn"
    >
      {/* Background Ambient Glowing Orbs */}
      <div className="absolute top-1/4 left-1/4 -translate-x-1/2 -translate-y-1/2 w-80 h-80 bg-[#0B6E5F]/15 rounded-full blur-3xl pointer-events-none" />
      <div className="absolute bottom-1/4 right-1/4 translate-x-1/2 translate-y-1/2 w-80 h-80 bg-[#3B82F6]/15 rounded-full blur-3xl pointer-events-none" />

      {/* TOP BAR */}
      <header className="shrink-0 relative z-10 w-full max-w-4xl mx-auto px-5 py-3 flex items-center justify-between border-b border-white/5">
        <div className="flex items-center gap-2.5">
          <div className="w-7 h-7 rounded-lg bg-gradient-to-tr from-[#0B6E5F] to-[#14B8A6] flex items-center justify-center text-white shadow-sm">
            <Radio className="w-3.5 h-3.5 animate-pulse" />
          </div>
          <div>
            <div className="flex items-center gap-2">
              <h2 id="voice-modal-title" className="text-xs sm:text-sm font-bold text-white tracking-wide">
                DevMind Voice Call
              </h2>
              <span className="px-2 py-0.5 text-[9px] font-semibold uppercase tracking-wider rounded-full bg-emerald-500/20 text-emerald-400 border border-emerald-500/30">
                Continuous Call
              </span>
            </div>
            <p className="text-[11px] text-slate-400">
              Repo: <span className="text-slate-200 font-mono">{repo.repo_name || repo.repo_id.slice(0, 12)}</span>
            </p>
          </div>
        </div>

        {/* Top Controls: Language & Close */}
        <div className="flex items-center gap-2.5">
          {/* Language Selector */}
          <div className="flex items-center bg-white/5 border border-white/10 rounded-lg p-0.5 text-[11px]">
            <button
              type="button"
              onClick={() => {
                unlockMobileAudio();
                setLanguage("en-IN");
                stopListening();
                setTimeout(startListening, 200);
              }}
              className={`px-2 py-0.5 rounded-md transition-colors cursor-pointer ${
                language === "en-IN"
                  ? "bg-[#0B6E5F] text-white font-medium shadow-xs"
                  : "text-slate-400 hover:text-white"
              }`}
              title="English (Indian Accent - Recommended)"
            >
              English (IN)
            </button>
            <button
              type="button"
              onClick={() => {
                unlockMobileAudio();
                setLanguage("hi-IN");
                stopListening();
                setTimeout(startListening, 200);
              }}
              className={`px-2 py-0.5 rounded-md transition-colors cursor-pointer ${
                language === "hi-IN"
                  ? "bg-[#0B6E5F] text-white font-medium shadow-xs"
                  : "text-slate-400 hover:text-white"
              }`}
              title="Hindi & Hinglish voice recognition"
            >
              हिन्दी / Hinglish
            </button>
            <button
              type="button"
              onClick={() => {
                unlockMobileAudio();
                setLanguage("en-US");
                stopListening();
                setTimeout(startListening, 200);
              }}
              className={`px-2 py-0.5 rounded-md transition-colors cursor-pointer ${
                language === "en-US"
                  ? "bg-[#0B6E5F] text-white font-medium shadow-xs"
                  : "text-slate-400 hover:text-white"
              }`}
              title="English (Global / US)"
            >
              English (US)
            </button>
          </div>

          {/* Close Button */}
          <button
            type="button"
            onClick={onClose}
            className="w-7 h-7 rounded-lg bg-white/5 hover:bg-white/10 border border-white/10 text-slate-300 hover:text-white flex items-center justify-center transition-all cursor-pointer"
            title="Minimize voice call"
          >
            <X className="w-4 h-4" />
          </button>
        </div>
      </header>

      {/* CENTER STAGE */}
      <main className="relative z-10 w-full max-w-2xl mx-auto px-4 py-2 flex-1 flex flex-col items-center justify-center text-center">
        {networkErrorNotice && (
          <div className="mb-3 w-full p-2.5 rounded-xl bg-amber-500/10 border border-amber-500/30 text-amber-200 text-xs flex items-start gap-2 text-left backdrop-blur-md animate-fadeIn">
            <AlertCircle className="w-3.5 h-3.5 text-amber-400 shrink-0 mt-0.5" />
            <div className="flex-1 space-y-0.5">
              <p className="font-semibold text-amber-300">Microphone Notice</p>
              <p className="text-amber-200/90 text-[11px] leading-relaxed">{networkErrorNotice}</p>
            </div>
            <button
              type="button"
              onClick={() => setNetworkErrorNotice(null)}
              className="text-amber-400 hover:text-white p-0.5"
            >
              <X className="w-3 h-3" />
            </button>
          </div>
        )}

        {/* Central Luminous Orb (Clickable to start/interrupt anytime!) */}
        <div
          onClick={handleOrbClick}
          className="relative flex items-center justify-center my-2 sm:my-3 cursor-pointer group"
          title="Click to speak / interrupt"
        >
          {callPhase === "listening" && (
            <>
              <div
                className="absolute rounded-full border border-emerald-400/30 transition-all duration-75 pointer-events-none"
                style={{
                  width: `${140 + audioLevel * 1.5}px`,
                  height: `${140 + audioLevel * 1.5}px`,
                  opacity: Math.max(0.2, audioLevel / 100),
                }}
              />
              <div
                className="absolute rounded-full border border-teal-400/20 transition-all duration-150 pointer-events-none"
                style={{
                  width: `${180 + audioLevel * 2.0}px`,
                  height: `${180 + audioLevel * 2.0}px`,
                  opacity: Math.max(0.1, (audioLevel / 100) * 0.7),
                }}
              />
            </>
          )}

          {callPhase === "speaking" && (
            <div className="absolute w-52 h-52 rounded-full border border-cyan-400/40 animate-ping opacity-30 pointer-events-none" />
          )}

          {callPhase === "thinking" && (
            <div className="absolute w-44 h-44 rounded-full border-2 border-t-indigo-400 border-r-transparent border-b-cyan-400 border-l-transparent animate-spin pointer-events-none" />
          )}

          {/* The Glowing Core Sphere */}
          <div
            className={`relative w-32 h-32 sm:w-36 sm:h-36 rounded-full flex items-center justify-center shadow-2xl transition-all duration-500 group-hover:scale-105 active:scale-95 ${
              callPhase === "listening"
                ? "bg-gradient-to-tr from-[#0B6E5F] via-[#10B981] to-[#34D399] shadow-emerald-500/40 scale-105"
                : callPhase === "thinking"
                ? "bg-gradient-to-tr from-[#4338CA] via-[#6366F1] to-[#06B6D4] shadow-indigo-500/40 animate-pulse"
                : callPhase === "speaking"
                ? "bg-gradient-to-tr from-[#0284C7] via-[#0EA5E9] to-[#14B8A6] shadow-cyan-500/50 scale-105"
                : callPhase === "cooldown"
                ? "bg-gradient-to-tr from-teal-700 to-emerald-800 shadow-teal-500/30 scale-100"
                : "bg-gradient-to-tr from-[#0B6E5F] to-[#14B8A6] shadow-emerald-500/40 ring-4 ring-emerald-500/30"
            }`}
          >
            {callPhase === "thinking" ? (
              <Sparkles className="w-10 h-10 text-white animate-spin" />
            ) : callPhase === "speaking" ? (
              <div className="flex items-center gap-1.5 h-10">
                <span className="w-1.5 h-6 bg-white rounded-full animate-bounce" />
                <span className="w-1.5 h-10 bg-white rounded-full animate-bounce [animation-delay:0.15s]" />
                <span className="w-1.5 h-8 bg-white rounded-full animate-bounce [animation-delay:0.3s]" />
                <span className="w-1.5 h-5 bg-white rounded-full animate-bounce [animation-delay:0.45s]" />
              </div>
            ) : callPhase === "cooldown" ? (
              <CheckCircle2 className="w-9 h-9 text-emerald-300 animate-pulse" />
            ) : isMuted ? (
              <MicOff className="w-10 h-10 text-slate-400" />
            ) : callPhase === "idle" ? (
              <div className="flex flex-col items-center justify-center gap-1">
                <Mic className="w-8 h-8 text-white animate-bounce" />
                <span className="text-[10px] text-white font-semibold tracking-wide">Tap to Speak</span>
              </div>
            ) : (
              <Mic
                className={`w-10 h-10 text-white transition-transform ${
                  audioLevel > 15 ? "scale-110" : "scale-100"
                }`}
              />
            )}
          </div>
        </div>

        {/* State Label */}
        <div className="mt-2 mb-2">
          <p
            className={`text-xs sm:text-sm font-semibold tracking-wide transition-colors ${
              callPhase === "listening"
                ? "text-emerald-400"
                : callPhase === "thinking"
                ? "text-indigo-300"
                : callPhase === "speaking"
                ? "text-cyan-300 animate-pulse"
                : callPhase === "cooldown"
                ? "text-teal-300"
                : "text-slate-300"
            }`}
          >
            {callPhase === "listening" && "Listening... speak now or tap orb"}
            {callPhase === "thinking" && "DevMind is checking codebase context..."}
            {callPhase === "speaking" && "DevMind is speaking out loud..."}
            {callPhase === "cooldown" && "Audio finishing... preparing mic for follow-up"}
            {callPhase === "idle" && "Tap Orb to Speak • Real-time Call"}
          </p>
        </div>

        {/* Spoken Subtitle Box */}
        <div className="w-full max-h-52 overflow-y-auto px-4 py-3 rounded-xl bg-white/5 border border-white/10 backdrop-blur-md flex flex-col justify-center space-y-2 text-left shadow-inner">
          {/* User spoken transcript */}
          {userTranscript && (
            <div className="text-xs text-slate-300 flex items-center justify-between gap-2 border-b border-white/5 pb-1.5">
              <div className="flex items-start gap-1.5">
                <span className="text-emerald-400 font-bold shrink-0">You:</span>
                <p className="italic text-slate-200 text-xs">
                  &ldquo;{userTranscript}&rdquo;
                </p>
              </div>
              {/* Quick Send Button */}
              {callPhase === "listening" && (
                <button
                  type="button"
                  onClick={handleManualSend}
                  className="px-2 py-0.5 rounded bg-emerald-500/20 hover:bg-emerald-500/30 text-emerald-300 border border-emerald-500/30 flex items-center gap-1 text-[10px] font-semibold transition-colors cursor-pointer shrink-0"
                  title="Send immediately"
                >
                  <Send className="w-3 h-3" />
                  <span>Send</span>
                </button>
              )}
            </div>
          )}

          {/* DevMind spoken answer */}
          {aiAnswer ? (
            <div className="space-y-1">
              <div className="text-xs text-slate-200 flex items-start justify-between gap-2">
                <div className="flex items-start gap-1.5 flex-1">
                  <span className="text-cyan-400 font-bold shrink-0">DevMind:</span>
                  <p className="leading-relaxed font-sans text-white/95 text-xs">
                    {aiAnswer}
                  </p>
                </div>
                {/* Replay Button */}
                <button
                  type="button"
                  onClick={handleReplayAnswer}
                  className="shrink-0 px-2 py-1 rounded bg-cyan-500/20 hover:bg-cyan-500/30 text-cyan-300 border border-cyan-500/30 flex items-center gap-1 text-[10px] font-medium transition-colors cursor-pointer"
                  title="Replay spoken voice"
                >
                  <Volume2 className="w-3 h-3" />
                  <span>Replay</span>
                </button>
              </div>
            </div>
          ) : !userTranscript ? (
            <p className="text-xs text-slate-400 text-center italic py-2">
              Say something like &ldquo;Explain the project architecture&rdquo; or &ldquo;How is auth handled?&rdquo;
            </p>
          ) : null}

          {/* Referenced Code Files Chips */}
          {citedFiles.length > 0 && (
            <div className="flex items-center gap-1.5 pt-1.5 flex-wrap border-t border-white/5">
              <span className="text-[10px] text-slate-400 flex items-center gap-1">
                <FileCode className="w-3 h-3 text-cyan-400" />
                Referenced:
              </span>
              {citedFiles.map((f) => (
                <span
                  key={f}
                  className="px-1.5 py-0.5 text-[9px] rounded bg-white/10 text-slate-200 font-mono"
                >
                  {f.split("/").pop()}
                </span>
              ))}
            </div>
          )}
        </div>

        {/* Quick Voice Prompt Buttons */}
        <div className="w-full mt-3 flex flex-wrap items-center justify-center gap-1.5">
          {quickPrompts.map((prompt) => (
            <button
              key={prompt}
              type="button"
              onClick={() => {
                unlockMobileAudio();
                submitVoiceQuery(prompt);
              }}
              disabled={callPhase === "thinking"}
              className="px-2.5 py-1 text-[11px] font-medium rounded-lg bg-white/5 hover:bg-white/15 border border-white/10 text-slate-300 hover:text-white transition-all cursor-pointer disabled:opacity-50"
            >
              {prompt}
            </button>
          ))}
        </div>
      </main>

      {/* BOTTOM CONTROL DOCK (Always 100% visible, fully above the taskbar!) */}
      <footer className="shrink-0 relative z-20 w-full max-w-md mx-auto px-4 py-2.5 flex flex-col items-center gap-1.5 border-t border-white/5 bg-[#070A10]/90 backdrop-blur-md">
        <div className="flex items-center gap-4">
          {/* Mute / Unmute Toggle */}
          <button
            type="button"
            onClick={handleToggleMute}
            className={`w-11 h-11 rounded-xl flex items-center justify-center transition-all cursor-pointer shadow-md ${
              isMuted
                ? "bg-rose-500/20 text-rose-400 border border-rose-500/40 hover:bg-rose-500/30"
                : "bg-white/10 text-white border border-white/15 hover:bg-white/20"
            }`}
            title={isMuted ? "Unmute microphone" : "Mute microphone"}
          >
            {isMuted ? <MicOff className="w-5 h-5" /> : <Mic className="w-5 h-5" />}
          </button>

          {/* User Interrupt Button (active when DevMind is speaking) */}
          {callPhase === "speaking" && (
            <button
              type="button"
              onClick={handleInterrupt}
              className="px-3 h-11 rounded-xl bg-amber-500/20 text-amber-300 border border-amber-500/40 hover:bg-amber-500/30 flex items-center gap-1.5 text-xs font-semibold transition-all cursor-pointer shadow-md animate-pulse"
              title="Stop DevMind from speaking and speak now"
            >
              <RotateCcw className="w-4 h-4" />
              <span>Interrupt / Ask</span>
            </button>
          )}

          {/* End Call Button */}
          <button
            type="button"
            onClick={onClose}
            className="w-11 h-11 rounded-xl bg-rose-600 hover:bg-rose-700 text-white flex items-center justify-center transition-all cursor-pointer shadow-md shadow-rose-600/30 hover:scale-105"
            title="End voice call"
          >
            <PhoneOff className="w-5 h-5" />
          </button>
        </div>

        <p className="text-[10px] text-slate-500">
          Hands-free continuous call • Tap orb anytime to speak • Follow-up enabled
        </p>
      </footer>
    </div>
  );
};
