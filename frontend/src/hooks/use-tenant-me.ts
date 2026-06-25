"use client";

import { useQuery } from "@tanstack/react-query";
import { getTenantMe } from "@/lib/tenant";
import { runDashboardQueryFnLogged } from "@/lib/api/request-timing";

export const TENANT_ME_QUERY_KEY = ["tenant", "me"] as const;

export function useTenantMe(enabled: boolean) {
  return useQuery({
    queryKey: TENANT_ME_QUERY_KEY,
    queryFn: () =>
      runDashboardQueryFnLogged("tenant-me", () => getTenantMe()),
    enabled,
    staleTime: 1000 * 60 * 5,
  });
}
