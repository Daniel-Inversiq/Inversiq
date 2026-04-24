import { apiRequest } from "@/lib/api/client";

export type ReviewDetailResponse = {
  lead_id: string;
  status: string | null;
  review_reason: string | null;
  status_reason: string | null;
  error_info: string | null;
  created_at: string | null;
  updated_at: string | null;
  customerName: string | null;
  customerEmail: string | null;
  customerPhone: string | null;
  projectLocation: string | null;
  squareMeters: string | null;
  jobType: string | null;
  projectDescription: string | null;
  includedWork: string | null;
  publicNotes: string | null;
  excludedNotes: string | null;
  discountPercent: string | null;
  vatRatePercent: string | null;
  manualTotal: string | null;
  subtotalExcl: string | null;
  photoUrls: string[];
  review_reasons: string[];
  lead: Record<string, unknown> | null;
  intake: Record<string, unknown> | null;
  estimate: Record<string, unknown> | null;
  editor: Record<string, unknown> | null;
  overrides: Record<string, unknown> | null;
};

export function fetchReviewDetail(leadId: string) {
  const normalizedLeadId = encodeURIComponent(String(leadId ?? "").trim());
  return apiRequest<ReviewDetailResponse>(`/app/reviews/${normalizedLeadId}/detail`);
}

