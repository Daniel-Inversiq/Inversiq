import type { PipelineRunItem, ReviewQueueRow, TenantLeadListItem } from "@/types/offers";

import { dedupeLatestByLead } from "@/lib/offers/offer-rows-summary";
import { parseApiDateTime } from "@/lib/presentation";
import { isReviewFlowStatus } from "@/lib/product-flow";

function parseTimeMs(value: string | null | undefined): number {
  if (!value) {
    return 0;
  }
  const t = parseApiDateTime(value).getTime();
  return Number.isNaN(t) ? 0 : t;
}

function firstTimestamp(...candidates: Array<string | null | undefined>): string | null {
  for (const candidate of candidates) {
    if (typeof candidate === "string" && candidate.trim()) {
      return candidate.trim();
    }
  }
  return null;
}

/**
 * Review / Controle queue from pipeline runs plus leads when intake (or similar) sets
 * `Lead.status` to a review-needed state without creating a `pipeline_runs` row.
 *
 * Keeps latest run per lead (same dedupe as offers), then adds lead-backed rows for leads
 * that are in a review-needed status but do not already have a review row.
 */
export function buildReviewQueueRowsFromPipelineAndLeads(
  runItems: PipelineRunItem[],
  leads: TenantLeadListItem[],
  tenantId: string,
): ReviewQueueRow[] {
  const deduped = dedupeLatestByLead(runItems);
  const leadById = new Map(leads.map((lead) => [lead.id, lead]));

  const fromRuns: ReviewQueueRow[] = deduped
    .filter((run) => isReviewFlowStatus(run.status))
    .map((run) => {
      const leadId = String(run.lead_id ?? "").trim();
      const lead = leadById.get(leadId);
      const createdAt = firstTimestamp(
        run.created_at,
        run.submitted_at,
        run.review_created_at,
        lead?.created_at,
        lead?.submitted_at,
        lead?.review_created_at,
      );
      const updatedAt = firstTimestamp(
        run.updated_at,
        run.review_updated_at,
        run.completed_at,
        run.next_action_at,
        lead?.updated_at,
        lead?.review_updated_at,
        lead?.next_action_at,
        createdAt,
      );
      return {
        runId: run.id,
        leadId,
        tenantId: run.tenant_id,
        status: run.status,
        createdAt,
        updatedAt,
        customerName: lead?.name?.trim() || "",
        primaryHref: `/reviews/${leadId}`,
      } satisfies ReviewQueueRow;
    });

  const usedLeadIds = new Set(fromRuns.map((r) => r.leadId));
  const out: ReviewQueueRow[] = [...fromRuns];

  for (const lead of leads) {
    const lid = String(lead.id ?? "").trim();
    if (!lid || usedLeadIds.has(lid)) {
      continue;
    }
    if (!isReviewFlowStatus(lead.status)) {
      continue;
    }
    usedLeadIds.add(lid);
    const createdAt = firstTimestamp(
      lead.created_at,
      lead.submitted_at,
      lead.review_created_at,
    );
    const updatedAt = firstTimestamp(
      lead.updated_at,
      lead.review_updated_at,
      lead.next_action_at,
      createdAt,
    );
    out.push({
      runId: 0,
      leadId: lid,
      tenantId,
      status: lead.status,
      createdAt,
      updatedAt,
      customerName: lead.name?.trim() || "",
      primaryHref: `/reviews/${lid}`,
    });
  }

  return out.sort(
    (a, b) => parseTimeMs(b.updatedAt ?? b.createdAt) - parseTimeMs(a.updatedAt ?? a.createdAt),
  );
}
