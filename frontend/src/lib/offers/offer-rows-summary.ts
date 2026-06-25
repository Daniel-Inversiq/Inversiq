import type { OfferRow, PipelineRunItem, TenantLeadListItem } from "@/types/offers";

import { OFFERS_QUOTE_FANOUT_CAP } from "@/lib/offers/query-keys";
import { isOfferBucketStatus } from "@/lib/product-flow";

/** Same dedupe semantics as the heavy `fetchOffers` path (latest run id per lead). */
export function dedupeLatestByLead(items: PipelineRunItem[]): PipelineRunItem[] {
  const latestByLead = new Map<string, PipelineRunItem>();

  for (const item of items) {
    const current = latestByLead.get(item.lead_id);
    if (!current || item.id > current.id) {
      latestByLead.set(item.lead_id, item);
    }
  }

  return Array.from(latestByLead.values()).sort((a, b) => b.id - a.id);
}

/**
 * Dashboard / overview: offer rows from pipeline + leads only (no `/quotes/{id}/json`).
 * Amount and project description are left empty until a full offers fetch loads quote JSON.
 *
 * `publish_quote` / `compute_and_persist_quote` often update `Lead` without creating a
 * `pipeline_runs` row. Those leads are merged in when they have an offer-flow status and no run exists.
 */
export function buildOfferRowsSummaryFromPipelineAndLeads(
  runItems: PipelineRunItem[],
  leads: TenantLeadListItem[],
  options?: { maxRows?: number },
): OfferRow[] {
  const maxRows = options?.maxRows ?? OFFERS_QUOTE_FANOUT_CAP;
  const deduped = dedupeLatestByLead(runItems);
  const leadIdsWithRun = new Set(deduped.map((r) => String(r.lead_id ?? "").trim()));
  const latestRuns = deduped.filter((run) => isOfferBucketStatus(run.status)).slice(0, maxRows);
  const leadById = new Map(leads.map((lead) => [lead.id, lead]));

  const fromRuns: OfferRow[] = latestRuns.map((run) => {
    const normalizedLeadId = String(run.lead_id ?? "").trim();
    const lead = leadById.get(normalizedLeadId);
    return {
      runId: run.id,
      leadId: normalizedLeadId,
      customerName: lead?.name?.trim() || "",
      projectDescription: null,
      status: run.status,
      createdAt: run.created_at,
      updatedAt: run.updated_at ?? run.completed_at,
      amount: null,
      amountLoadFailed: false,
      detailHref: `/quotes/${normalizedLeadId}`,
    } satisfies OfferRow;
  });

  const usedLeadIds = new Set(fromRuns.map((r) => r.leadId));
  const out: OfferRow[] = [...fromRuns];

  for (const lead of leads) {
    if (out.length >= maxRows) {
      break;
    }
    const lid = String(lead.id ?? "").trim();
    if (!lid || usedLeadIds.has(lid)) {
      continue;
    }
    if (leadIdsWithRun.has(lid)) {
      continue;
    }
    if (!isOfferBucketStatus(lead.status)) {
      continue;
    }
    usedLeadIds.add(lid);
    out.push({
      runId: 0,
      leadId: lid,
      customerName: lead.name?.trim() || "",
      projectDescription: null,
      status: lead.status,
      createdAt: null,
      updatedAt: null,
      amount: null,
      amountLoadFailed: false,
      detailHref: `/quotes/${lid}`,
    });
  }

  return out;
}
