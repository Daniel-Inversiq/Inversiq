"use client";

import { useQuery } from "@tanstack/react-query";
import { ApiError } from "@/lib/api/client";
import { fetchBillingState } from "@/lib/api/billing";

export function useBillingState(queryString: string, enabled: boolean) {
  return useQuery({
    queryKey: ["billing", "state", queryString],
    queryFn: () => fetchBillingState(queryString),
    enabled,
    retry: (failureCount, error) => {
      if (error instanceof ApiError && [401, 403].includes(error.status)) {
        return false;
      }
      return failureCount < 1;
    },
  });
}
