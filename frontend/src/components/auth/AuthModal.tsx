"use client";

import React, { useState } from "react";
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

  if (!isOpen) return null;

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

  const handleGoogleAuth = async () => {
    try {
      setLoading(true);
      setError(null);
      await loginWithGoogle();
      if (onSuccess) onSuccess();
      onClose();
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : "Google login failed");
    } finally {
      setLoading(false);
    }
  };

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
          <div className="grid grid-cols-2 gap-2">
            <button
              type="button"
              onClick={handleGoogleAuth}
              disabled={loading}
              className="flex items-center justify-center gap-2 py-2 px-3 rounded-xl border border-[#D0CFC8] bg-white hover:bg-[#FAF9F6] text-[#1C2024] font-medium text-xs transition-all shadow-sm active:scale-[0.99] disabled:opacity-50"
            >
              <svg className="w-3.5 h-3.5 shrink-0" viewBox="0 0 24 24">
                <path
                  fill="#4285F4"
                  d="M22.56 12.25c0-.78-.07-1.53-.2-2.25H12v4.26h5.92c-.26 1.37-1.04 2.53-2.21 3.31v2.77h3.57c2.08-1.92 3.28-4.74 3.28-8.09z"
                />
                <path
                  fill="#34A853"
                  d="M12 23c2.97 0 5.46-.98 7.28-2.66l-3.57-2.77c-.98.66-2.23 1.06-3.71 1.06-2.86 0-5.29-1.93-6.16-4.53H2.18v2.84C3.99 20.53 7.7 23 12 23z"
                />
                <path
                  fill="#FBBC05"
                  d="M5.84 14.09c-.22-.66-.35-1.36-.35-2.09s.13-1.43.35-2.09V7.06H2.18C1.43 8.55 1 10.22 1 12s.43 3.45 1.18 4.94l2.85-2.22.81-.63z"
                />
                <path
                  fill="#EA4335"
                  d="M12 5.38c1.62 0 3.06.56 4.21 1.64l3.15-3.15C17.45 2.09 14.97 1 12 1 7.7 1 3.99 3.47 2.18 7.06l3.66 2.84c.87-2.6 3.3-4.52 6.16-4.52z"
                />
              </svg>
              <span>Google</span>
            </button>

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
