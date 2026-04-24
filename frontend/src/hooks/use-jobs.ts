"use client";

import { useQuery } from "@tanstack/react-query";
import { fetchJobs } from "@/lib/api/jobs";
import { runDashboardQueryFnLogged } from "@/lib/api/request-timing";
import { DateFilterValue } from "@/lib/date-filter";

export function useJobs(enabled = true, dateFilter?: DateFilterValue) {
  return useQuery({
    queryKey: ["jobs", dateFilter?.date, dateFilter?.start, dateFilter?.end],
    queryFn: () => runDashboardQueryFnLogged("jobs (useJobs)", () => fetchJobs(dateFilter)),
    enabled,
    staleTime: 1000 * 30,
  });
}
