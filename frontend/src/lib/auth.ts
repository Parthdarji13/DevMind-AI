"use client";

import { useSyncExternalStore } from "react";
import { User, AuthResponse } from "./types";

const TOKEN_KEY = "devmind_auth_token";
const USER_KEY = "devmind_auth_user";
const AUTH_CHANGE_EVENT = "devmind_auth_changed";

let cachedUserRaw: string | null = null;
let cachedUser: User | null = null;

export function getStoredToken(): string | null {
  if (typeof window === "undefined") return null;
  return localStorage.getItem(TOKEN_KEY);
}

export function getStoredUser(): User | null {
  if (typeof window === "undefined") return null;
  const raw = localStorage.getItem(USER_KEY);
  if (!raw) {
    cachedUserRaw = null;
    cachedUser = null;
    return null;
  }
  if (raw === cachedUserRaw) {
    return cachedUser;
  }
  try {
    cachedUser = JSON.parse(raw) as User;
    cachedUserRaw = raw;
    return cachedUser;
  } catch {
    cachedUser = null;
    cachedUserRaw = null;
    return null;
  }
}

export function setAuth(token: string, user: User) {
  if (typeof window === "undefined") return;
  const raw = JSON.stringify(user);
  localStorage.setItem(TOKEN_KEY, token);
  localStorage.setItem(USER_KEY, raw);
  cachedUser = user;
  cachedUserRaw = raw;
  window.dispatchEvent(new Event(AUTH_CHANGE_EVENT));
}

export function clearAuth() {
  if (typeof window === "undefined") return;
  localStorage.removeItem(TOKEN_KEY);
  localStorage.removeItem(USER_KEY);
  cachedUser = null;
  cachedUserRaw = null;
  window.dispatchEvent(new Event(AUTH_CHANGE_EVENT));
}

export async function loginAsGuest(sessionId?: string): Promise<User> {
  const backendUrl = process.env.NEXT_PUBLIC_API_URL || "http://127.0.0.1:8000";
  const res = await fetch(`${backendUrl}/api/auth/guest`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ session_id: sessionId || null }),
  });

  if (!res.ok) {
    throw new Error(`Guest login failed with status ${res.status}`);
  }

  const data: AuthResponse = await res.json();
  setAuth(data.access_token, data.user);
  return data.user;
}

export async function signUpWithEmail(name: string, email: string, password: string): Promise<User> {
  const backendUrl = process.env.NEXT_PUBLIC_API_URL || "http://127.0.0.1:8000";
  const res = await fetch(`${backendUrl}/api/auth/signup`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ name, email, password }),
  });

  if (!res.ok) {
    let errorDetail = "Sign up failed";
    try {
      const errJson = await res.json();
      errorDetail = errJson.detail || errorDetail;
    } catch {
      errorDetail = `Server returned status ${res.status}`;
    }
    throw new Error(errorDetail);
  }

  const data: AuthResponse = await res.json();
  setAuth(data.access_token, data.user);
  return data.user;
}

export async function signInWithEmail(email: string, password: string): Promise<User> {
  const backendUrl = process.env.NEXT_PUBLIC_API_URL || "http://127.0.0.1:8000";
  const res = await fetch(`${backendUrl}/api/auth/signin`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ email, password }),
  });

  if (!res.ok) {
    let errorDetail = "Invalid credentials";
    try {
      const errJson = await res.json();
      errorDetail = errJson.detail || errorDetail;
    } catch {
      errorDetail = `Server returned status ${res.status}`;
    }
    throw new Error(errorDetail);
  }

  const data: AuthResponse = await res.json();
  setAuth(data.access_token, data.user);
  return data.user;
}

export async function loginWithGoogle(credential: string): Promise<User> {
  const cleanCredential = (credential || "").trim();
  if (!cleanCredential) {
    throw new Error("Google credential token is required.");
  }

  const backendUrl = process.env.NEXT_PUBLIC_API_URL || "http://127.0.0.1:8000";
  const res = await fetch(`${backendUrl}/api/auth/google`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ credential: cleanCredential }),
  });

  if (!res.ok) {
    let errorDetail = "Google login failed";
    try {
      const errJson = await res.json();
      errorDetail = errJson.detail || errorDetail;
    } catch {
      errorDetail = `Server returned status ${res.status}`;
    }
    throw new Error(errorDetail);
  }

  const data: AuthResponse = await res.json();
  setAuth(data.access_token, data.user);
  return data.user;
}


function subscribeAuth(callback: () => void): () => void {
  if (typeof window === "undefined") return () => {};
  window.addEventListener(AUTH_CHANGE_EVENT, callback);
  window.addEventListener("storage", callback);
  return () => {
    window.removeEventListener(AUTH_CHANGE_EVENT, callback);
    window.removeEventListener("storage", callback);
  };
}

const getServerSnapshotNull = () => null;

export function useAuth() {
  const user = useSyncExternalStore(
    subscribeAuth,
    getStoredUser,
    getServerSnapshotNull
  );
  const token = useSyncExternalStore(
    subscribeAuth,
    getStoredToken,
    getServerSnapshotNull
  );

  const logout = () => {
    clearAuth();
  };

  return {
    user,
    token,
    isLoading: false,
    isAuthenticated: Boolean(user),
    logout,
  };
}
