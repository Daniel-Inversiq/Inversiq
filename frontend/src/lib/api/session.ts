import { apiRequestSameOrigin, apiUrl } from "@/lib/api/client";
import { APP_ROUTES } from "@/lib/routes";
import { SessionUser } from "@/types/session";

export function fetchSessionUser() {
  return apiRequestSameOrigin<SessionUser>("/api/auth/me");
}

type LoginPayload = {
  email: string;
  password: string;
  next?: string;
};

type RegisterPayload = {
  company_name?: string;
  email: string;
  phone?: string;
  password: string;
};

export function login(payload: LoginPayload) {
  return apiRequestSameOrigin<SessionUser & { next?: string }>("/api/auth/login", {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

export function register(payload: RegisterPayload) {
  return apiRequestSameOrigin<SessionUser & { next?: string }>("/api/auth/register", {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

export function logout() {
  return apiRequestSameOrigin<{ ok: boolean }>("/api/auth/logout", {
    method: "POST",
    body: JSON.stringify({}),
  });
}

function sanitizeNextPath(nextPath: string): string {
  const fallback = APP_ROUTES.dashboard;
  const trimmed = nextPath.trim();

  if (!trimmed.startsWith("/")) {
    return fallback;
  }

  // Prevent protocol-relative and absolute URLs.
  if (trimmed.startsWith("//")) {
    return fallback;
  }

  try {
    const parsed = new URL(trimmed, "https://inversiq.local");
    if (parsed.origin !== "https://inversiq.local") {
      return fallback;
    }
    return `${parsed.pathname}${parsed.search}${parsed.hash}`;
  } catch {
    return fallback;
  }
}

export function getGoogleAuthStartUrl(nextPath: string = APP_ROUTES.dashboard) {
  const safeNextPath = sanitizeNextPath(nextPath);
  const params = new URLSearchParams({ next: safeNextPath });
  return `${apiUrl("/auth/google/start")}?${params.toString()}`;
}
