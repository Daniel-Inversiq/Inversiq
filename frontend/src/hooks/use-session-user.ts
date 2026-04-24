"use client";

import { useQuery } from "@tanstack/react-query";
import { ApiError } from "@/lib/api/client";
import { runDashboardQueryFnLogged } from "@/lib/api/request-timing";
import { fetchSessionUser } from "@/lib/api/session";

export function useSessionUser() {
  return useQuery({
    queryKey: ["session", "me"],
    queryFn: () => runDashboardQueryFnLogged("session (useSessionUser)", fetchSessionUser),
    retry: (failureCount, error) => {
      if (error instanceof ApiError && [401, 403].includes(error.status)) {
        return false;
      }
      return failureCount < 1;
    },
  });
}
