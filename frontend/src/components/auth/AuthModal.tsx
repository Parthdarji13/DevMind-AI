"use client";

import React, { useState, useEffect, useRef } from "react";
import {
  X,
  Sparkles,
  Lock,
  Mail,
  User as UserIcon,
  AlertCircle,
  ArrowRight,
  Shield,
  Loader2,
} from "lucide-react";

import {
  signInWithEmail,
  signUpWithEmail,
  loginWithGoogle,
  loginAsGuest,
} from "@/lib/auth";

declare global {
  interface Window {
    google?: {
      accounts: {
        id: {
          initialize: (config: {
            client_id: string;
            callback: (response: { credential?: string }) => void;
            auto_select?: boolean;
            cancel_on_tap_outside?: boolean;
          }) => void;
          prompt: (momentListener?: (notification: unknown) => void) => void;
          renderButton: (
            parent: HTMLElement,
            options: {
              type?: "standard" | "icon";
              theme?: "outline" | "filled_blue" | "filled_black";
              size?: "large" | "medium" | "small";
              text?: "signin_with" | "signup_with" | "continue_with" | "signin";
              shape?: "rectangular" | "pill" | "circle" | "square";
              logo_alignment?: "left" | "center";
              width?: string | number;
              locale?: string;
            }
          ) => void;
        };
      };
    };
  }
}

interface AuthModalProps {
  isOpen: boolean;
  onClose: () => void;
  onSuccess?: () => void;
  initialMode?: "signin" | "signup";
}

