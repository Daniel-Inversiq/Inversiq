"use client";

import { useQuery } from "@tanstack/react-query";
import { fetchDashboardActivity } from "@/lib/api/dashboard";

type UseDashboardActivityOptions = {
  enabled?: boolean;
};

export function useDashboardActivity(options: UseDashboardActivityOptions = {}) {
  return useQuery({
    queryKey: ["dashboard", "activity"],
    queryFn: fetchDashboardActivity,
    enabled: options.enabled ?? true,
  });
}
