import { apiRequest } from "@/lib/api/client";
import { TenantLeadListItem } from "@/types/offers";
import { DateFilterValue, toApiDateFilterQuery } from "@/lib/date-filter";

export function fetchTenantLeads(dateFilter?: DateFilterValue) {
  if (!dateFilter) {
    return apiRequest<TenantLeadListItem[]>("/app/leads");
  }
  const params = new URLSearchParams(
    toApiDateFilterQuery(dateFilter) as Record<string, string>,
  );
  return apiRequest<TenantLeadListItem[]>(`/app/leads?${params.toString()}`);
}

export function fetchLeadDetail(leadId: string) {
  const normalizedLeadId = encodeURIComponent(String(leadId ?? "").trim());
  return apiRequest<Record<string, unknown>>(`/app/leads/${normalizedLeadId}`);
}
