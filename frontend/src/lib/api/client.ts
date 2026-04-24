import { logDashboardApiRequest } from "@/lib/api/request-timing";

const API_BASE_URL =
  process.env.NEXT_PUBLIC_API_BASE_URL?.replace(/\/$/, "") ?? "";

export function apiUrl(path: string): string {
  if (!path) {
    return API_BASE_URL;
  }
  const normalizedPath = path.startsWith("/") ? path : `/${path}`;
  return `${API_BASE_URL}${normalizedPath}`;
}

/** Prevents hung backend calls from keeping React Query in `isLoading` forever. */
const DEFAULT_REQUEST_TIMEOUT_MS = 45_000;

function getTimeoutAbortSignal(ms: number): AbortSignal {
  if (typeof AbortSignal !== "undefined" && typeof AbortSignal.timeout === "function") {
    return AbortSignal.timeout(ms);
  }
  const controller = new AbortController();
  globalThis.setTimeout(() => controller.abort(), ms);
  return controller.signal;
}

function isAbortError(error: unknown): boolean {
  if (!error || typeof error !== "object") {
    return false;
  }
  const name = (error as { name?: string }).name;
  return name === "AbortError";
}

type ApiDebugSnapshot = {
  url: string;
  method: string;
  status: number;
  ok: boolean;
  at: string;
  payloadPreview: string;
};

let lastApiDebugSnapshot: ApiDebugSnapshot | null = null;

export class ApiError extends Error {
  status: number;
  code?: string;

  constructor(message: string, status: number, code?: string) {
    super(message);
    this.name = "ApiError";
    this.status = status;
    this.code = code;
  }
}

type RequestOptions = RequestInit & {
  headers?: HeadersInit;
};

function toPreview(payload: unknown): string {
  if (payload === undefined || payload === null) {
    return "";
  }

  if (typeof payload === "string") {
    return payload.slice(0, 600);
  }

  try {
    return JSON.stringify(payload).slice(0, 600);
  } catch {
    return String(payload).slice(0, 600);
  }
}

function setLastApiDebugSnapshot(snapshot: ApiDebugSnapshot) {
  lastApiDebugSnapshot = snapshot;
}

export function getLastApiDebugSnapshot() {
  return lastApiDebugSnapshot;
}

export function getApiBaseUrl() {
  return API_BASE_URL;
}

/**
 * True when the shell is served from a loopback host (typical local Next dev).
 * Used only to allow same-origin fallback when NEXT_PUBLIC_API_BASE_URL is unset.
 */
function isLoopbackHostname(hostname: string): boolean {
  const h = hostname.trim().toLowerCase();
  return h === "localhost" || h === "127.0.0.1" || h === "::1" || h.endsWith(".localhost");
}

/**
 * Public FastAPI origin for browser links (intake HTML, etc.).
 * - Prefer `NEXT_PUBLIC_API_BASE_URL` (no trailing slash; same as API client).
 * - If unset, use `window.location.origin` only on loopback — local same-origin dev
 *   when the shell and API share one origin or you proxy under that origin.
 * - Otherwise empty (callers should treat as “base not configured”).
 */
export function getPublicBackendBaseUrl(): string {
  if (API_BASE_URL) {
    return API_BASE_URL;
  }
  if (typeof window !== "undefined" && isLoopbackHostname(window.location.hostname)) {
    return window.location.origin;
  }
  return "";
}

/** Absolute public intake URL for a tenant (`GET /t/{tenant_id}/intake` on FastAPI). */
export function buildTenantIntakeUrl(tenantId: string): string {
  const path = `/t/${tenantId}/intake`;
  const absoluteUrl = apiUrl(path);
  return absoluteUrl || path;
}

export async function apiRequest<T>(
  path: string,
  options: RequestOptions = {},
): Promise<T> {
  const url = apiUrl(path);
  const method = (options.method ?? "GET").toUpperCase();
  const startedAt = Date.now();
  logDashboardApiRequest("start", { method, path, durationMs: 0 });
  let response: Response;

  const timeoutSignal = getTimeoutAbortSignal(DEFAULT_REQUEST_TIMEOUT_MS);
  const mergedSignal =
    typeof AbortSignal !== "undefined" && typeof AbortSignal.any === "function" && options.signal
      ? AbortSignal.any([options.signal, timeoutSignal])
      : timeoutSignal;

  try {
    response = await fetch(url, {
      ...options,
      signal: mergedSignal,
      credentials: "include",
      headers: {
        "Content-Type": "application/json",
        Accept: "application/json",
        ...options.headers,
      },
      cache: "no-store",
    });
  } catch (error) {
    const durationMs = Date.now() - startedAt;
    setLastApiDebugSnapshot({
      url,
      method,
      status: 0,
      ok: false,
      at: new Date().toISOString(),
      payloadPreview: error instanceof Error ? error.message : "Network error",
    });
    if (isAbortError(error)) {
      logDashboardApiRequest("timeout", {
        method,
        path,
        durationMs,
        detail: `limit=${DEFAULT_REQUEST_TIMEOUT_MS}ms`,
      });
      throw new ApiError("Request timed out", 0, "TIMEOUT");
    }
    logDashboardApiRequest("network_error", {
      method,
      path,
      durationMs,
      detail: error instanceof Error ? error.message : "unknown",
    });
    throw new ApiError("Backend is unreachable", 0, "NETWORK_ERROR");
  }

  if (!response.ok) {
    let message = `Request failed with status ${response.status}`;
    const rawBody = await response.text();
    let payloadPreview = rawBody;

    if (rawBody) {
      try {
        const payload = JSON.parse(rawBody) as { detail?: string };
        payloadPreview = toPreview(payload);
        if (payload.detail) {
          message = payload.detail;
        }
      } catch {
        payloadPreview = rawBody;
      }
    }

    setLastApiDebugSnapshot({
      url,
      method,
      status: response.status,
      ok: false,
      at: new Date().toISOString(),
      payloadPreview: toPreview(payloadPreview || message),
    });
    logDashboardApiRequest("http_error", {
      method,
      path,
      durationMs: Date.now() - startedAt,
      status: response.status,
    });
    throw new ApiError(message, response.status);
  }

  const payload = (await response.json()) as T;
  setLastApiDebugSnapshot({
    url,
    method,
    status: response.status,
    ok: true,
    at: new Date().toISOString(),
    payloadPreview: toPreview(payload),
  });

  logDashboardApiRequest("success", {
    method,
    path,
    durationMs: Date.now() - startedAt,
    status: response.status,
  });

  return payload;
}
