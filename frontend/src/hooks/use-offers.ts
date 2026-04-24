"use client";

import { useQuery, useQueryClient } from "@tanstack/react-query";
import { fetchOffers } from "@/lib/api/offers";
import { runDashboardQueryFnLogged } from "@/lib/api/request-timing";
import { DateFilterValue } from "@/lib/date-filter";

export function useOffers(tenantId?: string, dateFilter?: DateFilterValue) {
  const queryClient = useQueryClient();
  return useQuery({
    queryKey: ["offers", tenantId, dateFilter?.date, dateFilter?.start, dateFilter?.end],
    queryFn: () =>
      runDashboardQueryFnLogged("offers (useOffers)", () =>
        fetchOffers(tenantId ?? "", { queryClient }),
      ),
    enabled: Boolean(tenantId),
    staleTime: 1000 * 30,
    gcTime: 1000 * 60 * 5,
    retry: 1,
  });
}
