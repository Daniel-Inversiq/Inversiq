"use client";

import Link from "next/link";
import { useMemo, useState } from "react";
import { CalendarClock, CheckCircle2, Clock3, Download, ExternalLink, FileEdit, History, Mail } from "lucide-react";
import { useLeadDetail } from "@/hooks/use-lead-detail";
import { usePipelineRuns } from "@/hooks/use-pipeline-runs";
import { useOfferDetail } from "@/hooks/use-offer-detail";
import { useReviewDetail } from "@/hooks/use-review-detail";
import { useTenantLeads } from "@/hooks/use-tenant-leads";
import { useSessionContext } from "@/components/shared/session-provider";
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
import { StatusBadge } from "@/components/ui/status-badge";
import { Button, buttonVariants } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";
import { getNumberLocale, t, tStatus } from "@/lib/i18n";
import { formatDateTime } from "@/lib/presentation";
import { getBackendHref } from "@/lib/api/origin";
import { resolveOfferCustomerName } from "@/lib/offers/identity";

function formatMoney(value: unknown) {
  if (typeof value !== "number" || !Number.isFinite(value)) {
    return t("offers.detail.not_available");
  }
  return new Intl.NumberFormat(getNumberLocale(), {
    style: "currency",
    currency: "EUR",
    maximumFractionDigits: 2,
  }).format(value);
}

function asObject(value: unknown): Record<string, unknown> | null {
  if (!value || typeof value !== "object" || Array.isArray(value)) {
    return null;
  }
  return value as Record<string, unknown>;
}

type SimplePhoto = {
  id: string;
  title: string;
  href: string;
};

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
        title: "Foto",
        href,
      });
      continue;
    }
    const row = asObject(item);
    if (!row) {
      continue;
    }
    const href = textValue(row.url, row.href, row.src, row.image_url, row.download_url, row.public_url);
    if (!href) {
      continue;
    }
    const id = textValue(row.id, row.key, row.object_key, href) || href;
    const title = textValue(row.filename, row.name, row.label, row.object_key) || "Foto";
    out.push({ id, title, href });
  }
  return out;
}

function resolvePhotoUrl(url: string): string {
  const trimmed = url.trim();
  if (trimmed.startsWith("/files/")) {
    return getBackendHref(trimmed);
  }
  return trimmed;
}

type OfferDetailViewProps = {
  leadId: string;
};

function textValue(...candidates: unknown[]): string {
  for (const candidate of candidates) {
    if (typeof candidate === "string" && candidate.trim()) {
      return candidate.trim();
    }
    if (typeof candidate === "number" && Number.isFinite(candidate)) {
      return String(candidate);
    }
  }
  return "";
}

function parseIsoLocalInput(value: string): string {
  if (!value) {
    return "";
  }
  const normalized = value.trim().replace(" ", "T");
  return normalized.length >= 16 ? normalized.slice(0, 16) : normalized;
}

