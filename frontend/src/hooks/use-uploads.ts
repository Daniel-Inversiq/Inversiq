"use client";

import { useQuery } from "@tanstack/react-query";
import { fetchUploads } from "@/lib/api/uploads";

export function useUploads(enabled = true) {
  return useQuery({
    queryKey: ["uploads"],
    queryFn: fetchUploads,
    enabled,
    staleTime: 1000 * 30,
  });
}
