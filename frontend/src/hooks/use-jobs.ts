"use client";

import { useQuery } from "@tanstack/react-query";
import { fetchJobs } from "@/lib/api/jobs";
import { runDashboardQueryFnLogged } from "@/lib/api/request-timing";
import { DASHBOARD_LIVE_QUERY_OPTIONS } from "@/lib/dashboard-live";
import { DateFilterValue } from "@/lib/date-filter";

export function useJobs(
  enabled = true,
  dateFilter?: DateFilterValue,
  /** When true, poll on an interval and refetch on focus/reconnect (dashboard). */
  live = false,
) {
  return useQuery({
    queryKey: ["jobs", dateFilter?.date, dateFilter?.start, dateFilter?.end],
    queryFn: () => runDashboardQueryFnLogged("jobs (useJobs)", () => fetchJobs(dateFilter)),
    enabled,
    staleTime: 1000 * 30,
    ...(live ? DASHBOARD_LIVE_QUERY_OPTIONS : {}),
  });
}
