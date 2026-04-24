import type { QueryClient } from "@tanstack/react-query";
import { apiRequest } from "@/lib/api/client";
import { logDashboardOffersQuery } from "@/lib/api/request-timing";
import { dedupeLatestByLead } from "@/lib/offers/offer-rows-summary";
import { resolveCanonicalQuoteId, resolveOfferCustomerName } from "@/lib/offers/identity";
import {
  OFFERS_PIPELINE_FETCH_LIMIT,
  OFFERS_QUOTE_FANOUT_CAP,
  pipelineRunsQueryKey,
  tenantLeadsQueryKey,
} from "@/lib/offers/query-keys";
import {
  OfferRow,
  PipelineRunsResponse,
  QuoteTotalsPayload,
  TenantLeadListItem,
} from "@/types/offers";

type LeadQuoteResult = {
  payload: QuoteTotalsPayload | null;
  canonicalLeadId: string | null;
  amount: number | null;
  projectDescription: string | null;
  customerName: string | null;
  failed: boolean;
};

const leadQuoteRequestCache = new Map<string, Promise<LeadQuoteResult>>();
const tenantLeadsRequestCache = new Map<string, Promise<TenantLeadListItem[]>>();

function toAmount(payload: QuoteTotalsPayload): number | null {
  const total = payload.totals?.grand_total ?? payload.totals?.pre_tax;
  return typeof total === "number" && Number.isFinite(total) ? total : null;
}

function toProjectDescription(payload: QuoteTotalsPayload): string | null {
  const candidates = [
    payload.project?.description,
    payload.project?.address,
    payload.project?.location,
    payload.summary?.project_description,
    payload.summary?.description,
    payload.summary?.address,
    payload.summary?.location,
    payload.intake?.project_description,
    payload.intake?.address,
    payload.intake?.street,
    payload.intake?.city,
  ];

  for (const value of candidates) {
    if (typeof value === "string" && value.trim()) {
      return value.trim();
    }
  }
  return null;
}

async function fetchLeadQuoteData(leadId: string): Promise<LeadQuoteResult> {
  const existingRequest = leadQuoteRequestCache.get(leadId);
  if (existingRequest) {
    return existingRequest;
  }

  const request = apiRequest<QuoteTotalsPayload>(`/quotes/${leadId}/json`)
    .then((payload) => {
      const canonicalLeadId = resolveCanonicalQuoteId({
        quotePayload: payload,
        fallbackIds: [leadId],
      });
      return {
        payload,
        canonicalLeadId: canonicalLeadId || null,
        amount: toAmount(payload),
        projectDescription: toProjectDescription(payload),
        customerName: resolveOfferCustomerName({ quotePayload: payload }),
        failed: false,
      };
    })
    .catch(() => ({
      payload: null,
      canonicalLeadId: null,
      amount: null,
      projectDescription: null,
      customerName: null,
      failed: true,
    }));

  leadQuoteRequestCache.set(leadId, request);
  return request;
}

async function fetchTenantLeads(tenantId: string): Promise<TenantLeadListItem[]> {
  const existingRequest = tenantLeadsRequestCache.get(tenantId);
  if (existingRequest) {
    return existingRequest;
  }

  const request = apiRequest<TenantLeadListItem[]>("/app/leads").catch(() => []);
  tenantLeadsRequestCache.set(tenantId, request);
  return request;
}

export type FetchOffersOptions = {
  /** When set, reuse cached pipeline runs / tenant leads if present (e.g. after visiting the dashboard). */
  queryClient?: QueryClient;
};

export async function fetchOffers(tenantId: string, options?: FetchOffersOptions): Promise<OfferRow[]> {
  const { queryClient } = options ?? {};
  const offersQueryStartedAt = Date.now();
  logDashboardOffersQuery("start", { tenantId, durationMs: 0 });

  try {
    const pipelineKey = pipelineRunsQueryKey(tenantId, undefined, OFFERS_PIPELINE_FETCH_LIMIT);
    const cachedRuns = queryClient?.getQueryData<PipelineRunsResponse>(pipelineKey);
    const cachedLeads = queryClient?.getQueryData<TenantLeadListItem[]>(tenantLeadsQueryKey(tenantId));

    const runsPromise = cachedRuns
      ? Promise.resolve(cachedRuns)
      : apiRequest<PipelineRunsResponse>(
          `/api/pipeline-runs?tenant_id=${encodeURIComponent(tenantId)}&limit=${OFFERS_PIPELINE_FETCH_LIMIT}`,
        );

    const leadsPromise = cachedLeads ? Promise.resolve(cachedLeads) : fetchTenantLeads(tenantId);

    const [runs, tenantLeads] = await Promise.all([runsPromise, leadsPromise]);
    const latestRuns = dedupeLatestByLead(runs.items).slice(0, OFFERS_QUOTE_FANOUT_CAP);
    const leadById = new Map(tenantLeads.map((lead) => [lead.id, lead]));

    const offers = await Promise.all(
      latestRuns.map(async (run) => {
        const normalizedLeadId = String(run.lead_id ?? "").trim();
        const lead = leadById.get(normalizedLeadId);
        const quoteResult = await fetchLeadQuoteData(normalizedLeadId);
        const canonicalLeadId =
          quoteResult.canonicalLeadId || normalizedLeadId || String(lead?.id ?? "").trim();

        if (!canonicalLeadId) {
          return null;
        }

        const customerName = resolveOfferCustomerName({
          quotePayload: quoteResult.payload,
          leadName: lead?.name,
        });

        return {
          runId: run.id,
          leadId: canonicalLeadId,
          customerName: customerName || quoteResult.customerName || "",
          projectDescription: quoteResult.projectDescription,
          status: run.status,
          createdAt: run.created_at,
          updatedAt: run.updated_at ?? run.completed_at,
          amount: quoteResult.amount,
          amountLoadFailed: quoteResult.failed,
          detailHref: `/offertes/${encodeURIComponent(canonicalLeadId)}`,
        } satisfies OfferRow;
      }),
    );
    const sanitizedOffers = offers.filter((offer): offer is OfferRow => Boolean(offer));

    const totalMs = Date.now() - offersQueryStartedAt;
    logDashboardOffersQuery("success", {
      tenantId,
      durationMs: totalMs,
      offersCount: sanitizedOffers.length,
      quoteFetches: latestRuns.length,
    });

    return sanitizedOffers;
  } catch (error) {
    logDashboardOffersQuery("failure", {
      tenantId,
      durationMs: Date.now() - offersQueryStartedAt,
      error: error instanceof Error ? error.message : String(error),
    });
    throw error;
  }
}
