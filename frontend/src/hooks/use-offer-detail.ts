"use client";

import { useQuery } from "@tanstack/react-query";
import { apiRequest } from "@/lib/api/client";
import { QuoteTotalsPayload } from "@/types/offers";

export function useOfferDetail(leadId?: string, enabled = true) {
  return useQuery({
    queryKey: ["offers", "detail", leadId],
    queryFn: () => apiRequest<QuoteTotalsPayload>(`/quotes/${leadId}/json`),
    enabled: enabled && Boolean(leadId),
    staleTime: 1000 * 30,
  });
}
