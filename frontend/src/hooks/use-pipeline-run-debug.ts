"use client";

import { useQuery } from "@tanstack/react-query";
import { fetchPipelineRunDebug } from "@/lib/api/pipeline-runs";

export function usePipelineRunDebug(runId?: number, enabled = true) {
  return useQuery({
    queryKey: ["pipeline-runs", "debug", runId],
    queryFn: () => fetchPipelineRunDebug(runId ?? 0),
    enabled: enabled && typeof runId === "number" && Number.isFinite(runId),
    staleTime: 1000 * 15,
  });
}
