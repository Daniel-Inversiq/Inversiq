import { getDateLocale } from "@/lib/i18n";

export function parseApiDateTime(value: string): Date {
  const normalized = value.trim();
  if (!normalized) {
    return new Date(Number.NaN);
  }

  // Backend often returns UTC timestamps without a timezone suffix.
  // Treat those as UTC to avoid displaying them behind local time.
  const hasTimezone = /(?:[zZ]|[+\-]\d{2}:\d{2})$/.test(normalized);
  const normalizedForDate = hasTimezone ? normalized : `${normalized}Z`;
  return new Date(normalizedForDate);
}

export function formatDateTime(value: string | null | undefined) {
  if (!value) {
    return "—";
  }
  const date = parseApiDateTime(value);
  if (Number.isNaN(date.getTime())) {
    return "—";
  }
  return date.toLocaleString(getDateLocale(), {
    year: "numeric",
    month: "2-digit",
    day: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
  });
}

/**
 * Semantic colors for status chips. Intended for `<Badge variant="outline" className={statusTone(s)} />`.
 * — Brand green: completed / success
 * — Sage: in progress / needs attention
 * — Rose: failed / error
 * — Zinc: neutral / unknown
 */
export function statusTone(status: string | null | undefined): string {
  const normalized = (status ?? "").trim().toUpperCase();
  if (["COMPLETED", "SUCCEEDED", "ACCEPTED", "SIGNED", "DONE", "SENT"].includes(normalized)) {
    return "border-primary/25 bg-primary/12 text-primary shadow-none";
  }
  if (["FAILED", "REJECTED", "ERROR", "PROCESSING_FAILED"].includes(normalized)) {
    return "border-rose-200/75 bg-rose-50 text-rose-900 shadow-none";
  }
  if (["CONFIG_NEEDED"].includes(normalized)) {
    return "border-amber-200/80 bg-amber-50 text-amber-900 shadow-none";
  }
  if (
    ["NEEDS_REVIEW", "REVIEW_REQUIRED"].includes(
      normalized,
    )
  ) {
    return "border-blue-200/80 bg-blue-50 text-blue-900 shadow-none";
  }
  if (
    ["RUNNING", "NEW", "PENDING", "SCHEDULED", "PROCESSING", "FLAGGED_DAMAGE"].includes(
      normalized,
    )
  ) {
    return "border-slate-200/90 bg-slate-50 text-slate-800 shadow-none";
  }
  if (normalized === "UNCERTAIN") {
    return "border-zinc-200/85 bg-zinc-100/90 text-zinc-800 shadow-none";
  }
  return "border-zinc-200/85 bg-zinc-50/90 text-zinc-800 shadow-none";
}
