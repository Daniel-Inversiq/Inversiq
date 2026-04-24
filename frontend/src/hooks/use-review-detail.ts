"use client";

import { useQuery } from "@tanstack/react-query";
import { fetchReviewDetail } from "@/lib/api/reviews";

export function useReviewDetail(leadId?: string, enabled = true) {
  return useQuery({
    queryKey: ["reviews", "detail", leadId],
    queryFn: () => fetchReviewDetail(leadId ?? ""),
    enabled: enabled && Boolean(leadId),
    staleTime: 1000 * 30,
  });
}

