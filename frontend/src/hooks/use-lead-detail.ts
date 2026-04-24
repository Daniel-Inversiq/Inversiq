"use client";

import { useQuery } from "@tanstack/react-query";
import { fetchLeadDetail } from "@/lib/api/leads";

export function useLeadDetail(leadId?: string, enabled = true) {
  return useQuery({
    queryKey: ["leads", "detail", leadId],
    queryFn: () => fetchLeadDetail(leadId ?? ""),
    enabled: enabled && Boolean(leadId),
    staleTime: 1000 * 30,
  });
}
