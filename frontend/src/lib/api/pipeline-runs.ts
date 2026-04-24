import { apiRequest } from "@/lib/api/client";
import { PipelineRunDebugResponse, PipelineRunsResponse } from "@/types/offers";

type ListPipelineRunsOptions = {
  tenantId?: string;
  leadId?: string;
  limit?: number;
};

export function fetchPipelineRuns(options: ListPipelineRunsOptions) {
  const params = new URLSearchParams();
  if (options.tenantId) {
    params.set("tenant_id", options.tenantId);
  }
  if (options.leadId) {
    params.set("lead_id", options.leadId);
  }
  params.set("limit", String(options.limit ?? 50));
  return apiRequest<PipelineRunsResponse>(`/api/pipeline-runs?${params.toString()}`);
}

export function fetchPipelineRunDebug(runId: number) {
  return apiRequest<PipelineRunDebugResponse>(`/api/pipeline-runs/${runId}/debug`);
}
