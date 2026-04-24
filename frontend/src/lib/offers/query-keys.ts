/** Align with `usePipelineRuns` / `useTenantLeads` so `fetchOffers` can read the same React Query cache. */

export function tenantLeadsQueryKey(tenantId: string) {
  return ["tenant", "leads", tenantId] as const;
}

/** Query param `limit` when listing pipeline runs for offers (matches dashboard `usePipelineRuns`). */
export const OFFERS_PIPELINE_FETCH_LIMIT = 100;

/** Max distinct leads processed for quote JSON fan-out (matches `fetchOffers`). */
export const OFFERS_QUOTE_FANOUT_CAP = 50;

export function pipelineRunsQueryKey(
  tenantId: string | undefined,
  leadId: string | undefined,
  limit: number | undefined,
) {
  return ["pipeline-runs", tenantId, leadId, limit] as const;
}
