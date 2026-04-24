"use client";

import { createContext, ReactNode, useContext, useMemo } from "react";
import { useSessionUser } from "@/hooks/use-session-user";
import { SessionUser } from "@/types/session";

type SessionContextValue = {
  user: SessionUser | null;
  isLoading: boolean;
  isAuthenticated: boolean;
  error: unknown;
};

const SessionContext = createContext<SessionContextValue | null>(null);

type SessionProviderProps = {
  children: ReactNode;
};

export function SessionProvider({ children }: SessionProviderProps) {
  const sessionQuery = useSessionUser();
  const value = useMemo<SessionContextValue>(
    () => ({
      user: sessionQuery.data ?? null,
      isLoading: sessionQuery.isLoading,
      isAuthenticated: Boolean(sessionQuery.data),
      error: sessionQuery.error,
    }),
    [sessionQuery.data, sessionQuery.error, sessionQuery.isLoading],
  );

  return (
    <SessionContext.Provider value={value}>{children}</SessionContext.Provider>
  );
}

export function useSessionContext() {
  const context = useContext(SessionContext);
  if (!context) {
    throw new Error("useSessionContext must be used within SessionProvider");
  }
  return context;
}
