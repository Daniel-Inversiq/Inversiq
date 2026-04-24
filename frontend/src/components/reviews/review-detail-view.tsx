"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useEffect, useMemo, useRef, useState } from "react";
import { useSessionContext } from "@/components/shared/session-provider";
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
import { StatusBadge } from "@/components/ui/status-badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { HelpTooltip } from "@/components/ui/help-tooltip";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from "@/components/ui/dialog";
import { Skeleton } from "@/components/ui/skeleton";
import { useReviewDetail } from "@/hooks/use-review-detail";
import { apiRequest, getApiBaseUrl } from "@/lib/api/client";
import { t, tStatus } from "@/lib/i18n";
import { formatDateTime } from "@/lib/presentation";
import { cn } from "@/lib/utils";

type ReviewDetailViewProps = {
  leadId: string;
};

type SimplePhoto = {
  id: string;
  title: string;
  href: string;
  source: string;
};

type IntakeRow = {
  key: string;
  label: string;
  value: string;
};

type ReviewFormState = {
  squareMeters: string;
  jobType: string;
  projectDescription: string;
};

type OfferFormState = {
  customerName: string;
  customerEmail: string;
  customerPhone: string;
  projectLocation: string;
  includedWork: string;
  excludedNotes: string;
  publicNotes: string;
  discountPercent: string;
  manualTotal: string;
  subtotalExcl: string;
  vatRatePercent: string;
};

type ReviewFieldKey = keyof ReviewFormState;
type OfferFieldKey = keyof OfferFormState;

function asRecord(value: unknown): Record<string, unknown> | null {
  if (!value || typeof value !== "object" || Array.isArray(value)) {
    return null;
  }
  return value as Record<string, unknown>;
}

function asRecordOrJson(value: unknown): Record<string, unknown> | null {
  const direct = asRecord(value);
  if (direct) {
    return direct;
  }
  if (typeof value !== "string" || !value.trim()) {
    return null;
  }
  try {
    return asRecord(JSON.parse(value));
  } catch {
    return null;
  }
}

function textValue(...candidates: unknown[]): string {
  for (const candidate of candidates) {
    if (typeof candidate === "string" && candidate.trim()) {
      return candidate.trim();
    }
    if (typeof candidate === "number" && Number.isFinite(candidate)) {
      return String(candidate);
    }
    if (typeof candidate === "boolean") {
      return String(candidate);
    }
  }
  return "";
}

function mergePrefillState<T extends Record<string, string>>(
  prev: T,
  incoming: T,
  touched: Partial<Record<keyof T, boolean>>,
): T {
  const next = { ...prev };
  for (const key of Object.keys(incoming) as Array<keyof T>) {
    if (touched[key]) {
      continue;
    }
    if (prev[key].trim()) {
      continue;
    }
    if (!incoming[key].trim()) {
      continue;
    }
    next[key] = incoming[key];
  }
  return next;
}

function collectPhotoCandidates(input: unknown): SimplePhoto[] {
  if (!Array.isArray(input)) {
    return [];
  }
  const out: SimplePhoto[] = [];
  for (const item of input) {
    if (typeof item === "string" && item.trim()) {
      const href = item.trim();
      out.push({
        id: href,
        title: t("review.photo.upload"),
        href,
        source: t("review.photo.source.lead"),
      });
      continue;
    }
    const row = asRecord(item);
    if (!row) {
      continue;
    }
    const href = textValue(row.url, row.href, row.src, row.image_url, row.download_url, row.public_url);
    if (!href) {
      continue;
    }
    const id = textValue(row.id, row.key, row.object_key, href) || href;
    const title = textValue(row.filename, row.name, row.label, row.object_key) || t("review.photo.upload");
    const source = textValue(row.source, row.origin) || t("review.photo.source.lead");
    out.push({ id, title, href, source });
  }
  return out;
}

function formatUnknownValue(value: unknown): string {
  if (value === null || value === undefined) {
    return "";
  }
  if (typeof value === "string" || typeof value === "number" || typeof value === "boolean") {
    return String(value);
  }
  if (Array.isArray(value)) {
    const normalized = value
      .map((entry) => (typeof entry === "string" ? entry.trim() : String(entry)))
      .filter(Boolean);
    return normalized.join(", ");
  }
  try {
    return JSON.stringify(value);
  } catch {
    return String(value);
  }
}

function toHumanLabel(key: string): string {
  return key
    .replace(/[_-]+/g, " ")
    .replace(/\s+/g, " ")
    .trim()
    .replace(/^\w/, (char) => char.toUpperCase());
}

function intakeRowsFromObject(data: Record<string, unknown> | null): IntakeRow[] {
  if (!data) {
    return [];
  }
  const rows: IntakeRow[] = [];
  for (const [key, value] of Object.entries(data)) {
    const normalizedValue = formatUnknownValue(value).trim();
    if (!normalizedValue) {
      continue;
    }
    rows.push({ key, label: toHumanLabel(key), value: normalizedValue });
  }
  return rows;
}

const INTAKE_GROUPS: Array<{ id: string; title: string; description: string; keys: string[] }> = [
  {
    id: "project",
    title: t("review.intake_groups.project.title"),
    description: t("review.intake_groups.project.description"),
    keys: [
      "address",
      "street",
      "house_number",
      "postal_code",
      "zip",
      "city",
      "municipality",
      "location",
      "project_location",
      "project_address",
      "project_type",
      "property_type",
      "surface",
      "area",
      "m2",
    ],
  },
  {
    id: "request",
    title: t("review.intake_groups.request.title"),
    description: t("review.intake_groups.request.description"),
    keys: [
      "description",
      "project_description",
      "request_summary",
      "service",
      "services",
      "work_type",
      "timeline",
      "urgency",
      "budget",
      "notes",
      "comment",
    ],
  },
  {
    id: "contact",
    title: t("review.intake_groups.contact.title"),
    description: t("review.intake_groups.contact.description"),
    keys: ["name", "first_name", "last_name", "email", "phone", "phone_number", "preferred_date", "preferred_time"],
  },
];

function splitIntakeRows(rows: IntakeRow[]) {
  const used = new Set<string>();
  const groups = INTAKE_GROUPS.map((group) => {
    const entries = rows.filter((row) => {
      const key = row.key.toLowerCase();
      const match = group.keys.some((candidate) => key === candidate || key.includes(candidate));
      if (match) {
        used.add(row.key);
      }
      return match;
    });
    return { ...group, entries };
  }).filter((group) => group.entries.length > 0);

  const misc = rows.filter((row) => !used.has(row.key));
  return { groups, misc };
}

function resolvePhotoUrl(url: string): string {
  const trimmed = url.trim();
  if (trimmed.startsWith("/files/")) {
    return `${getApiBaseUrl()}${trimmed}`;
  }
  return trimmed;
}

function statusHelpText(status: string): string {
  const normalized = status.trim().toLowerCase();
  if (normalized === "needs_review" || normalized === "review_required") {
    return t("review.reason.status_help.manual_check");
  }
  if (normalized.includes("failed")) {
    return t("review.reason.status_help.processing_failed");
  }
  return t("review.reason.status_help.default");
}

