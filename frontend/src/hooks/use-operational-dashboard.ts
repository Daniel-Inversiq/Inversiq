"use client";

import { useQuery } from "@tanstack/react-query";
import { fetchOperationalDashboard } from "@/lib/api/operational-dashboard";
import { runDashboardQueryFnLogged } from "@/lib/api/request-timing";
import { DASHBOARD_LIVE_QUERY_OPTIONS } from "@/lib/dashboard-live";

export function operationalDashboardQueryKey(
  tenantId: string,
  chartDays: number,
  timezoneOffsetMinutes: number,
) {
  return ["operational-dashboard", tenantId, chartDays, timezoneOffsetMinutes] as const;
}

type Options = {
  tenantId: string;
  chartDays: number;
  enabled?: boolean;
  /** When true, poll on an interval and refetch on focus/reconnect (dashboard). */
  live?: boolean;
};

export function useOperationalDashboard(options: Options) {
  const { tenantId, chartDays, enabled = true, live = false } = options;
  const tz =
    typeof window !== "undefined" ? -new Date().getTimezoneOffset() : 0;

  return useQuery({
    queryKey: operationalDashboardQueryKey(tenantId, chartDays, tz),
    queryFn: () =>
      runDashboardQueryFnLogged("operational-dashboard", () =>
        fetchOperationalDashboard({
          chartDays,
          timezoneOffsetMinutes: tz,
        }),
      ),
    enabled: enabled && Boolean(tenantId),
    staleTime: 1000 * 15,
    ...(live ? DASHBOARD_LIVE_QUERY_OPTIONS : {}),
  });
}
