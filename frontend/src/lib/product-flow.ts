const normalize = (value: string | null | undefined) => (value ?? "").trim().toUpperCase();

const OFFER_INCLUDED = new Set([
  "NEW",
  "RUNNING",
  "PROCESSING",
  "SUCCEEDED",
  /** Engine persists successful runs as COMPLETED (`inversiq.engine.runner._finish_pipeline_run`). */
  "COMPLETED",
  "READY",
  "QUOTE_READY",
  "SENT",
  "VIEWED",
  "PENDING",
  "PENDING_RESPONSE",
]);

const REVIEW_INCLUDED = new Set([
  "REVIEW_REQUIRED",
  "NEEDS_REVIEW",
  "PROCESSING_FAILED",
  "FAILED",
  "ERROR",
  "UNCERTAIN",
  "FLAGGED_DAMAGE",
]);

const EXECUTION_INCLUDED = new Set([
  "ACCEPTED",
  "SIGNED",
  "SCHEDULED",
  "IN_PROGRESS",
  "DONE",
]);

export function isOfferFlowStatus(status: string | null | undefined): boolean {
  return OFFER_INCLUDED.has(normalize(status));
}

export function isReviewFlowStatus(status: string | null | undefined): boolean {
  return REVIEW_INCLUDED.has(normalize(status));
}

/**
 * Dashboard bucket guard: review-needed statuses always win over offer statuses.
 * This keeps offers/review buckets mutually exclusive even if callers only have one status value.
 */
export function isOfferBucketStatus(status: string | null | undefined): boolean {
  return isOfferFlowStatus(status) && !isReviewFlowStatus(status);
}

export function isExecutionFlowStatus(status: string | null | undefined): boolean {
  return EXECUTION_INCLUDED.has(normalize(status));
}