/** Plain-language explanation for known backend reason codes (never show raw codes to users). */
function plainReviewReasonEnglish(reason: string): string | null {
  const normalized = reason.trim().toLowerCase();
  const map: Record<string, string> = {
    needs_review: t("review.reason.codes.needs_review"),
    review_required: t("review.reason.codes.review_required"),
    missing_wall_rate: t("review.reason.codes.missing_wall_rate"),
    missing_photos: t("review.reason.codes.missing_photos"),
    missing_photo: t("review.reason.codes.missing_photo"),
    low_confidence: t("review.reason.codes.low_confidence"),
    vision_low_confidence: t("review.reason.codes.vision_low_confidence"),
    insufficient_context: t("review.reason.codes.insufficient_context"),
    quote_generation_failed: t("review.reason.codes.quote_generation_failed"),
    estimate_generation_failed: t("review.reason.codes.estimate_generation_failed"),
    upload_failed: t("review.reason.codes.upload_failed"),
    "repair work required": t("review.reason.codes.repair_work_required"),
    "substrate visible": t("review.reason.codes.substrate_visible"),
    "surface damage detected": t("review.reason.codes.surface_damage_detected"),
    "surface preparation required": t("review.reason.codes.surface_preparation_required"),
  };
  if (map[normalized]) {
    return map[normalized];
  }
  if (normalized.includes("missing") && normalized.includes("photo")) {
    return t("review.reason.fallbacks.missing_photo");
  }
  if (normalized.includes("missing") && normalized.includes("rate")) {
    return t("review.reason.fallbacks.missing_rate");
  }
  if (normalized.includes("failed")) {
    return t("review.reason.fallbacks.failed");
  }
  if (normalized.includes("confidence")) {
    return t("review.reason.fallbacks.confidence");
  }
  return null;
}

function reviewReasonChipLabelEnglish(reason: string): string {
  const normalized = reason.trim().toLowerCase();
  const map: Record<string, string> = {
    needs_review: t("review.reason.chips.manual_check"),
    review_required: t("review.reason.chips.manual_check"),
    missing_wall_rate: t("review.reason.chips.missing_rate"),
    missing_photos: t("review.reason.chips.photos"),
    missing_photo: t("review.reason.chips.photos"),
    low_confidence: t("review.reason.chips.low_confidence"),
    vision_low_confidence: t("review.reason.chips.photo_check"),
    insufficient_context: t("review.reason.chips.missing_details"),
    quote_generation_failed: t("review.reason.chips.generation_issue"),
    estimate_generation_failed: t("review.reason.chips.generation_issue"),
    upload_failed: t("review.reason.chips.upload_issue"),
    "repair work required": t("review.reason.chips.repair_work"),
    "substrate visible": t("review.reason.chips.substrate"),
    "surface damage detected": t("review.reason.chips.damage"),
    "surface preparation required": t("review.reason.chips.preparation"),
  };
  if (map[normalized]) {
    return map[normalized];
  }
  const translated = plainReviewReasonEnglish(reason);
  return translated ? translated.slice(0, 56) : toHumanLabel(reason).slice(0, 44);
}

function normalizeReviewReasonEnglish(reason: string): string {
  const known = plainReviewReasonEnglish(reason);
  if (known) {
    return known;
  }
  return toHumanLabel(reason);
}

async function postForm(path: string, formData: URLSearchParams) {
  const url = `${getApiBaseUrl()}${path}`;
  const response = await fetch(url, {
    method: "POST",
    credentials: "include",
    headers: {
      "Content-Type": "application/x-www-form-urlencoded;charset=UTF-8",
    },
    body: formData.toString(),
  });
  if (!response.ok) {
    throw new Error(t("review.errors.request_failed_with_status", { status: response.status }));
  }
  return response;
}

type QuoteFromLeadResponse = {
  quote_id?: string;
};

type ExistingQuoteCandidate = {
  quote_id?: string | number | null;
  quoteId?: string | number | null;
  id?: string | number | null;
};

async function createQuote(leadId: string): Promise<string> {
  const response = await apiRequest<QuoteFromLeadResponse>(`/quotes/from-lead/${encodeURIComponent(leadId)}`, {
    method: "POST",
  });
  const quoteId = String(response.quote_id ?? "").trim();
  if (!quoteId) {
    throw new Error(t("review.feedback.continue_failed"));
  }
  return quoteId;
}

function resolveExistingQuoteId(...sources: unknown[]): string {
  for (const source of sources) {
    const record = asRecord(source) as ExistingQuoteCandidate | null;
    if (!record) {
      continue;
    }
    const directId = textValue(record.quote_id, record.quoteId, record.id);
    if (directId) {
      return directId;
    }
  }
  return "";
}

const fieldLabelClass = "text-[12px] font-semibold leading-tight text-zinc-800";
const fieldLabelHintClass = "text-[11px] font-medium uppercase tracking-[0.04em] text-zinc-500";
const fieldInputBase =
  "h-10 w-full rounded-lg border bg-white px-3 text-sm text-zinc-900 shadow-sm outline-none transition duration-150 ease-out motion-reduce:transition-none";
const fieldInputClass = cn(
  fieldInputBase,
  "border-zinc-200/95 placeholder:text-zinc-400 focus:border-zinc-400 focus:ring-2 focus:ring-zinc-900/[0.06] focus:ring-offset-0",
);
const fieldInputAttentionClass = cn(
  fieldInputBase,
  "border-amber-300/90 bg-amber-50/20 focus:border-amber-400 focus:ring-2 focus:ring-amber-500/15",
);
const fieldTextareaClass = cn(
  "min-h-[100px] w-full rounded-lg border border-zinc-200/95 bg-white px-3 py-2.5 text-sm text-zinc-900 shadow-sm outline-none transition duration-150 placeholder:text-zinc-400 focus:border-zinc-400 focus:ring-2 focus:ring-zinc-900/[0.06] motion-reduce:transition-none",
);
const fieldHelpClass = "text-[12px] leading-relaxed text-zinc-500";

function SectionShell({
  title,
  description,
  children,
  className,
  headerExtra,
  titleAside,
}: {
  title: string;
  description?: string;
  children: React.ReactNode;
  className?: string;
  headerExtra?: React.ReactNode;
  /** Shown next to the title (e.g. inline help). */
  titleAside?: React.ReactNode;
}) {
  return (
    <section
      className={cn(
        "surface-card overflow-hidden rounded-2xl border-zinc-200/80 shadow-[0_1px_0_rgba(15,23,42,0.03)]",
        className,
      )}
    >
      <div className="border-b border-zinc-100/95 bg-zinc-50/40 px-5 py-4 sm:px-6">
        <div className="flex flex-wrap items-start justify-between gap-3">
          <div className="min-w-0 space-y-1">
            <div className="flex flex-wrap items-center gap-2">
              <h2 className="text-base font-semibold tracking-tight text-zinc-950">{title}</h2>
              {titleAside}
            </div>
            {description ? <p className="max-w-prose text-[13px] leading-relaxed text-zinc-600">{description}</p> : null}
          </div>
          {headerExtra}
        </div>
      </div>
      <div className="px-5 py-5 sm:px-6 sm:py-6">{children}</div>
    </section>
  );
}

