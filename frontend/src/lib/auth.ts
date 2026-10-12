"use client";

import { useState, useEffect } from "react";
import { User, AuthResponse } from "./types";

const TOKEN_KEY = "devmind_auth_token";
const USER_KEY = "devmind_auth_user";
const AUTH_CHANGE_EVENT = "devmind_auth_changed";

export function getStoredToken(): string | null {
  if (typeof window === "undefined") return null;
  return localStorage.getItem(TOKEN_KEY);
}

export function getStoredUser(): User | null {
  if (typeof window === "undefined") return null;
  const raw = localStorage.getItem(USER_KEY);
  if (!raw) return null;
  try {
    return JSON.parse(raw) as User;
  } catch {
    return null;
  }
}

export function setAuth(token: string, user: User) {
  if (typeof window === "undefined") return;
  localStorage.setItem(TOKEN_KEY, token);
  localStorage.setItem(USER_KEY, JSON.stringify(user));
  window.dispatchEvent(new Event(AUTH_CHANGE_EVENT));
}

export function clearAuth() {
  if (typeof window === "undefined") return;
  localStorage.removeItem(TOKEN_KEY);
  localStorage.removeItem(USER_KEY);
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

export async function loginWithGoogle(email?: string, name?: string): Promise<User> {
  const backendUrl = process.env.NEXT_PUBLIC_API_URL || "http://127.0.0.1:8000";
  const res = await fetch(`${backendUrl}/api/auth/google`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      email: email || "developer@gmail.com",
      name: name || "Google Developer",
    }),
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


export function useAuth() {
  const [user, setUser] = useState<User | null>(() => getStoredUser());
  const [token, setToken] = useState<string | null>(() => getStoredToken());


  useEffect(() => {
    // Listen for auth state changes
    const handler = () => {
      setToken(getStoredToken());
      setUser(getStoredUser());
    };

    window.addEventListener(AUTH_CHANGE_EVENT, handler);
    window.addEventListener("storage", handler);
    return () => {
      window.removeEventListener(AUTH_CHANGE_EVENT, handler);
      window.removeEventListener("storage", handler);
    };
  }, []);


  const logout = () => {
    clearAuth();
    setUser(null);
    setToken(null);
  };

  return {
    user,
    token,
    isLoading: false,
    isAuthenticated: Boolean(user),
    logout,
  };

}
