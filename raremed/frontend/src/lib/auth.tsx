"use client";

import { createContext, useCallback, useContext, useEffect, useMemo, useState, type ReactNode } from "react";

import { ApiError, getMe, loginAccount, logoutAccount, registerAccount } from "@/lib/api";
import type { SessionUser } from "@/lib/types";

type AuthContextValue = {
  user: SessionUser | null;
  loading: boolean;
  errorCode: string | null;
  refresh: () => Promise<SessionUser | null>;
  login: (email: string, password: string) => Promise<SessionUser>;
  register: (email: string, password: string, displayName?: string) => Promise<SessionUser>;
  logout: () => Promise<void>;
};

const AuthContext = createContext<AuthContextValue | null>(null);

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<SessionUser | null>(null);
  const [loading, setLoading] = useState(true);
  const [errorCode, setErrorCode] = useState<string | null>(null);

  const refresh = useCallback(async () => {
    try {
      const next = await getMe();
      setUser(next);
      setErrorCode(null);
      return next;
    } catch (error) {
      setUser(null);
      if (error instanceof ApiError && error.code !== "unauthenticated") {
        setErrorCode(error.code);
      }
      return null;
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    let cancelled = false;
    getMe()
      .then((next) => {
        if (cancelled) return;
        setUser(next);
        setErrorCode(null);
      })
      .catch((error: unknown) => {
        if (cancelled) return;
        setUser(null);
        if (error instanceof ApiError && error.code !== "unauthenticated") {
          setErrorCode(error.code);
        }
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, []);

  const value = useMemo<AuthContextValue>(
    () => ({
      user,
      loading,
      errorCode,
      refresh,
      login: async (email, password) => {
        const next = (await loginAccount(email, password)).user;
        setUser(next);
        setErrorCode(null);
        return next;
      },
      register: async (email, password, displayName) => {
        const next = (await registerAccount(email, password, displayName)).user;
        setUser(next);
        setErrorCode(null);
        return next;
      },
      logout: async () => {
        await logoutAccount().catch(() => undefined);
        setUser(null);
      },
    }),
    [errorCode, loading, refresh, user],
  );

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useOptionalAuth() {
  return useContext(AuthContext);
}

export function useAuth() {
  const value = useOptionalAuth();
  if (!value) {
    throw new Error("useAuth must be used within AuthProvider");
  }
  return value;
}