export function OfferDetailView({ leadId }: OfferDetailViewProps) {
  const session = useSessionContext();
  const tenantId = session.user?.tenant_id?.trim() ?? "";
  const isReady = session.isAuthenticated && tenantId.length > 0;
  const leadsQuery = useTenantLeads(tenantId, isReady);
  const leadDetailQuery = useLeadDetail(leadId, isReady);
  const detailQuery = useOfferDetail(leadId, isReady);
  const reviewDetailQuery = useReviewDetail(leadId, isReady);
  const runsQuery = usePipelineRuns({
    tenantId: isReady ? tenantId : undefined,
    leadId,
    enabled: isReady,
    limit: 10,
  });

  const lead = useMemo(
    () => leadsQuery.data?.find((item) => item.id === leadId) ?? null,
    [leadId, leadsQuery.data],
  );
  const [isSending, setIsSending] = useState(false);
  const [isRecalculating, setIsRecalculating] = useState(false);
  const [isSavingFollowup, setIsSavingFollowup] = useState(false);
  const [actionMessage, setActionMessage] = useState<string>("");
  const [actionError, setActionError] = useState<string>("");
  const detailPayload = asObject(detailQuery.data);
  const detailMeta = asObject(detailPayload?.meta);
  const detailSummary = asObject(detailPayload?.summary);
  const detailIntake = asObject(detailPayload?.intake);
  const reviewDetail = asObject(reviewDetailQuery.data);
  const reviewLead = asObject(reviewDetail?.lead);
  const reviewIntake = asObject(reviewDetail?.intake);
  const leadRecord = asObject(leadDetailQuery.data) ?? asObject(lead);
  const photos = useMemo(() => {
    const payload = detailPayload ?? null;
    const meta = detailMeta ?? null;
    const summary = detailSummary ?? null;
    const intake = detailIntake ?? null;
    const review = reviewDetail ?? null;
    const reviewLeadRecord = reviewLead ?? null;
    const reviewIntakeRecord = reviewIntake ?? null;
    const normalizedLead = leadRecord ?? null;
    const fromLead = [
      ...collectPhotoCandidates(review?.photoUrls),
      ...collectPhotoCandidates(review?.photos),
      ...collectPhotoCandidates(review?.images),
      ...collectPhotoCandidates(review?.attachments),
      ...collectPhotoCandidates(review?.uploads),
      ...collectPhotoCandidates(reviewLeadRecord?.photoUrls),
      ...collectPhotoCandidates(reviewLeadRecord?.photos),
      ...collectPhotoCandidates(reviewLeadRecord?.images),
      ...collectPhotoCandidates(reviewLeadRecord?.attachments),
      ...collectPhotoCandidates(reviewLeadRecord?.uploads),
      ...collectPhotoCandidates(reviewIntakeRecord?.photoUrls),
      ...collectPhotoCandidates(reviewIntakeRecord?.photos),
      ...collectPhotoCandidates(reviewIntakeRecord?.images),
      ...collectPhotoCandidates(reviewIntakeRecord?.attachments),
      ...collectPhotoCandidates(reviewIntakeRecord?.uploads),
      ...collectPhotoCandidates(payload?.photoUrls),
      ...collectPhotoCandidates(payload?.photos),
      ...collectPhotoCandidates(payload?.images),
      ...collectPhotoCandidates(payload?.attachments),
      ...collectPhotoCandidates(payload?.uploads),
      ...collectPhotoCandidates(meta?.photos),
      ...collectPhotoCandidates(meta?.images),
      ...collectPhotoCandidates(meta?.attachments),
      ...collectPhotoCandidates(summary?.photos),
      ...collectPhotoCandidates(summary?.images),
      ...collectPhotoCandidates(summary?.attachments),
      ...collectPhotoCandidates(intake?.photos),
      ...collectPhotoCandidates(intake?.images),
      ...collectPhotoCandidates(intake?.attachments),
      ...collectPhotoCandidates(intake?.uploads),
      ...collectPhotoCandidates(normalizedLead?.photos),
      ...collectPhotoCandidates(normalizedLead?.images),
      ...collectPhotoCandidates(normalizedLead?.attachments),
      ...collectPhotoCandidates(normalizedLead?.uploads),
    ];
    const deduped = new Map<string, SimplePhoto>();
    for (const photo of fromLead) {
      const normalizedHref = photo.href.trim();
      if (!normalizedHref || deduped.has(normalizedHref)) {
        continue;
      }
      deduped.set(normalizedHref, {
        ...photo,
        href: normalizedHref,
      });
    }
    return Array.from(deduped.values());
  }, [detailIntake, detailMeta, detailPayload, detailSummary, leadRecord, reviewDetail, reviewIntake, reviewLead]);
  const photoPreviews = photos.slice(0, 3);
  const primaryPhotoHref = photos[0] ? resolvePhotoUrl(photos[0].href) : "";

  if (!session.isLoading && !session.isAuthenticated) {
    return (
      <Alert variant="destructive">
        <AlertTitle>{t("common.auth.not_logged_in")}</AlertTitle>
        <AlertDescription>
          {t("offers.detail.errors.session_expired")}
        </AlertDescription>
      </Alert>
    );
  }

  if (session.isLoading || leadsQuery.isLoading || detailQuery.isLoading || reviewDetailQuery.isLoading || runsQuery.isLoading) {
    return (
      <div className="space-y-3">
        <Skeleton className="h-10 w-80 rounded-xl" />
        <Skeleton className="h-40 w-full rounded-xl" />
        <Skeleton className="h-40 w-full rounded-xl" />
      </div>
    );
  }

  if (leadsQuery.error || detailQuery.error || reviewDetailQuery.error || runsQuery.error) {
    return (
      <Alert variant="destructive">
        <AlertTitle>{t("offers.detail.errors.load_failed_title")}</AlertTitle>
        <AlertDescription>
          <div className="space-y-3">
            <p>{t("offers.detail.errors.load_failed_description")}</p>
            <Button
              variant="outline"
              size="sm"
              onClick={() =>
                void Promise.all([
                  leadsQuery.refetch(),
                  detailQuery.refetch(),
                  reviewDetailQuery.refetch(),
                  runsQuery.refetch(),
                ])
              }
            >
              {t("common.actions.retry")}
            </Button>
          </div>
        </AlertDescription>
      </Alert>
    );
  }

  if (!lead) {
    return (
      <Alert variant="destructive">
        <AlertTitle>{t("offers.detail.errors.lead_not_found_title")}</AlertTitle>
        <AlertDescription>
          {t("offers.detail.errors.lead_not_found_description")}
        </AlertDescription>
      </Alert>
    );
  }

  const runs = runsQuery.data?.items ?? [];
  const latestRun = runs[0];
  const totals = detailQuery.data?.totals;
  const detailOverrides = asObject(detailMeta?.overrides);
  const detailFollowupSummary = asObject(detailPayload?.followup_summary) ?? asObject(detailMeta?.followup_summary);
  const quoteReadiness =
    asObject(detailPayload?.quote_readiness) ?? asObject(reviewDetail?.quote_readiness);
  const missingFromReadiness =
    quoteReadiness?.missing_pricing_config === true ||
    (Array.isArray(quoteReadiness?.missingConfig) &&
      (quoteReadiness.missingConfig as unknown[]).includes("price_per_m2"));
  /** Prefer live tenant readiness from API; avoid stale estimate_json.meta alone. */
  const missingPricingConfig = quoteReadiness
    ? Boolean(missingFromReadiness)
    : Boolean(detailMeta?.missing_pricing_config);
  const missingConfigKeys = Array.isArray(quoteReadiness?.missingConfig)
    ? (quoteReadiness.missingConfig as unknown[]).filter((k): k is string => typeof k === "string")
    : [];
  const missingConfigLabels: Record<string, string> = {
    price_per_m2: "Prijs per m²",
  };
  const leadStatusForRecalc = String(
    (detailPayload?.lead_status as string | undefined) || lead?.status || "",
  ).toUpperCase();
  const canRecalculateQuote = leadStatusForRecalc === "CONFIG_NEEDED" && quoteReadiness?.isReady === true;
  const summary = detailQuery.data?.summary;
  const intake = detailQuery.data?.intake;
  const statusForNextAction = (latestRun?.status || lead.status || "").trim().toLowerCase();
  const shouldOpenOffer =
    statusForNextAction === "quote_ready" ||
    statusForNextAction === "ready" ||
    statusForNextAction === "succeeded";
  const isNeedsReview =
    statusForNextAction === "needs_review" || statusForNextAction === "review_required";
  const isOfferAlreadySent =
    statusForNextAction === "sent" ||
    statusForNextAction === "viewed" ||
    statusForNextAction === "accepted" ||
    statusForNextAction === "signed" ||
    statusForNextAction === "done" ||
    statusForNextAction === "completed";
  const offerValue = totals?.grand_total ?? totals?.pre_tax;
  const hasOfferValue = typeof offerValue === "number" && Number.isFinite(offerValue) && offerValue > 0;
  const projectDescription =
    summary?.project_description || summary?.description || intake?.project_description || "";
  const projectAddress = summary?.address || intake?.address || "";
  const customerName =
    resolveOfferCustomerName({
      quotePayload: detailQuery.data,
      leadName: lead.name,
      extraCandidates: [
        reviewDetail?.customerName,
        reviewIntake?.customer_name,
        reviewIntake?.contact_name,
        reviewIntake?.full_name,
        reviewIntake?.name,
        reviewLead?.customer_name,
        reviewLead?.contact_name,
        reviewLead?.full_name,
        reviewLead?.name,
      ],
    }) || t("offers.detail.unknown_customer");
  const customerEmail = textValue(lead.email, detailSummary?.customer_email, detailIntake?.email, detailIntake?.customer_email);
  const customerPhone = textValue(detailSummary?.customer_phone, detailIntake?.phone, detailIntake?.phone_number);
  const squareMeters = textValue(detailSummary?.square_meters, detailIntake?.square_meters, detailIntake?.sqm, detailIntake?.m2);
  const workType = textValue(detailSummary?.job_type, detailIntake?.job_type, detailIntake?.project_type);
  const publicNotes = textValue(detailSummary?.public_notes, detailOverrides?.public_notes);
  const internalNotes = textValue(detailOverrides?.internal_notes);
  const nextAction = textValue(detailFollowupSummary?.next_action, detailOverrides?.next_action);
  const nextActionInput = parseIsoLocalInput(
    textValue(detailFollowupSummary?.next_action_at_input, detailOverrides?.next_action_at),
  );

  const publicQuoteHref = getBackendHref(`/quotes/${leadId}/html`);
  const downloadPdfHref = getBackendHref(`/app/leads/${leadId}/export-pdf`);
  const editQuoteHref = `/offertes/${encodeURIComponent(leadId)}/bewerken`;
  const sendQuoteHref = getBackendHref(`/app/leads/${leadId}/send`);

  const saveFollowup = async (formData: FormData) => {
    setActionError("");
    setActionMessage("");
    setIsSavingFollowup(true);
    try {
      const payload = new URLSearchParams();
      payload.set("next_action", String(formData.get("next_action") ?? ""));
      payload.set("next_action_at", String(formData.get("next_action_at") ?? ""));
      payload.set("internal_notes", String(formData.get("internal_notes") ?? ""));
      const response = await fetch(
        getBackendHref(`/app/tenants/${encodeURIComponent(tenantId)}/quotes/${encodeURIComponent(leadId)}/partials/internal-notes`),
        {
          method: "POST",
          credentials: "include",
          headers: { "Content-Type": "application/x-www-form-urlencoded;charset=UTF-8" },
          body: payload.toString(),
        },
      );
      if (!response.ok) {
        throw new Error("Opslaan mislukt");
      }
      await detailQuery.refetch();
      setActionMessage("Opvolging en notitie opgeslagen.");
    } catch (error) {
      setActionError(error instanceof Error ? error.message : "Opslaan mislukt");
    } finally {
      setIsSavingFollowup(false);
    }
  };

  const sendQuote = async () => {
    setActionError("");
    setActionMessage("");
    setIsSending(true);
    try {
      const response = await fetch(sendQuoteHref, {
        method: "POST",
        credentials: "include",
      });
      if (!response.ok) {
        throw new Error("Offerte versturen mislukt");
      }
      await Promise.all([detailQuery.refetch(), runsQuery.refetch()]);
      setActionMessage("Offerte is naar de klant gestuurd.");
    } catch (error) {
      setActionError(error instanceof Error ? error.message : "Offerte versturen mislukt");
    } finally {
      setIsSending(false);
    }
  };

  const recalculateQuote = async () => {
    setActionError("");
    setActionMessage("");
    setIsRecalculating(true);
    try {
      const response = await fetch(getBackendHref(`/quotes/publish/${encodeURIComponent(leadId)}`), {
        method: "POST",
        credentials: "include",
        redirect: "manual",
      });
      if (response.status >= 400) {
        throw new Error("Opnieuw berekenen mislukt");
      }
      await Promise.all([
        detailQuery.refetch(),
        reviewDetailQuery.refetch(),
        runsQuery.refetch(),
        leadsQuery.refetch(),
      ]);
      setActionMessage("Offerte is opnieuw berekend.");
    } catch (error) {
      setActionError(error instanceof Error ? error.message : "Opnieuw berekenen mislukt");
    } finally {
      setIsRecalculating(false);
    }
  };

  const cardShellClass = "rounded-xl border border-zinc-200/75 bg-white p-3 shadow-[0_1px_0_rgba(15,23,42,0.03)] sm:p-3.5";
  const compactHeadingClass = "text-[13px] font-semibold leading-tight tracking-[-0.02em] text-zinc-950";

  return (
    <section className="mx-auto w-full max-w-[min(1480px,100%)] space-y-2.5">
      <header className="space-y-2.5">
        {missingPricingConfig ? (
          <Alert className="rounded-xl border border-zinc-200/75 bg-white text-zinc-900 shadow-[0_1px_0_rgba(15,23,42,0.03)]">
            <AlertTitle>Prijsinstellingen ontbreken</AlertTitle>
            <AlertDescription className="mt-2 space-y-2">
              <p>Je hebt nog geen prijs per m² ingesteld. Stel dit eerst in om offertes te genereren.</p>
              {missingConfigKeys.length > 0 ? (
                <p className="text-[12px] font-medium text-zinc-700">
                  Ontbrekend:{" "}
                  {missingConfigKeys.map((k) => missingConfigLabels[k] ?? k).join(", ")}
                </p>
              ) : null}
              <Link
                href="/instellingen"
                className={buttonVariants({
                  variant: "outline",
                  size: "sm",
                  className: "h-8 rounded-md border-zinc-300/85 bg-white px-2.5 text-[12px] font-semibold text-zinc-700 hover:bg-zinc-50/90",
                })}
              >
                Ga naar instellingen
              </Link>
            </AlertDescription>
          </Alert>
        ) : null}
        {canRecalculateQuote ? (
          <Alert className="rounded-xl border border-zinc-200/75 bg-white text-zinc-900 shadow-[0_1px_0_rgba(15,23,42,0.03)]">
            <AlertTitle>Offerte opnieuw berekenen</AlertTitle>
            <AlertDescription className="mt-2 space-y-2">
              <p className="text-[12px] text-zinc-700">
                Prijsinstellingen zijn nu ingevuld. Deze offerte staat nog op &quot;instellingen nodig&quot; tot je de
                berekening opnieuw uitvoert.
              </p>
              <Button
                type="button"
                size="sm"
                disabled={isRecalculating}
                onClick={() => void recalculateQuote()}
                className="h-8 rounded-md px-2.5 text-[12px] font-semibold"
              >
                {isRecalculating ? "Bezig…" : "Offerte opnieuw berekenen"}
              </Button>
            </AlertDescription>
          </Alert>
        ) : null}
        <div className="space-y-0.5">
          <p className="text-[10px] font-semibold uppercase leading-none tracking-[0.05em] text-zinc-500">{t("offers.detail.header.kicker")}</p>
          <h1 className="text-[22px] font-semibold leading-tight tracking-[-0.02em] text-zinc-950">
            Offerte #{lead.id.slice(-6).toUpperCase()}
          </h1>
          <p className="text-[12px] font-medium text-zinc-600">
            <span className="font-semibold text-zinc-900">{customerName}</span>
            <span className="mx-2">-</span>
            <span>{workType || "Werksoort onbekend"}</span>
            {squareMeters ? <span className="mx-2">- {squareMeters} m2</span> : null}
            {hasOfferValue ? <span className="mx-2">- {formatMoney(offerValue)}</span> : null}
          </p>
        </div>
        <div className="grid gap-2.5 rounded-xl border border-zinc-200/75 bg-white p-3 shadow-[0_1px_0_rgba(15,23,42,0.03)] md:grid-cols-[minmax(0,1fr)_auto] md:items-center sm:p-3.5">
          <div className="space-y-1">
            <p className="text-[10px] font-semibold uppercase leading-none tracking-[0.05em] text-zinc-500">
              {t("offers.detail.status_action.title")}
            </p>
            <div className="flex items-center gap-2">
              <StatusBadge status={latestRun?.status || lead.status}>
                {tStatus(latestRun?.status || lead.status)}
              </StatusBadge>
              <span className="text-[10px] font-medium text-zinc-500">
                {t("offers.detail.cards.status.last_run", {
                  datetime: formatDateTime(latestRun?.updated_at),
                })}
              </span>
            </div>
            <p className="text-[11px] font-medium leading-snug text-zinc-500">{t("offers.detail.status_action.helper")}</p>
          </div>
          <div className="flex flex-wrap items-center justify-end gap-1.5">
            <Button size="sm" onClick={() => void sendQuote()} disabled={isSending}>
              <Mail className="mr-1 h-3.5 w-3.5" /> {isSending ? "Versturen..." : "Stuur naar klant"}
            </Button>
            <Link href={publicQuoteHref} target="_blank" className={buttonVariants({ variant: "outline", size: "sm", className: "border-zinc-300/85 bg-white text-zinc-700 hover:bg-zinc-50/90" })}>
              <ExternalLink className="mr-1 h-3.5 w-3.5" /> Open publieke offerte
            </Link>
            <Link href={downloadPdfHref} target="_blank" className={buttonVariants({ variant: "outline", size: "sm", className: "border-zinc-300/85 bg-white text-zinc-700 hover:bg-zinc-50/90" })}>
              <Download className="mr-1 h-3.5 w-3.5" /> PDF
            </Link>
            <Link href={editQuoteHref} className={buttonVariants({ variant: "outline", size: "sm", className: "border-zinc-300/85 bg-white text-zinc-700 hover:bg-zinc-50/90" })}>
              <FileEdit className="mr-1 h-3.5 w-3.5" /> Bewerken
            </Link>
          </div>
        </div>
        <div className="flex flex-wrap items-center gap-2">
          <Link
            href="/customers"
            className={buttonVariants({
              variant: "outline",
              size: "sm",
              className: "border-zinc-300/85 bg-white text-zinc-700 hover:bg-zinc-50/90",
            })}
          >
            {t("offers.detail.actions.back_to_leads")}
          </Link>
        </div>
      </header>

      <div className="grid grid-cols-1 gap-2.5 lg:grid-cols-3">
        <article className={cardShellClass}>
          <p className="text-[10px] font-semibold uppercase leading-none tracking-[0.05em] text-zinc-500">{t("offers.detail.cards.status.label")}</p>
          <div className="mt-2">
            <StatusBadge status={latestRun?.status || lead.status}>
              {tStatus(latestRun?.status || lead.status)}
            </StatusBadge>
          </div>
          <p className="mt-1 text-[11px] font-medium text-zinc-500">
            {t("offers.detail.cards.status.last_run", {
              datetime: formatDateTime(latestRun?.updated_at),
            })}
          </p>
        </article>

        <article className={cardShellClass}>
          <p className="text-[10px] font-semibold uppercase leading-none tracking-[0.05em] text-zinc-500">{t("offers.detail.cards.quote_value.label")}</p>
          <p className="mt-1.5 text-[1.5rem] font-semibold leading-tight text-zinc-900">
            {formatMoney(offerValue)}
          </p>
          {!hasOfferValue ? (
            <p className="mt-1 text-[11px] font-medium text-zinc-500">{t("offers.detail.cards.quote_value.pending")}</p>
          ) : null}
        </article>

        <article className={cardShellClass}>
          <p className="text-[10px] font-semibold uppercase leading-none tracking-[0.05em] text-zinc-500">{t("offers.detail.cards.customer.label")}</p>
          <p className="mt-1 text-[12px] font-medium text-zinc-600">{lead.email || t("offers.detail.no_email")}</p>
          <p className="mt-2 text-[10px] font-semibold uppercase leading-none tracking-[0.05em] text-zinc-500">Controle</p>
          <p className="mt-1 text-[12px] font-semibold text-zinc-900">
            {isNeedsReview ? "Even nalopen" : isOfferAlreadySent || shouldOpenOffer ? "Gecontroleerd" : "Open"}
          </p>
        </article>
      </div>

      <div className="grid grid-cols-1 gap-2.5 lg:grid-cols-3">
        <div className="space-y-2.5 lg:col-span-2">
          <section className={cardShellClass}>
            <h2 className={compactHeadingClass}>Project & klant</h2>
            <div className="mt-2.5 grid gap-2.5 sm:grid-cols-2">
              <div>
                <p className="text-[10px] font-semibold uppercase leading-none tracking-[0.05em] text-zinc-500">Contact</p>
                <p className="mt-1 text-[12px] font-semibold text-zinc-900">{customerName}</p>
                <p className="text-[12px] font-medium text-zinc-600">{customerEmail || "Geen e-mail"}</p>
                <p className="text-[12px] font-medium text-zinc-600">{customerPhone || "Geen telefoon"}</p>
              </div>
              <div>
                <p className="text-[10px] font-semibold uppercase leading-none tracking-[0.05em] text-zinc-500">Locatie & werk</p>
                <p className="mt-1 text-[12px] font-medium text-zinc-600">{projectAddress || "Geen adres"}</p>
                <p className="text-[12px] font-medium text-zinc-600">{workType || "Werksoort onbekend"}</p>
                <p className="text-[12px] font-medium text-zinc-600">{squareMeters ? `${squareMeters} m2` : "Oppervlakte onbekend"}</p>
              </div>
            </div>
          </section>

          <section className={cardShellClass}>
            <div className="flex items-center justify-between gap-2">
              <h2 className={compactHeadingClass}>Foto&apos;s van aanvraag</h2>
              {photos.length > 0 ? (
                <span className="rounded-full border border-zinc-200/90 bg-zinc-50 px-2 py-0.5 text-[10px] font-semibold uppercase tracking-[0.04em] text-zinc-600">
                  {photos.length} foto{photos.length === 1 ? "" : "'s"}
                </span>
              ) : null}
            </div>
            {photos.length === 0 ? (
              <div className="mt-2.5 rounded-md border border-dashed border-zinc-200/85 bg-zinc-50/55 px-3 py-4">
                <p className="text-[12px] font-medium text-zinc-600">
                  Er zijn geen foto&apos;s toegevoegd aan deze aanvraag.
                </p>
              </div>
            ) : (
              <div className="mt-2.5 space-y-2.5">
                <div className="flex gap-2 overflow-x-auto pb-0.5">
                  {photoPreviews.map((photo) => (
                    <a
                      key={photo.id}
                      href={resolvePhotoUrl(photo.href)}
                      target="_blank"
                      rel="noopener noreferrer"
                      className="group block w-28 shrink-0 overflow-hidden rounded-md border border-zinc-200/85 bg-zinc-100/70 shadow-sm transition hover:border-zinc-300"
                    >
                      <div className="aspect-[4/3]">
                        <img
                          src={resolvePhotoUrl(photo.href)}
                          alt={photo.title}
                          className="h-full w-full object-cover transition duration-200 group-hover:scale-[1.02]"
                        />
                      </div>
                    </a>
                  ))}
                </div>
                <a
                  href={primaryPhotoHref}
                  target="_blank"
                  rel="noopener noreferrer"
                  className={buttonVariants({
                    variant: "outline",
                    size: "sm",
                    className: "border-zinc-300/85 bg-white text-zinc-700 hover:bg-zinc-50/90",
                  })}
                >
                  {photos.length > 1 ? "Bekijk alle foto's" : "Bekijk foto"}
                </a>
              </div>
            )}
          </section>

          <section className={cardShellClass}>
            <h2 className={compactHeadingClass}>Klantvraag</h2>
            <p className="mt-2 whitespace-pre-wrap text-[12px] font-medium leading-[1.5] text-zinc-600">
              {projectDescription || publicNotes || "Geen toelichting beschikbaar."}
            </p>
          </section>

          <section className={cardShellClass}>
            <div className="mb-1.5 flex items-center gap-2">
              <History className="h-3.5 w-3.5 text-zinc-500" />
              <h2 className={compactHeadingClass}>Historie</h2>
            </div>
            <ol className="space-y-1">
              {runs.length === 0 ? (
                <li className="text-[13px] text-zinc-700">Nog geen gebeurtenissen.</li>
              ) : (
                runs.slice(0, 8).map((run) => (
                  <li key={run.id} className="rounded-md border border-zinc-200/70 px-2.5 py-1.5 text-[12px]">
                    <p className="font-semibold leading-tight text-zinc-900">{tStatus(run.status)}</p>
                    <p className="text-[11px] font-medium text-zinc-500">{formatDateTime(run.updated_at ?? run.created_at)}</p>
                  </li>
                ))
              )}
            </ol>
          </section>
        </div>

        <aside className="space-y-2.5">
          <section className={cardShellClass}>
            <h2 className={compactHeadingClass}>Workflow</h2>
            <div className="mt-2 space-y-2">
              <div className="rounded-md border border-zinc-200/70 p-2">
                <p className="text-[10px] font-semibold uppercase leading-none tracking-[0.05em] text-zinc-500">Huidige status</p>
                <div className="mt-1">
                  <StatusBadge status={latestRun?.status || lead.status}>
                    {tStatus(latestRun?.status || lead.status)}
                  </StatusBadge>
                </div>
              </div>
              <Button size="sm" className="w-full" onClick={() => void sendQuote()} disabled={isSending}>
                <Mail className="mr-1 h-3.5 w-3.5" /> {isSending ? "Versturen..." : "Offerte versturen"}
              </Button>
              <Link href={publicQuoteHref} target="_blank" className={buttonVariants({ variant: "outline", size: "sm", className: "w-full border-zinc-300/85 bg-white text-zinc-700 hover:bg-zinc-50/90" })}>
                <ExternalLink className="mr-1 h-3.5 w-3.5" /> Open klantlink
              </Link>
            </div>
          </section>

          <section className={cardShellClass}>
            <div className="mb-1.5 flex items-center gap-2">
              <CalendarClock className="h-3.5 w-3.5 text-zinc-500" />
              <h2 className={compactHeadingClass}>Opvolging & notitie</h2>
            </div>
            <form
              className="space-y-2"
              onSubmit={(event) => {
                event.preventDefault();
                void saveFollowup(new FormData(event.currentTarget));
              }}
            >
              <div>
                <label className="mb-1 block text-[10px] font-semibold uppercase leading-none tracking-[0.05em] text-zinc-500">Volgende stap</label>
                <input
                  name="next_action"
                  defaultValue={nextAction}
                  className="h-8 w-full rounded-md border border-zinc-300/85 px-2.5 text-[12px] font-medium text-zinc-700 focus:ring-2 focus:ring-primary/28 focus:outline-none"
                />
              </div>
              <div>
                <label className="mb-1 block text-[10px] font-semibold uppercase leading-none tracking-[0.05em] text-zinc-500">Gepland voor</label>
                <input
                  type="datetime-local"
                  name="next_action_at"
                  defaultValue={nextActionInput}
                  className="h-8 w-full rounded-md border border-zinc-300/85 px-2.5 text-[12px] font-medium text-zinc-700 focus:ring-2 focus:ring-primary/28 focus:outline-none"
                />
              </div>
              <div>
                <label className="mb-1 block text-[10px] font-semibold uppercase leading-none tracking-[0.05em] text-zinc-500">Interne notitie</label>
                <textarea
                  name="internal_notes"
                  defaultValue={internalNotes}
                  rows={3}
                  className="w-full rounded-md border border-zinc-300/85 px-2.5 py-2 text-[12px] font-medium text-zinc-700 focus:ring-2 focus:ring-primary/28 focus:outline-none"
                />
              </div>
              <Button size="sm" type="submit" className="w-full" disabled={isSavingFollowup}>
                <Clock3 className="mr-1 h-3.5 w-3.5" /> {isSavingFollowup ? "Opslaan..." : "Opslaan"}
              </Button>
            </form>
          </section>

          {actionMessage ? (
            <Alert>
              <AlertDescription>{actionMessage}</AlertDescription>
            </Alert>
          ) : null}
          {actionError ? (
            <Alert variant="destructive">
              <AlertDescription>{actionError}</AlertDescription>
            </Alert>
          ) : null}
        </aside>
      </div>
      <section className={cardShellClass}>
        <h2 className={compactHeadingClass}>{t("offers.detail.handoff.title")}</h2>
        <ul className="mt-2 space-y-1 text-[12px] font-medium text-zinc-600">
          <li className="flex items-center gap-1.5">
            <CheckCircle2 className="h-3.5 w-3.5 text-primary" aria-hidden />
            {t("offers.detail.handoff.steps.send_quote")}
          </li>
          <li className="flex items-center gap-1.5">
            <CheckCircle2 className="h-3.5 w-3.5 text-primary" aria-hidden />
            {t("offers.detail.handoff.steps.track_acceptance")}
          </li>
          <li className="flex items-center gap-1.5">
            <CheckCircle2 className="h-3.5 w-3.5 text-primary" aria-hidden />
            {t("offers.detail.handoff.steps.convert_to_job")}
          </li>
        </ul>
      </section>
    </section>
  );
}