export const AuthModal: React.FC<AuthModalProps> = ({
  isOpen,
  onClose,
  onSuccess,
  initialMode = "signin",
}) => {
  const [mode, setMode] = useState<"signin" | "signup">(initialMode);
  const [name, setName] = useState("");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [confirmPassword, setConfirmPassword] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const googleBtnContainerRef = useRef<HTMLDivElement>(null);
  const googleClientId = process.env.NEXT_PUBLIC_GOOGLE_CLIENT_ID || "";
  const isGoogleConfigured = Boolean(
    googleClientId && !googleClientId.startsWith("your_")
  );

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);

    if (mode === "signup") {
      if (!name.trim()) {
        setError("Please enter your name.");
        return;
      }
      if (!email.trim() || !email.includes("@")) {
        setError("Please enter a valid email address.");
        return;
      }
      if (password.length < 6) {
        setError("Password must be at least 6 characters long.");
        return;
      }
      if (password !== confirmPassword) {
        setError("Passwords do not match.");
        return;
      }

      try {
        setLoading(true);
        await signUpWithEmail(name.trim(), email.trim(), password);
        if (onSuccess) onSuccess();
        onClose();
      } catch (err: unknown) {
        setError(err instanceof Error ? err.message : "Sign up failed");
      } finally {
        setLoading(false);
      }
    } else {
      // Sign In
      if (!email.trim()) {
        setError("Please enter your email.");
        return;
      }
      if (!password) {
        setError("Please enter your password.");
        return;
      }

      try {
        setLoading(true);
        await signInWithEmail(email.trim(), password);
        if (onSuccess) onSuccess();
        onClose();
      } catch (err: unknown) {
        setError(err instanceof Error ? err.message : "Invalid email or password");
      } finally {
        setLoading(false);
      }
    }
  };

  useEffect(() => {
    if (!isOpen || !isGoogleConfigured) return;

    let isSubscribed = true;

    const setupGoogle = () => {
      if (!isSubscribed) return;
      if (typeof window === "undefined" || !window.google?.accounts?.id) return;

      try {
        window.google.accounts.id.initialize({
          client_id: googleClientId,
          callback: async (response: { credential?: string }) => {
            if (!response.credential) {
              setError("Google sign-in did not return a valid credential token.");
              return;
            }
            try {
              setLoading(true);
              setError(null);
              await loginWithGoogle(response.credential);
              if (onSuccess) onSuccess();
              onClose();
            } catch (err: unknown) {
              setError(
                err instanceof Error ? err.message : "Google authentication failed"
              );
            } finally {
              setLoading(false);
            }
          },
        });

        if (googleBtnContainerRef.current) {
          googleBtnContainerRef.current.innerHTML = "";
          window.google.accounts.id.renderButton(googleBtnContainerRef.current, {
            type: "standard",
            theme: "outline",
            size: "large",
            text: "continue_with",
            shape: "rectangular",
            logo_alignment: "left",
            width: 175,
          });
        }
      } catch (err) {
        console.warn("Failed to initialize Google Identity Services:", err);
      }
    };

    if (window.google?.accounts?.id) {
      setupGoogle();
    } else {
      const interval = setInterval(() => {
        if (window.google?.accounts?.id) {
          clearInterval(interval);
          setupGoogle();
        }
      }, 250);
      return () => {
        isSubscribed = false;
        clearInterval(interval);
      };
    }

    return () => {
      isSubscribed = false;
    };
  }, [isOpen, isGoogleConfigured, googleClientId, onSuccess, onClose]);

  const handleGuestAuth = async () => {
    try {
      setLoading(true);
      setError(null);
      await loginAsGuest();
      if (onSuccess) onSuccess();
      onClose();
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : "Guest login failed");
    } finally {
      setLoading(false);
    }
  };

  if (!isOpen) return null;

  return (
    <div className="fixed inset-0 bg-black/60 backdrop-blur-sm z-50 flex items-center justify-center p-4 animate-in fade-in duration-200">
      <div className="bg-white rounded-2xl max-w-md w-full shadow-2xl border border-[#E5E2DB] overflow-hidden animate-in zoom-in-95 duration-150">
        {/* Top Header */}
        <div className="px-6 pt-5 pb-4 flex items-center justify-between border-b border-[#F0EFEA]">
          <div className="flex items-center gap-2.5">
            <div className="w-8 h-8 rounded-lg bg-[#0B6E5F] text-white flex items-center justify-center font-bold text-xs shadow-sm">
              DM
            </div>
            <div>
              <h3 className="font-semibold text-[#1C2024] text-base">
                {mode === "signin" ? "Welcome Back" : "Create Account"}
              </h3>
              <p className="text-xs text-[#636A74]">
                {mode === "signin"
                  ? "Sign in to access your indexed repositories"
                  : "Sign up for private codebase intelligence"}
              </p>
            </div>
          </div>
          <button
            onClick={onClose}
            className="w-8 h-8 rounded-lg text-[#636A74] hover:text-[#1C2024] hover:bg-[#F0EFEA] flex items-center justify-center transition-colors"
          >
            <X className="w-4 h-4" />
          </button>
        </div>

        {/* Tab Switcher */}
        <div className="p-1.5 mx-6 mt-4 bg-[#F7F6F3] rounded-xl flex items-center border border-[#EBE8E1]">
          <button
            type="button"
            onClick={() => {
              setMode("signin");
              setError(null);
            }}
            className={`flex-1 py-1.5 text-xs font-semibold rounded-lg transition-all ${
              mode === "signin"
                ? "bg-white text-[#1C2024] shadow-sm"
                : "text-[#636A74] hover:text-[#1C2024]"
            }`}
          >
            Sign In
          </button>
          <button
            type="button"
            onClick={() => {
              setMode("signup");
              setError(null);
            }}
            className={`flex-1 py-1.5 text-xs font-semibold rounded-lg transition-all ${
              mode === "signup"
                ? "bg-white text-[#1C2024] shadow-sm"
                : "text-[#636A74] hover:text-[#1C2024]"
            }`}
          >
            Sign Up
          </button>
        </div>

        {/* Body Content */}
        <div className="p-6 space-y-4">
          {error && (
            <div className="p-3 rounded-xl bg-rose-50 border border-rose-200 flex items-start gap-2 text-xs text-rose-700 animate-in fade-in duration-150">
              <AlertCircle className="w-4 h-4 mt-0.5 shrink-0" />
              <span>{error}</span>
            </div>
          )}

          {/* Form */}
          <form onSubmit={handleSubmit} className="space-y-3">
            {mode === "signup" && (
              <div>
                <label className="block text-xs font-medium text-[#484F58] mb-1">
                  Full Name
                </label>
                <div className="relative">
                  <UserIcon className="w-4 h-4 text-[#8C877D] absolute left-3 top-2.5" />
                  <input
                    type="text"
                    required
                    placeholder="e.g. Parth Darji"
                    value={name}
                    onChange={(e) => setName(e.target.value)}
                    className="w-full pl-9 pr-3 py-2 text-xs rounded-xl border border-[#D0CFC8] bg-[#FAF9F6] focus:bg-white focus:outline-none focus:ring-2 focus:ring-[#0B6E5F] transition-all"
                  />
                </div>
              </div>
            )}

            <div>
              <label className="block text-xs font-medium text-[#484F58] mb-1">
                Email Address
              </label>
              <div className="relative">
                <Mail className="w-4 h-4 text-[#8C877D] absolute left-3 top-2.5" />
                <input
                  type="email"
                  required
                  placeholder="developer@example.com"
                  value={email}
                  onChange={(e) => setEmail(e.target.value)}
                  className="w-full pl-9 pr-3 py-2 text-xs rounded-xl border border-[#D0CFC8] bg-[#FAF9F6] focus:bg-white focus:outline-none focus:ring-2 focus:ring-[#0B6E5F] transition-all"
                />
              </div>
            </div>

            <div>
              <label className="block text-xs font-medium text-[#484F58] mb-1">
                Password
              </label>
              <div className="relative">
                <Lock className="w-4 h-4 text-[#8C877D] absolute left-3 top-2.5" />
                <input
                  type="password"
                  required
                  placeholder="••••••••"
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                  className="w-full pl-9 pr-3 py-2 text-xs rounded-xl border border-[#D0CFC8] bg-[#FAF9F6] focus:bg-white focus:outline-none focus:ring-2 focus:ring-[#0B6E5F] transition-all"
                />
              </div>
            </div>

            {mode === "signup" && (
              <div>
                <label className="block text-xs font-medium text-[#484F58] mb-1">
                  Confirm Password
                </label>
                <div className="relative">
                  <Lock className="w-4 h-4 text-[#8C877D] absolute left-3 top-2.5" />
                  <input
                    type="password"
                    required
                    placeholder="••••••••"
                    value={confirmPassword}
                    onChange={(e) => setConfirmPassword(e.target.value)}
                    className="w-full pl-9 pr-3 py-2 text-xs rounded-xl border border-[#D0CFC8] bg-[#FAF9F6] focus:bg-white focus:outline-none focus:ring-2 focus:ring-[#0B6E5F] transition-all"
                  />
                </div>
              </div>
            )}

            <button
              type="submit"
              disabled={loading}
              className="w-full mt-2 py-2.5 px-4 bg-[#0B6E5F] hover:bg-[#09584C] text-white text-xs font-semibold rounded-xl transition-all shadow-sm active:scale-[0.99] disabled:opacity-50 flex items-center justify-center gap-1.5"
            >
              {loading ? (
                <Loader2 className="w-4 h-4 animate-spin" />
              ) : (
                <>
                  <span>{mode === "signin" ? "Sign In" : "Create Account"}</span>
                  <ArrowRight className="w-3.5 h-3.5" />
                </>
              )}
            </button>
          </form>

          {/* Divider */}
          <div className="relative flex items-center justify-center pt-1">
            <div className="border-t border-[#E5E2DB] w-full"></div>
            <span className="bg-white px-2.5 text-[11px] font-medium text-[#8C877D] uppercase tracking-wider">
              Or Fast Access
            </span>
          </div>

          {/* Social / 1-Click Options (NO TOKEN PROMPTS!) */}
          {isGoogleConfigured ? (
            <div className="grid grid-cols-2 gap-2">
              <div className="relative flex items-center justify-center min-h-[38px] rounded-xl overflow-hidden border border-[#D0CFC8] bg-white">
                <div
                  ref={googleBtnContainerRef}
                  className="w-full flex items-center justify-center scale-95"
                />
              </div>
              <button
                type="button"
                onClick={handleGuestAuth}
                disabled={loading}
                className="flex items-center justify-center gap-1.5 py-2 px-3 rounded-xl border border-[#D0CFC8] bg-[#F7F6F3] hover:bg-[#F0EFEA] text-[#1C2024] font-medium text-xs transition-all shadow-sm active:scale-[0.99] disabled:opacity-50"
              >
                <Sparkles className="w-3.5 h-3.5 text-[#0B6E5F]" />
                <span>Guest Dev</span>
              </button>
            </div>
          ) : (
            <button
              type="button"
              onClick={handleGuestAuth}
              disabled={loading}
              className="w-full flex items-center justify-center gap-2 py-2.5 px-4 rounded-xl border border-[#D0CFC8] bg-[#F7F6F3] hover:bg-[#F0EFEA] text-[#1C2024] font-medium text-xs transition-all shadow-sm active:scale-[0.99] disabled:opacity-50"
            >
              <Sparkles className="w-4 h-4 text-[#0B6E5F]" />
              <span>Continue as Guest Dev (1-Click Instant Access)</span>
            </button>
          )}

          {/* Privacy Guarantee Note */}
          <div className="p-3 rounded-xl bg-[#FAF9F6] border border-[#EBE8E1] flex items-center gap-2 text-[11px] text-[#636A74]">
            <Shield className="w-4 h-4 text-[#0B6E5F] shrink-0" />
            <span>All code repositories are isolated to your authenticated account.</span>
          </div>
        </div>
      </div>
    </div>
  );
};
