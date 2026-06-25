"use client";

import { useQuery } from "@tanstack/react-query";
import { fetchPipelineRuns } from "@/lib/api/pipeline-runs";
import { runDashboardQueryFnLogged } from "@/lib/api/request-timing";
import { DASHBOARD_LIVE_QUERY_OPTIONS } from "@/lib/dashboard-live";
import { pipelineRunsQueryKey } from "@/lib/offers/query-keys";

type UsePipelineRunsOptions = {
  tenantId?: string;
  leadId?: string;
  enabled?: boolean;
  limit?: number;
  /** When true, poll on an interval and refetch on focus/reconnect (dashboard). */
  live?: boolean;
};

export function usePipelineRuns(options: UsePipelineRunsOptions) {
  const { tenantId, leadId, enabled = true, limit, live = false } = options;
  return useQuery({
    queryKey: pipelineRunsQueryKey(tenantId, leadId, limit),
    queryFn: () =>
      runDashboardQueryFnLogged("pipeline-runs (usePipelineRuns)", () =>
        fetchPipelineRuns({ tenantId, leadId, limit }),
      ),
    enabled: enabled && Boolean(tenantId || leadId),
    staleTime: 1000 * 15,
    ...(live ? DASHBOARD_LIVE_QUERY_OPTIONS : {}),
  });
}
