/**
 * Lightweight dashboard polling (no websockets). Used only where explicitly enabled.
 * Pauses in background tabs via `refetchIntervalInBackground: false`.
 */
export const DASHBOARD_LIVE_REFETCH_MS = 15_000;

export const DASHBOARD_LIVE_QUERY_OPTIONS = {
  refetchInterval: DASHBOARD_LIVE_REFETCH_MS,
  refetchOnWindowFocus: true,
  refetchOnReconnect: true,
  refetchIntervalInBackground: false,
} as const;
