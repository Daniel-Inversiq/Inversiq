import { apiRequest } from "@/lib/api/client";
import { getApiBaseUrl } from "@/lib/api/client";
import { APP_ROUTES } from "@/lib/routes";
import { SessionUser } from "@/types/session";

export function fetchSessionUser() {
  return apiRequest<SessionUser>("/auth/me");
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
  return apiRequest<SessionUser & { next?: string }>("/auth/login", {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

export function register(payload: RegisterPayload) {
  return apiRequest<SessionUser & { next?: string }>("/auth/register", {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

export function logout() {
  return apiRequest<{ ok: boolean }>("/auth/logout", {
    method: "POST",
    body: JSON.stringify({}),
  });
}

export function getGoogleAuthStartUrl(nextPath = APP_ROUTES.dashboard) {
  const params = new URLSearchParams({ next: nextPath });
  return `${getApiBaseUrl()}/auth/google/start?${params.toString()}`;
}
