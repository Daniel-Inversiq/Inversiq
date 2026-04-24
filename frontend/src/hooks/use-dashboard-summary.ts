"use client";

import { useQuery } from "@tanstack/react-query";
import { fetchDashboardSummary } from "@/lib/api/dashboard";

type UseDashboardSummaryOptions = {
  enabled?: boolean;
};

export function useDashboardSummary(options: UseDashboardSummaryOptions = {}) {
  return useQuery({
    queryKey: ["dashboard", "summary"],
    queryFn: fetchDashboardSummary,
    enabled: options.enabled ?? true,
  });
}