export function ReviewDetailView({ leadId }: ReviewDetailViewProps) {
  const router = useRouter();
  const normalizedLeadId = String(leadId ?? "").trim();
  const session = useSessionContext();
  const tenantId = session.user?.tenant_id?.trim() ?? "";
  const isReady = session.isAuthenticated && tenantId.length > 0 && normalizedLeadId.length > 0;

  const reviewDetailQuery = useReviewDetail(normalizedLeadId, isReady);
  const leadDetail = asRecord(reviewDetailQuery.data);
  const embeddedLead = asRecord(leadDetail?.lead);
  const leadRecord = embeddedLead ?? leadDetail;

  const intakeRecord =
    asRecord(leadDetail?.intake) ??
    asRecord(leadRecord?.intake) ??
    asRecord(leadRecord?.intake_data) ??
    asRecord(leadRecord?.form_answers) ??
    asRecord(leadRecord?.answers) ??
    null;

  const intakeRows = intakeRowsFromObject(intakeRecord);
  const { groups: intakeGroups, misc: intakeMisc } = splitIntakeRows(intakeRows);

  const photos = useMemo(() => {
    const fromLead = [
      ...collectPhotoCandidates(leadDetail?.photoUrls),
      ...collectPhotoCandidates(leadDetail?.photos),
      ...collectPhotoCandidates(leadRecord?.photos),
      ...collectPhotoCandidates(leadRecord?.images),
      ...collectPhotoCandidates(leadRecord?.attachments),
      ...collectPhotoCandidates(leadDetail?.uploads),
      ...collectPhotoCandidates(leadRecord?.uploads),
      ...collectPhotoCandidates(intakeRecord?.photos),
      ...collectPhotoCandidates(intakeRecord?.images),
      ...collectPhotoCandidates(intakeRecord?.attachments),
      ...collectPhotoCandidates(intakeRecord?.uploads),
    ];

    const deduped = new Map<string, SimplePhoto>();
    for (const photo of fromLead) {
      const normalizedHref = photo.href.trim();
      if (!normalizedHref) {
        continue;
      }
      if (!deduped.has(normalizedHref)) {
        deduped.set(normalizedHref, { ...photo, href: normalizedHref });
      }
    }
    return Array.from(deduped.values());
  }, [intakeRecord, leadDetail, leadRecord]);

  const statusValue = textValue(leadDetail?.status, leadRecord?.status) || "UNKNOWN";
  const nameValue = textValue(leadDetail?.customerName, leadRecord?.name, leadRecord?.customer_name) || t("review.summary.unknown_customer");
  const emailValue = textValue(leadDetail?.customerEmail, leadRecord?.email);
  const phoneValue = textValue(leadRecord?.phone, leadRecord?.phone_number, leadRecord?.tel);
  const summaryValue =
    textValue(
      leadRecord?.summary,
      leadRecord?.request_summary,
      leadRecord?.project_description,
      leadRecord?.description,
      intakeRecord?.project_description,
      intakeRecord?.description,
      intakeRecord?.address,
    ) || t("review.summary.no_summary");

  const addressValue =
    textValue(
      leadRecord?.address,
      leadRecord?.project_address,
      intakeRecord?.address,
      intakeRecord?.project_address,
      [intakeRecord?.street, intakeRecord?.house_number].filter(Boolean).join(" ").trim(),
      [intakeRecord?.postal_code ?? intakeRecord?.zip, intakeRecord?.city].filter(Boolean).join(" ").trim(),
      intakeRecord?.location,
    ) || t("review.summary.location_missing");

  const createdAtValue = textValue(leadDetail?.created_at, leadRecord?.created_at, asRecord(leadDetail?.meta)?.created_at);
  const updatedAtValue = textValue(leadDetail?.updated_at, leadRecord?.updated_at, asRecord(leadDetail?.meta)?.updated_at);

  const operatorNotesValue =
    textValue(
      leadRecord?.operator_note,
      leadRecord?.operator_notes,
      leadRecord?.internal_note,
      leadRecord?.internal_notes,
      leadRecord?.note,
      leadRecord?.notes,
      intakeRecord?.notes,
      intakeRecord?.comment,
    ) || "";

  const reviewReason =
    textValue(
      leadDetail?.review_reason,
      leadDetail?.status_reason,
      leadDetail?.error_info,
      asRecord(leadDetail?.review)?.reason,
      asRecord(leadRecord?.review)?.reason,
      leadRecord?.review_reason,
      leadRecord?.status_reason,
    ) || statusHelpText(statusValue);

  const reviewReasons = useMemo(() => {
    const estimateMeta = asRecord(asRecordOrJson(leadRecord?.estimate_json)?.meta);
    const rawReasons = [
      ...(Array.isArray(leadDetail?.review_reasons) ? leadDetail.review_reasons : []),
      ...(Array.isArray(estimateMeta?.needs_review_reasons) ? estimateMeta.needs_review_reasons : []),
      ...(Array.isArray(leadRecord?.needs_review_reasons) ? leadRecord.needs_review_reasons : []),
      asRecord(leadDetail?.review)?.reason,
      asRecord(leadRecord?.review)?.reason,
      leadRecord?.review_reason,
      leadRecord?.status_reason,
      leadRecord?.error_message,
    ];
    const unique = new Set<string>();
    for (const raw of rawReasons) {
      if (typeof raw !== "string" || !raw.trim()) {
        continue;
      }
      unique.add(normalizeReviewReasonEnglish(raw));
    }
    if (unique.size === 0) {
      unique.add(reviewReason);
    }
    return Array.from(unique);
  }, [leadDetail, leadRecord, reviewReason]);
  const quoteReadiness = asRecord(leadDetail?.quote_readiness);
  const missingPricingConfig =
    quoteReadiness?.missing_pricing_config === true ||
    (Array.isArray(quoteReadiness?.missingConfig) &&
      quoteReadiness.missingConfig.includes("price_per_m2")) ||
    reviewReasons.some((reason) => reason.toLowerCase().includes("missing_wall_rate"));

  const reviewDetail = asRecord(leadDetail?.review);
  const reviewRecord = asRecord(leadRecord?.review);
  const estimatePayload = asRecord(leadDetail?.estimate) ?? asRecordOrJson(leadRecord?.estimate_json);
  const estimateCustomer = asRecord(estimatePayload?.customer);
  const estimateProject = asRecord(estimatePayload?.project);
  const estimateMeta = asRecord(estimatePayload?.meta);
  const estimateTotals = asRecord(estimatePayload?.totals);
  const estimateOverrides = asRecord(leadDetail?.overrides) ?? asRecordOrJson(leadRecord?.estimate_overrides_json);
  const editorData =
    asRecord(leadDetail?.editor) ??
    asRecordOrJson(leadRecord?.editor_json) ??
    asRecord(leadRecord?.editor) ??
    asRecordOrJson(leadRecord?.edit_estimate_json) ??
    null;

  const initialReviewFormState = useMemo<ReviewFormState>(
    () => ({
      squareMeters: textValue(
        leadDetail?.squareMeters,
        estimateOverrides?.square_meters,
        reviewDetail?.square_meters,
        reviewRecord?.square_meters,
        leadRecord?.square_meters,
        intakeRecord?.square_meters,
        intakeRecord?.area_sqm,
        intakeRecord?.surface,
        intakeRecord?.m2,
      ),
      jobType: textValue(
        leadDetail?.jobType,
        estimateOverrides?.job_type,
        reviewDetail?.job_type,
        reviewRecord?.job_type,
        leadRecord?.job_type,
        intakeRecord?.job_type,
        intakeRecord?.project_type,
      ),
      projectDescription: textValue(
        leadDetail?.projectDescription,
        estimateOverrides?.project_description,
        estimatePayload?.project_description,
        reviewDetail?.project_description,
        reviewRecord?.project_description,
        leadRecord?.project_description,
        intakeRecord?.project_description,
        intakeRecord?.description,
        leadRecord?.request_summary,
        leadRecord?.description,
        leadRecord?.notes,
      ),
    }),
    [
      estimateOverrides,
      estimatePayload,
      intakeRecord,
      leadDetail?.jobType,
      leadDetail?.projectDescription,
      leadDetail?.squareMeters,
      leadRecord,
      reviewDetail,
      reviewRecord,
    ],
  );

  const initialOfferFormState = useMemo<OfferFormState>(
    () => ({
      customerName: textValue(
        leadDetail?.customerName,
        estimateOverrides?.customer_name,
        estimateCustomer?.name,
        reviewDetail?.customer_name,
        reviewRecord?.customer_name,
        intakeRecord?.customer_name,
        intakeRecord?.name,
        leadRecord?.customer_name,
        leadRecord?.name,
      ),
      customerEmail: textValue(
        leadDetail?.customerEmail,
        estimateOverrides?.customer_email,
        estimateCustomer?.email,
        reviewDetail?.customer_email,
        reviewRecord?.customer_email,
        intakeRecord?.customer_email,
        intakeRecord?.email,
        leadRecord?.customer_email,
        leadRecord?.email,
      ),
      customerPhone: textValue(
        leadDetail?.customerPhone,
        estimateOverrides?.customer_phone,
        estimateCustomer?.phone,
        reviewDetail?.customer_phone,
        reviewRecord?.customer_phone,
        intakeRecord?.customer_phone,
        intakeRecord?.phone,
        intakeRecord?.phone_number,
        leadRecord?.customer_phone,
        leadRecord?.phone,
      ),
      projectLocation: textValue(
        leadDetail?.projectLocation,
        estimateOverrides?.project_location,
        estimatePayload?.location,
        estimateCustomer?.location,
        estimateCustomer?.address,
        estimatePayload?.address,
        estimateProject?.location,
        estimateProject?.address,
        estimateMeta?.address,
        editorData?.project_location,
        reviewDetail?.project_location,
        reviewRecord?.project_location,
        intakeRecord?.project_location,
        intakeRecord?.address,
        intakeRecord?.project_address,
        leadRecord?.project_location,
        leadRecord?.address,
        leadRecord?.project_address,
      ),
      includedWork: textValue(
        leadDetail?.includedWork,
        estimateOverrides?.included_work,
        estimatePayload?.included_work,
        editorData?.included_work,
        reviewDetail?.included_work,
        reviewRecord?.included_work,
        leadRecord?.included_work,
      ),
      excludedNotes: textValue(
        leadDetail?.excludedNotes,
        estimateOverrides?.excluded_notes,
        estimatePayload?.excluded_notes,
        editorData?.excluded_notes,
        reviewDetail?.excluded_notes,
        reviewRecord?.excluded_notes,
        leadRecord?.excluded_notes,
      ),
      publicNotes: textValue(
        leadDetail?.publicNotes,
        estimateOverrides?.public_notes,
        estimatePayload?.public_notes,
        editorData?.public_notes,
        reviewDetail?.public_notes,
        reviewRecord?.public_notes,
        leadRecord?.public_notes,
        leadRecord?.description_for_quote,
      ),
      discountPercent: textValue(
        leadDetail?.discountPercent,
        estimateOverrides?.discount_percent,
        estimatePayload?.discount_percent,
        editorData?.discount_percent,
        reviewDetail?.discount_percent,
        reviewRecord?.discount_percent,
      ),
      manualTotal: textValue(
        leadDetail?.manualTotal,
        estimateOverrides?.manual_total,
        estimatePayload?.manual_total,
        editorData?.manual_total,
        reviewDetail?.manual_total,
        reviewRecord?.manual_total,
      ),
      subtotalExcl: textValue(
        leadDetail?.subtotalExcl,
        estimateOverrides?.subtotal_excl,
        estimateTotals?.pre_tax,
        estimatePayload?.subtotal_excl,
        editorData?.subtotal_excl,
        reviewDetail?.subtotal_excl,
        reviewRecord?.subtotal_excl,
      ),
      vatRatePercent: textValue(
        leadDetail?.vatRatePercent,
        estimateOverrides?.vat_rate_percent,
        estimatePayload?.vat_rate_percent,
        editorData?.vat_rate_percent,
        reviewDetail?.vat_rate_percent,
        reviewRecord?.vat_rate_percent,
      ),
    }),
    [
      editorData,
      estimateCustomer,
      estimateMeta,
      estimateOverrides,
      estimatePayload,
      estimateProject,
      estimateTotals,
      intakeRecord,
      leadDetail,
      leadRecord,
      reviewDetail,
      reviewRecord,
    ],
  );

  const [formState, setFormState] = useState<ReviewFormState>(initialReviewFormState);
  const [offerFormState, setOfferFormState] = useState<OfferFormState>(initialOfferFormState);
  const [touchedReviewFields, setTouchedReviewFields] = useState<Partial<Record<ReviewFieldKey, boolean>>>({});
  const [touchedOfferFields, setTouchedOfferFields] = useState<Partial<Record<OfferFieldKey, boolean>>>({});
  const initializedLeadRef = useRef<string | null>(null);
  const [saveError, setSaveError] = useState<string>("");
  const [saveSuccess, setSaveSuccess] = useState<string>("");
  const [isSaving, setIsSaving] = useState(false);
  const [isGenerating, setIsGenerating] = useState(false);
  const [isAdvancedOpen, setIsAdvancedOpen] = useState(false);

  useEffect(() => {
    if (!leadRecord) {
      return;
    }
    if (initializedLeadRef.current !== normalizedLeadId) {
      initializedLeadRef.current = normalizedLeadId;
      setTouchedReviewFields({});
      setTouchedOfferFields({});
      setFormState(initialReviewFormState);
      setOfferFormState(initialOfferFormState);
      return;
    }
    setFormState((prev) => mergePrefillState(prev, initialReviewFormState, touchedReviewFields));
    setOfferFormState((prev) => mergePrefillState(prev, initialOfferFormState, touchedOfferFields));
  }, [
    initialOfferFormState,
    initialReviewFormState,
    leadRecord,
    normalizedLeadId,
    touchedOfferFields,
    touchedReviewFields,
  ]);

  const isLoading = session.isLoading || (isReady && reviewDetailQuery.isLoading);

  const hasLeadData = Boolean(leadRecord);
  const hasBlockingLoadError = Boolean(!hasLeadData && reviewDetailQuery.error);
  const hasNonBlockingLoadError = Boolean(reviewDetailQuery.error);

  if (!session.isLoading && !session.isAuthenticated) {
    return (
      <Alert variant="destructive">
        <AlertTitle>{t("review.auth.sign_in_required_title")}</AlertTitle>
        <AlertDescription>{t("review.auth.sign_in_required_description")}</AlertDescription>
      </Alert>
    );
  }

  if (isLoading) {
    return (
      <div className="mx-auto max-w-6xl space-y-8 pb-10">
        <div className="space-y-4">
          <Skeleton className="h-3 w-36 rounded-md bg-zinc-100/90" />
          <Skeleton className="h-9 w-56 max-w-full rounded-lg bg-zinc-100/90" />
          <Skeleton className="h-4 w-full max-w-xl rounded-md bg-zinc-100/90" />
          <Skeleton className="h-6 w-full max-w-md rounded-md bg-zinc-100/90" />
        </div>
        <div className="grid gap-8 lg:grid-cols-[minmax(0,1fr)_340px] lg:items-start xl:grid-cols-[minmax(0,1fr)_360px]">
          <div className="space-y-6">
            <Skeleton className="h-36 w-full rounded-2xl bg-zinc-100/90" />
            <Skeleton className="h-56 w-full rounded-2xl bg-zinc-100/90" />
            <Skeleton className="h-72 w-full rounded-2xl bg-zinc-100/90" />
          </div>
          <div className="space-y-4">
            <Skeleton className="h-52 w-full rounded-2xl bg-zinc-100/90 lg:sticky lg:top-24" />
            <Skeleton className="h-40 w-full rounded-2xl bg-zinc-100/90" />
          </div>
        </div>
      </div>
    );
  }

  if (hasBlockingLoadError) {
    return (
      <Alert variant="destructive">
        <AlertTitle>{t("review.errors.load_failed_title")}</AlertTitle>
        <AlertDescription>
          <div className="space-y-3">
            <p className="text-sm leading-relaxed">{t("review.errors.load_failed_description")}</p>
            <Button variant="outline" size="sm" onClick={() => void reviewDetailQuery.refetch()}>
              {t("common.actions.retry")}
            </Button>
          </div>
        </AlertDescription>
      </Alert>
    );
  }

  if (!leadRecord) {
    return (
      <Alert variant="destructive">
        <AlertTitle>{t("review.errors.not_found_title")}</AlertTitle>
        <AlertDescription>
          {t("review.errors.not_found_description")}
        </AlertDescription>
      </Alert>
    );
  }

  const hasAnyError = hasNonBlockingLoadError;
  const refreshWorkspace = () => void reviewDetailQuery.refetch();
  const updateReviewField = (field: ReviewFieldKey, value: string) => {
    setTouchedReviewFields((prev) => (prev[field] ? prev : { ...prev, [field]: true }));
    setFormState((prev) => ({ ...prev, [field]: value }));
  };
  const updateOfferField = (field: OfferFieldKey, value: string) => {
    setTouchedOfferFields((prev) => (prev[field] ? prev : { ...prev, [field]: true }));
    setOfferFormState((prev) => ({ ...prev, [field]: value }));
  };

  const handleSaveAll = async (): Promise<boolean> => {
    setIsSaving(true);
    setSaveError("");
    setSaveSuccess("");
    try {
      const overrideBody = new URLSearchParams();
      if (formState.squareMeters.trim()) {
        overrideBody.set("square_meters", formState.squareMeters.trim());
      }
      if (formState.jobType.trim()) {
        overrideBody.set("job_type", formState.jobType.trim());
      }
      overrideBody.set("project_description", formState.projectDescription.trim());
      await postForm(`/app/reviews/${encodeURIComponent(normalizedLeadId)}/overrides`, overrideBody);

      const estimateBody = new URLSearchParams();
      const setIfPresent = (key: string, value: string) => {
        if (value.trim()) {
          estimateBody.set(key, value.trim());
        }
      };
      setIfPresent("customer_name", offerFormState.customerName);
      setIfPresent("customer_email", offerFormState.customerEmail);
      setIfPresent("customer_phone", offerFormState.customerPhone);
      setIfPresent("project_location", offerFormState.projectLocation);
      setIfPresent("included_work", offerFormState.includedWork);
      setIfPresent("excluded_notes", offerFormState.excludedNotes);
      setIfPresent("public_notes", offerFormState.publicNotes);
      setIfPresent("discount_percent", offerFormState.discountPercent);
      setIfPresent("manual_total", offerFormState.manualTotal);
      setIfPresent("subtotal_excl", offerFormState.subtotalExcl);
      setIfPresent("vat_rate_percent", offerFormState.vatRatePercent);
      await postForm(`/app/leads/${encodeURIComponent(normalizedLeadId)}/edit-estimate`, estimateBody);

      await refreshWorkspace();
      setSaveSuccess(t("review.feedback.saved"));
      return true;
    } catch (error) {
      setSaveError(error instanceof Error ? error.message : t("review.feedback.save_failed"));
      return false;
    } finally {
      setIsSaving(false);
    }
  };

  const handleGenerateEstimate = async () => {
    setIsGenerating(true);
    setSaveError("");
    try {
      const isSaveSuccessful = await handleSaveAll();
      if (!isSaveSuccessful) {
        return;
      }
      const existingQuoteId = resolveExistingQuoteId(
        leadDetail?.quote,
        leadRecord?.quote,
        asRecord(leadRecord?.latest_quote),
        { quote_id: leadDetail?.quote_id },
        { quoteId: leadDetail?.quoteId },
        { quote_id: leadRecord?.quote_id },
        { quoteId: leadRecord?.quoteId },
        { quote_id: leadRecord?.latest_quote_id },
      );
      const quoteId = existingQuoteId || (await createQuote(normalizedLeadId));
      await refreshWorkspace();
      router.push(`/offertes/${encodeURIComponent(quoteId)}`);
    } catch (error) {
      setSaveError(error instanceof Error ? error.message : t("review.feedback.continue_failed"));
    } finally {
      setIsGenerating(false);
    }
  };

  const requiredFieldsComplete =
    formState.squareMeters.trim().length > 0 &&
    formState.jobType.trim().length > 0 &&
    formState.projectDescription.trim().length > 0;

  const primaryReviewReason = reviewReasons[0] ?? reviewReason;
  const extraReviewReasons = reviewReasons.length > 1 ? reviewReasons.slice(1) : [];

  const reviewReasonChips = reviewReasons
    .map(reviewReasonChipLabelEnglish)
    .filter((reason, index, all) => reason.trim().length > 0 && all.indexOf(reason) === index)
    .slice(0, 4);

  const missingSquare = !formState.squareMeters.trim();
  const missingJobType = !formState.jobType.trim();
  const missingDescription = !formState.projectDescription.trim();
  const highlightRequired = !requiredFieldsComplete;

  const summaryCard = (
    <Card className="overflow-hidden rounded-2xl border-zinc-200/85 bg-white shadow-[0_8px_30px_-12px_rgba(15,23,42,0.12)]">
      <CardHeader className="space-y-1 border-b border-zinc-100/95 bg-gradient-to-b from-zinc-50/80 to-white pb-4">
        <div className="flex items-start gap-2">
          <div className="min-w-0 flex-1 space-y-1">
            <CardTitle className="text-lg font-semibold tracking-tight text-zinc-950">{t("review.cta.ready_title")}</CardTitle>
            <CardDescription className="text-[13px] leading-relaxed text-zinc-600">
              {t("review.cta.ready_description")}
            </CardDescription>
          </div>
          <HelpTooltip content={t("context_help.review_cta_continue")} className="mt-0.5" />
        </div>
      </CardHeader>
      <CardContent className="space-y-5 pt-5">
        <div className="space-y-2">
          <Button
            className="h-11 w-full text-[15px] font-semibold shadow-sm transition-[transform,box-shadow] duration-150 hover:shadow-md active:translate-y-px motion-reduce:transform-none"
            onClick={() => void handleGenerateEstimate()}
            disabled={isGenerating || !requiredFieldsComplete || missingPricingConfig}
          >
            {isGenerating ? t("review.cta.continuing") : t("review.cta.continue")}
          </Button>
          {!requiredFieldsComplete ? (
            <p className="text-center text-[12px] leading-relaxed text-amber-800/95">
              {t("review.cta.requirements")}
            </p>
          ) : (
            <p className="text-center text-[12px] text-zinc-500">{t("review.cta.next_hint")}</p>
          )}
        </div>
        <div className="flex flex-col gap-2 border-t border-zinc-100/95 pt-4">
          <Button
            size="sm"
            variant="outline"
            className="h-10 w-full font-medium"
            onClick={() => void handleSaveAll()}
            disabled={isSaving}
          >
            {isSaving ? t("review.actions.saving") : t("review.actions.save")}
          </Button>
          <Link
            href="/review"
            className="text-center text-[13px] font-medium text-zinc-600 underline-offset-4 transition-colors hover:text-zinc-900 hover:underline"
          >
            {t("review.actions.back_to_queue")}
          </Link>
        </div>
        {saveSuccess ? <p className="text-center text-[12px] font-medium text-primary">{saveSuccess}</p> : null}
        {saveError ? <p className="text-center text-[12px] font-medium text-red-600">{saveError}</p> : null}
      </CardContent>
    </Card>
  );

  return (
    <section className="mx-auto max-w-6xl space-y-8 pb-12">
      <header className="space-y-5">
        <div className="flex flex-col gap-4 border-b border-zinc-200/70 pb-6 sm:flex-row sm:items-end sm:justify-between">
          <div className="min-w-0 space-y-2">
            <p className="type-eyebrow text-zinc-500">{t("review.header.kicker")}</p>
            <h1 className="type-page-title text-balance text-zinc-950">{t("review.header.title")}</h1>
            <p className="max-w-prose text-[15px] font-medium leading-relaxed text-zinc-600">
              {t("review.header.subtitle")}
            </p>
          </div>
        </div>
        <div className="flex flex-wrap items-center gap-x-4 gap-y-2 text-[13px] text-zinc-600">
          <span className="font-semibold text-zinc-900">{nameValue}</span>
          <span className="hidden text-zinc-300 sm:inline" aria-hidden="true">
            ·
          </span>
          <span className="tabular-nums text-zinc-600">{t("review.header.requested_at", { date: formatDateTime(createdAtValue || null) })}</span>
          <span className="hidden text-zinc-300 sm:inline" aria-hidden="true">
            ·
          </span>
          <StatusBadge status={statusValue}>{tStatus(statusValue)}</StatusBadge>
        </div>
      </header>

      <div className="grid gap-8 lg:grid-cols-[minmax(0,1fr)_340px] lg:items-start xl:grid-cols-[minmax(0,1fr)_360px]">
        <div className="order-1 space-y-8 lg:order-none">
          {/* Why review */}
          <div className="overflow-hidden rounded-2xl border border-amber-200/80 bg-gradient-to-br from-amber-50/90 via-amber-50/40 to-white shadow-[0_1px_0_rgba(15,23,42,0.03)]">
            <div className="border-b border-amber-200/60 bg-amber-50/50 px-5 py-3.5 sm:px-6">
              <p className="text-[11px] font-semibold uppercase tracking-[0.08em] text-amber-900/75">{t("review.reason.title")}</p>
            </div>
            <div className="space-y-4 px-5 py-5 sm:px-6 sm:py-6">
              <p className="text-[15px] font-medium leading-relaxed text-amber-950">{primaryReviewReason}</p>
              {extraReviewReasons.length > 0 ? (
                <ul className="list-inside list-disc space-y-1.5 text-[13px] leading-relaxed text-amber-950/90">
                  {extraReviewReasons.map((line) => (
                    <li key={line}>{line}</li>
                  ))}
                </ul>
              ) : null}
              {reviewReasonChips.length > 0 ? (
                <div className="flex flex-wrap gap-2 pt-1">
                  {reviewReasonChips.map((reason, index) => (
                    <span
                      key={`${reason}-${index}`}
                      className="rounded-lg border border-amber-200/90 bg-white/80 px-2.5 py-1 text-[11px] font-medium text-amber-950/90 shadow-sm"
                    >
                      {reason}
                    </span>
                  ))}
                </div>
              ) : null}
              <p className="rounded-xl border border-amber-200/70 bg-white/60 px-3.5 py-2.5 text-[13px] font-medium leading-snug text-amber-950">
                {t("review.reason.what_to_do")}
              </p>
              {leadDetail?.error_info ? (
                <p className="text-[12px] leading-relaxed text-amber-900/85">
                  <span className="font-semibold">{t("review.reason.note_label")} </span>
                  {String(leadDetail.error_info)}
                </p>
              ) : null}
            </div>
          </div>
          {missingPricingConfig ? (
            <Alert className="border-amber-300 bg-amber-50 text-amber-900">
              <AlertTitle>Prijsinstellingen ontbreken</AlertTitle>
              <AlertDescription className="mt-2 space-y-2">
                <p>Je hebt nog geen prijs per m² ingesteld. Stel dit eerst in om offertes te genereren.</p>
                <Link href="/instellingen" className="inline-flex h-9 items-center rounded-md bg-zinc-900 px-3 text-sm font-semibold text-white">
                  Ga naar instellingen
                </Link>
              </AlertDescription>
            </Alert>
          ) : null}

          {/* Photos */}
          <SectionShell
            title={t("review.photo.title")}
            description={t("review.photo.description")}
            titleAside={<HelpTooltip content={t("context_help.review_photos")} />}
            headerExtra={
              photos.length > 0 ? (
                <span className="rounded-full border border-zinc-200/90 bg-white px-3 py-1 text-[12px] font-medium text-zinc-600 shadow-sm">
                  {t("review.photo.count", { count: photos.length })}
                </span>
              ) : null
            }
          >
            {photos.length === 0 ? (
              <div className="flex flex-col items-center justify-center rounded-xl border border-dashed border-zinc-200/95 bg-zinc-50/50 px-6 py-14 text-center">
                <p className="text-sm font-semibold text-zinc-800">{t("review.photo.empty_title")}</p>
                <p className="mt-2 max-w-sm text-[13px] leading-relaxed text-zinc-500">
                  {t("review.photo.empty_description")}
                </p>
              </div>
            ) : (
              <div className="space-y-4">
                <div className="grid grid-cols-2 gap-3 sm:grid-cols-3">
                  {photos.map((photo) => (
                    <Dialog key={photo.id}>
                      <DialogTrigger className="group relative block aspect-[4/3] overflow-hidden rounded-xl border border-zinc-200/90 bg-zinc-100/80 text-left shadow-sm outline-none transition duration-200 hover:border-zinc-300 hover:shadow-md focus-visible:ring-2 focus-visible:ring-zinc-400/50">
                        <img
                          src={resolvePhotoUrl(photo.href)}
                          alt={photo.title}
                          className="h-full w-full object-cover transition duration-300 group-hover:scale-[1.02] motion-reduce:transition-none"
                        />
                        <span className="pointer-events-none absolute inset-x-0 bottom-0 bg-gradient-to-t from-black/55 to-transparent px-2.5 pb-2 pt-8">
                          <span className="line-clamp-2 text-[11px] font-medium text-white">{photo.title}</span>
                        </span>
                      </DialogTrigger>
                      <DialogContent className="max-w-4xl border-zinc-200/90 p-3 sm:p-4">
                        <DialogHeader>
                          <DialogTitle>{photo.title}</DialogTitle>
                          <DialogDescription>{t("review.photo.source_label", { source: photo.source })}</DialogDescription>
                        </DialogHeader>
                        <div className="overflow-hidden rounded-lg border border-zinc-200/90 bg-zinc-50/50">
                          <img
                            src={resolvePhotoUrl(photo.href)}
                            alt={photo.title}
                            className="max-h-[80vh] w-full object-contain"
                          />
                        </div>
                      </DialogContent>
                    </Dialog>
                  ))}
                </div>
                <p className="text-[12px] leading-relaxed text-zinc-500">
                  {t("review.photo.tip")}
                </p>
              </div>
            )}
          </SectionShell>

          {/* Editable fields */}
          <SectionShell
            title={t("review.edit.title")}
            description={t("review.edit.description")}
          >
            <div className="space-y-10">
              <div className="space-y-4">
                <div>
                  <p className={fieldLabelHintClass}>{t("review.form.job_details.kicker")}</p>
                  <p className="mt-1 text-sm text-zinc-600">{t("review.form.job_details.description")}</p>
                </div>
                <div className="grid gap-5 sm:grid-cols-2">
                  <div className="space-y-2">
                    <label htmlFor="review-square-meters" className={fieldLabelClass}>
                      {t("review.form.fields.area.label")}
                    </label>
                    <input
                      id="review-square-meters"
                      type="number"
                      min="1"
                      step="1"
                      className={cn(fieldInputClass, highlightRequired && missingSquare && fieldInputAttentionClass)}
                      value={formState.squareMeters}
                      onChange={(event) => updateReviewField("squareMeters", event.target.value)}
                      placeholder={t("review.form.fields.area.placeholder")}
                      aria-invalid={highlightRequired && missingSquare}
                    />
                    <p className={fieldHelpClass}>{t("review.form.fields.area.help")}</p>
                  </div>
                  <div className="space-y-2">
                    <label htmlFor="review-job-type" className={fieldLabelClass}>
                      {t("review.form.fields.job_type.label")}
                    </label>
                    <select
                      id="review-job-type"
                      className={cn(fieldInputClass, highlightRequired && missingJobType && fieldInputAttentionClass)}
                      value={formState.jobType}
                      onChange={(event) => updateReviewField("jobType", event.target.value)}
                      aria-invalid={highlightRequired && missingJobType}
                    >
                      <option value="">{t("review.form.fields.job_type.options.unspecified")}</option>
                      <option value="interior">{t("review.form.fields.job_type.options.interior")}</option>
                      <option value="exterior">{t("review.form.fields.job_type.options.exterior")}</option>
                      <option value="both">{t("review.form.fields.job_type.options.both")}</option>
                    </select>
                    <p className={fieldHelpClass}>{t("review.form.fields.job_type.help")}</p>
                  </div>
                  <div className="space-y-2 sm:col-span-2">
                    <label htmlFor="review-project-description" className={fieldLabelClass}>
                      {t("review.form.fields.project_notes.label")}
                    </label>
                    <textarea
                      id="review-project-description"
                      rows={4}
                      className={cn(fieldTextareaClass, highlightRequired && missingDescription && fieldInputAttentionClass)}
                      value={formState.projectDescription}
                      onChange={(event) => updateReviewField("projectDescription", event.target.value)}
                      placeholder={t("review.form.fields.project_notes.placeholder")}
                      aria-invalid={highlightRequired && missingDescription}
                    />
                    <p className={fieldHelpClass}>{t("review.form.fields.project_notes.help")}</p>
                  </div>
                </div>
              </div>

              <div className="space-y-4 border-t border-zinc-100/95 pt-10">
                <div>
                  <p className={fieldLabelHintClass}>{t("review.form.location.kicker")}</p>
                  <p className="mt-1 text-sm text-zinc-600">{t("review.form.location.description")}</p>
                </div>
                <div className="space-y-2">
                  <label htmlFor="review-project-location-primary" className={fieldLabelClass}>
                    {t("review.form.fields.project_location.label")}
                  </label>
                  <input
                    id="review-project-location-primary"
                    type="text"
                    className={fieldInputClass}
                    value={offerFormState.projectLocation}
                    onChange={(event) => updateOfferField("projectLocation", event.target.value)}
                    placeholder={t("review.form.fields.project_location.placeholder")}
                  />
                  <p className={fieldHelpClass}>{t("review.form.fields.project_location.help")}</p>
                </div>
              </div>

              <div className="rounded-2xl border border-zinc-200/80 bg-zinc-50/35">
                <button
                  type="button"
                  onClick={() => setIsAdvancedOpen((prev) => !prev)}
                  aria-expanded={isAdvancedOpen}
                  className="flex w-full items-center justify-between gap-3 rounded-2xl px-4 py-4 text-left transition-colors hover:bg-zinc-100/50 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-zinc-300/80"
                >
                  <div className="min-w-0 space-y-0.5">
                    <span className="text-[12px] font-semibold uppercase tracking-[0.06em] text-zinc-600">{t("review.form.more_fields.title")}</span>
                    <p className="text-[13px] leading-snug text-zinc-600">{t("review.form.more_fields.description")}</p>
                  </div>
                  <span className="shrink-0 text-[12px] font-semibold text-zinc-600">{isAdvancedOpen ? t("review.actions.hide") : t("review.actions.show")}</span>
                </button>
                {isAdvancedOpen ? (
                  <div className="space-y-8 border-t border-zinc-200/80 px-4 py-5 sm:px-5">
                    <div className="space-y-4">
                      <p className={fieldLabelHintClass}>{t("review.form.contact.kicker")}</p>
                      <div className="grid gap-4 sm:grid-cols-2">
                        <div className="space-y-2 sm:col-span-2">
                          <label htmlFor="review-customer-name" className={fieldLabelClass}>
                            {t("review.form.fields.customer_name.label")}
                          </label>
                          <input
                            id="review-customer-name"
                            type="text"
                            className={fieldInputClass}
                            value={offerFormState.customerName}
                            onChange={(event) => updateOfferField("customerName", event.target.value)}
                            placeholder={t("review.form.fields.customer_name.placeholder")}
                          />
                        </div>
                        <div className="space-y-2">
                          <label htmlFor="review-customer-email" className={fieldLabelClass}>
                            {t("review.form.fields.customer_email.label")}
                          </label>
                          <input
                            id="review-customer-email"
                            type="email"
                            className={fieldInputClass}
                            value={offerFormState.customerEmail}
                            onChange={(event) => updateOfferField("customerEmail", event.target.value)}
                            placeholder={t("review.form.fields.customer_email.placeholder")}
                          />
                        </div>
                        <div className="space-y-2">
                          <label htmlFor="review-customer-phone" className={fieldLabelClass}>
                            {t("review.form.fields.customer_phone.label")}
                          </label>
                          <input
                            id="review-customer-phone"
                            type="text"
                            className={fieldInputClass}
                            value={offerFormState.customerPhone}
                            onChange={(event) => updateOfferField("customerPhone", event.target.value)}
                            placeholder={t("review.form.fields.customer_phone.placeholder")}
                          />
                        </div>
                      </div>
                    </div>
                    <div className="space-y-4">
                      <p className={fieldLabelHintClass}>{t("review.form.quote_wording.kicker")}</p>
                      <div className="grid gap-4 sm:grid-cols-2">
                        <div className="space-y-2 sm:col-span-2">
                          <label htmlFor="review-included-work" className={fieldLabelClass}>
                            {t("review.form.fields.included_work.label")}
                          </label>
                          <textarea
                            id="review-included-work"
                            rows={3}
                            className={fieldTextareaClass}
                            value={offerFormState.includedWork}
                            onChange={(event) => updateOfferField("includedWork", event.target.value)}
                            placeholder={t("review.form.fields.included_work.placeholder")}
                          />
                        </div>
                        <div className="space-y-2 sm:col-span-2">
                          <label htmlFor="review-public-notes" className={fieldLabelClass}>
                            {t("review.form.fields.public_notes.label")}
                          </label>
                          <textarea
                            id="review-public-notes"
                            rows={3}
                            className={fieldTextareaClass}
                            value={offerFormState.publicNotes}
                            onChange={(event) => updateOfferField("publicNotes", event.target.value)}
                            placeholder={t("review.form.fields.public_notes.placeholder")}
                          />
                        </div>
                        <div className="space-y-2 sm:col-span-2">
                          <label htmlFor="review-excluded-notes" className={fieldLabelClass}>
                            {t("review.form.fields.excluded_notes.label")}
                          </label>
                          <textarea
                            id="review-excluded-notes"
                            rows={2}
                            className={fieldTextareaClass}
                            value={offerFormState.excludedNotes}
                            onChange={(event) => updateOfferField("excludedNotes", event.target.value)}
                            placeholder={t("review.form.fields.excluded_notes.placeholder")}
                          />
                        </div>
                      </div>
                    </div>
                    <div className="space-y-4">
                      <p className={fieldLabelHintClass}>{t("review.form.pricing.kicker")}</p>
                      <div className="grid gap-4 sm:grid-cols-2">
                        <div className="space-y-2">
                          <label htmlFor="review-discount" className={fieldLabelClass}>
                            {t("review.form.fields.discount_percent.label")}
                          </label>
                          <input
                            id="review-discount"
                            type="number"
                            step="0.01"
                            className={fieldInputClass}
                            value={offerFormState.discountPercent}
                            onChange={(event) => updateOfferField("discountPercent", event.target.value)}
                            placeholder="0"
                          />
                        </div>
                        <div className="space-y-2">
                          <label htmlFor="review-vat-rate" className={fieldLabelClass}>
                            {t("review.form.fields.vat_rate_percent.label")}
                          </label>
                          <input
                            id="review-vat-rate"
                            type="number"
                            step="0.01"
                            className={fieldInputClass}
                            value={offerFormState.vatRatePercent}
                            onChange={(event) => updateOfferField("vatRatePercent", event.target.value)}
                            placeholder="21"
                          />
                        </div>
                        <div className="space-y-2">
                          <label htmlFor="review-manual-total" className={fieldLabelClass}>
                            {t("review.form.fields.manual_total.label")}
                          </label>
                          <input
                            id="review-manual-total"
                            type="number"
                            step="0.01"
                            className={fieldInputClass}
                            value={offerFormState.manualTotal}
                            onChange={(event) => updateOfferField("manualTotal", event.target.value)}
                            placeholder={t("review.form.fields.manual_total.placeholder")}
                          />
                        </div>
                        <div className="space-y-2">
                          <label htmlFor="review-subtotal-excl" className={fieldLabelClass}>
                            {t("review.form.fields.subtotal_excl.label")}
                          </label>
                          <input
                            id="review-subtotal-excl"
                            type="number"
                            step="0.01"
                            className={fieldInputClass}
                            value={offerFormState.subtotalExcl}
                            onChange={(event) => updateOfferField("subtotalExcl", event.target.value)}
                            placeholder={t("review.form.fields.subtotal_excl.placeholder")}
                          />
                        </div>
                      </div>
                    </div>
                    {intakeRows.length > 0 ? (
                      <div className="grid gap-2.5 md:grid-cols-2">
                        {intakeGroups
                          .flatMap((group) => group.entries)
                          .concat(intakeMisc)
                          .slice(0, 8)
                          .map((row) => (
                            <div key={row.key} className="rounded-xl border border-zinc-200/80 bg-white/80 p-3 shadow-sm">
                              <p className="text-[10px] font-semibold uppercase tracking-[0.06em] text-zinc-500">{row.label}</p>
                              <p className="mt-1.5 text-sm leading-relaxed text-zinc-800">{row.value}</p>
                            </div>
                          ))}
                      </div>
                    ) : null}
                  </div>
                ) : null}
              </div>
            </div>
          </SectionShell>

        </div>

        <aside className="order-2 space-y-6 lg:order-none">
          <div className="lg:sticky lg:top-24 lg:z-10 space-y-6">{summaryCard}</div>

          <Card className="rounded-2xl border-zinc-200/80 bg-zinc-50/30 shadow-[0_1px_0_rgba(15,23,42,0.02)]">
            <CardHeader className="border-b border-zinc-100/90 pb-3">
              <CardTitle className="text-base font-semibold">{t("review.summary.title")}</CardTitle>
              <CardDescription className="text-[13px]">{t("review.summary.description")}</CardDescription>
            </CardHeader>
            <CardContent className="space-y-3 pt-4">
              <div className="rounded-xl border border-zinc-200/85 bg-white/90 p-3 shadow-sm">
                <p className="text-[10px] font-semibold uppercase tracking-[0.06em] text-zinc-500">{t("review.summary.customer")}</p>
                <p className="mt-1 text-sm font-semibold text-zinc-900">{nameValue}</p>
              </div>
              <div className="rounded-xl border border-zinc-200/85 bg-white/90 p-3 text-sm text-zinc-700 shadow-sm">
                <p>{emailValue || t("review.summary.no_email")}</p>
                <p>{phoneValue || t("review.summary.no_phone")}</p>
              </div>
              <div className="rounded-xl border border-zinc-200/85 bg-white/90 p-3 shadow-sm">
                <p className="text-[10px] font-semibold uppercase tracking-[0.06em] text-zinc-500">{t("review.summary.project_location")}</p>
                <p className="mt-1 text-sm leading-relaxed text-zinc-800">{addressValue}</p>
              </div>
              <div className="rounded-xl border border-zinc-200/85 bg-white/90 p-3 shadow-sm">
                <p className="text-[10px] font-semibold uppercase tracking-[0.06em] text-zinc-500">{t("review.summary.summary")}</p>
                <p className="mt-1 text-sm leading-relaxed text-zinc-800">{summaryValue}</p>
              </div>
              <div className="grid gap-2 text-[12px] text-zinc-600">
                <div className="rounded-lg border border-zinc-200/80 bg-white/60 px-3 py-2">
                  {t("review.summary.created")} <span className="font-medium text-zinc-800">{formatDateTime(createdAtValue || null)}</span>
                </div>
                <div className="rounded-lg border border-zinc-200/80 bg-white/60 px-3 py-2">
                  {t("review.summary.updated")} <span className="font-medium text-zinc-800">{formatDateTime(updatedAtValue || null)}</span>
                </div>
              </div>
              {operatorNotesValue ? (
                <div className="rounded-lg border border-zinc-200 bg-white/90 px-3 py-2.5 shadow-sm">
                  <p className="text-[11px] font-semibold uppercase tracking-[0.05em] text-zinc-500">{t("review.summary.internal_note")}</p>
                  <p className="mt-1 text-xs leading-relaxed text-zinc-700">{operatorNotesValue}</p>
                </div>
              ) : null}
              {hasAnyError ? (
                <p className="text-[12px] font-medium text-red-600">
                  {t("review.summary.partial_load_warning")}
                </p>
              ) : null}
            </CardContent>
          </Card>
        </aside>
      </div>
    </section>
  );
}
