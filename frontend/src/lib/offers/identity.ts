import { QuoteTotalsPayload } from "@/types/offers";

function pickFirstText(...candidates: unknown[]): string {
  for (const candidate of candidates) {
    if (typeof candidate === "string" && candidate.trim()) {
      return candidate.trim();
    }
    if (typeof candidate === "number" && Number.isFinite(candidate)) {
      return String(candidate);
    }
  }
  return "";
}

function asObject(value: unknown): Record<string, unknown> | null {
  if (!value || typeof value !== "object" || Array.isArray(value)) {
    return null;
  }
  return value as Record<string, unknown>;
}

export function resolveOfferCustomerName(params: {
  quotePayload?: QuoteTotalsPayload | null;
  leadName?: string | null;
  extraCandidates?: unknown[];
}): string {
  const payload = params.quotePayload ?? null;
  const summary = asObject(payload?.summary);
  const intake = asObject(payload?.intake);
  const lead = asObject((payload as Record<string, unknown> | null)?.lead);
  const request = asObject((payload as Record<string, unknown> | null)?.request);

  return pickFirstText(
    ...(params.extraCandidates ?? []),
    params.leadName,
    payload?.summary?.customer_name,
    payload?.summary?.contact_name,
    payload?.summary?.name,
    summary?.full_name,
    payload?.intake?.customer_name,
    payload?.intake?.contact_name,
    payload?.intake?.name,
    intake?.full_name,
    (payload as Record<string, unknown> | null)?.customer_name,
    (payload as Record<string, unknown> | null)?.contact_name,
    (payload as Record<string, unknown> | null)?.full_name,
    (payload as Record<string, unknown> | null)?.name,
    request?.customer_name,
    request?.contact_name,
    request?.full_name,
    request?.name,
    lead?.customer_name,
    lead?.contact_name,
    lead?.full_name,
    lead?.name,
  );
}

export function resolveCanonicalQuoteId(params: {
  quotePayload?: QuoteTotalsPayload | null;
  fallbackIds?: Array<string | null | undefined>;
}): string {
  const payload = params.quotePayload ?? null;
  const meta = asObject((payload as Record<string, unknown> | null)?.meta);
  const lead = asObject((payload as Record<string, unknown> | null)?.lead);
  const request = asObject((payload as Record<string, unknown> | null)?.request);

  return pickFirstText(
    meta?.lead_id,
    (payload as Record<string, unknown> | null)?.lead_id,
    lead?.id,
    request?.lead_id,
    ...(params.fallbackIds ?? []),
  );
}
