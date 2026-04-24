"use client";

import { useQuery } from "@tanstack/react-query";
import { fetchCompanySettings } from "@/lib/api/settings";

export function useCompanySettings(enabled = true) {
  return useQuery({
    queryKey: ["settings", "company"],
    queryFn: fetchCompanySettings,
    enabled,
    staleTime: 1000 * 30,
  });
}
