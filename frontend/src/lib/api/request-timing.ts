/**
 * Opt-in timing logs for dashboard-related API traffic.
 * Enable: NEXT_PUBLIC_DEBUG_DASHBOARD_API_TIMING=true (restart dev server).
 *
 * Reading logs (paths are relative to API base URL):
 * - GET /app/me              → session query (useSessionUser)
 * - GET /app/leads           → leads query (useTenantLeads) and/or offers-internal fetch
 * - GET /app/jobs            → jobs query (useJobs)
 * - GET /api/pipeline-runs?… → pipeline runs (usePipelineRuns) and/or offers-internal fetch
 * - GET /quotes/{leadId}/json → `useOffers` / Quotes page only (`fetchOffers` fan-out, N ≤ cap)
 */

export function isDashboardApiTimingEnabled(): boolean {
  return process.env.NEXT_PUBLIC_DEBUG_DASHBOARD_API_TIMING === "true";
}

type ApiTimingPhase = "start" | "success" | "http_error" | "timeout" | "network_error";

export function logDashboardApiRequest(
  phase: ApiTimingPhase,
  ctx: {
    method: string;
    path: string;
    durationMs: number;
    status?: number;
    detail?: string;
  },
): void {
  if (!isDashboardApiTimingEnabled()) {
    return;
  }

  const { method, path, durationMs, status, detail } = ctx;
  const base = `[dashboard-api-timing] ${phase.padEnd(14)} ${method} ${path} ${durationMs}ms`;
  const suffix =
    status !== undefined
      ? ` status=${status}`
      : "";
  const extra = detail ? ` ${detail}` : "";
  // eslint-disable-next-line no-console -- intentional debug instrumentation
  console.debug(`${base}${suffix}${extra}`);
}

/** Wraps a TanStack `queryFn` to log wall-clock duration (pairs with per-HTTP logs from `apiRequest`). */
export async function runDashboardQueryFnLogged<T>(name: string, queryFn: () => Promise<T>): Promise<T> {
  if (!isDashboardApiTimingEnabled()) {
    return queryFn();
  }
  const startedAt = Date.now();
  // eslint-disable-next-line no-console -- intentional debug instrumentation
  console.debug("[dashboard-api-timing] queryFn start", { name, at: startedAt });
  try {
    const data = await queryFn();
    // eslint-disable-next-line no-console -- intentional debug instrumentation
    console.debug("[dashboard-api-timing] queryFn success", {
      name,
      durationMs: Date.now() - startedAt,
    });
    return data;
  } catch (error) {
    // eslint-disable-next-line no-console -- intentional debug instrumentation
    console.debug("[dashboard-api-timing] queryFn failure", {
      name,
      durationMs: Date.now() - startedAt,
      error: error instanceof Error ? error.message : String(error),
    });
    throw error;
  }
}

/** Boundaries for `fetchOffers` (useOffers): wall-clock over pipeline + leads + quote fan-out. */
export function logDashboardOffersQuery(
  phase: "start" | "success" | "failure",
  ctx: {
    tenantId: string;
    durationMs?: number;
    offersCount?: number;
    quoteFetches?: number;
    error?: string;
  },
): void {
  if (!isDashboardApiTimingEnabled()) {
    return;
  }
  // eslint-disable-next-line no-console -- intentional debug instrumentation
  console.debug(`[dashboard-api-timing] useOffers fetchOffers ${phase}`, ctx);
}
