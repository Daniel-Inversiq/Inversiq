const normalize = (value: string | null | undefined) => (value ?? "").trim().toUpperCase();

const OFFER_INCLUDED = new Set([
  "NEW",
  "RUNNING",
  "PROCESSING",
  "SUCCEEDED",
  /** Engine persists successful runs as COMPLETED (`inversiq.engine.runner._finish_pipeline_run`). */
  "COMPLETED",
  /** Intake can finish here when tenant pricing is missing — still a customer offer request. */
  "CONFIG_NEEDED",
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

/** Lead statuses treated as “closed” when `?filter=open` is applied on `/customers`. */
const CLOSED_LEAD_CUSTOMER_FILTER = new Set([
  "WON",
  "LOST",
  "REJECTED",
  "DECLINED",
  "CANCELLED",
  "ARCHIVED",
  "CLOSED",
  "DONE",
]);

/** Used by `/customers?filter=open` (dashboard KPI deep link). */
export function isOpenLeadCustomerFilter(status: string | null | undefined): boolean {
  const u = normalize(status);
  if (!u) {
    return true;
  }
  return !CLOSED_LEAD_CUSTOMER_FILTER.has(u);
}

/**
 * Subset of review-queue rows for `/review?filter=attention` (dashboard KPI).
 * Focuses on items that typically need the next human decision.
 */
export function isReviewDashboardAttentionStatus(status: string | null | undefined): boolean {
  const u = normalize(status);
  return (
    u === "NEEDS_REVIEW" ||
    u === "REVIEW_REQUIRED" ||
    u === "PROCESSING_FAILED" ||
    u === "FAILED" ||
    u === "ERROR" ||
    u === "UNCERTAIN" ||
    u === "FLAGGED_DAMAGE"
  );
}

