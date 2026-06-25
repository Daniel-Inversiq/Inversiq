"use client";

import { useQuery } from "@tanstack/react-query";
import { fetchTenantLeads } from "@/lib/api/leads";
import { runDashboardQueryFnLogged } from "@/lib/api/request-timing";
import { DateFilterValue } from "@/lib/date-filter";
import { tenantLeadsQueryKey } from "@/lib/offers/query-keys";
import { DASHBOARD_LIVE_QUERY_OPTIONS } from "@/lib/dashboard-live";

export function useTenantLeads(
  tenantId: string,
  enabled = true,
  dateFilter?: DateFilterValue,
  /** When true, poll on an interval and refetch on focus/reconnect (dashboard). */
  live = false,
) {
  return useQuery({
    queryKey: [...tenantLeadsQueryKey(tenantId), dateFilter?.date, dateFilter?.start, dateFilter?.end],
    queryFn: () =>
      runDashboardQueryFnLogged("tenant-leads (useTenantLeads)", () =>
        fetchTenantLeads(dateFilter),
      ),
    enabled: enabled && Boolean(tenantId),
    staleTime: 1000 * 30,
    ...(live ? DASHBOARD_LIVE_QUERY_OPTIONS : {}),
  });
}
