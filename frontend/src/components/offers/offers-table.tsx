"use client";

import Link from "next/link";
import { type ReactNode } from "react";
import { ClipboardList, Database } from "lucide-react";
import { useSessionContext } from "@/components/shared/session-provider";
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
import { Button, buttonVariants } from "@/components/ui/button";
import { StatusBadge } from "@/components/ui/status-badge";
import { Skeleton } from "@/components/ui/skeleton";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { DateFilter } from "@/components/shared/date-filter";
import { useOffers } from "@/hooks/use-offers";
import { useDateFilterQuery } from "@/hooks/use-date-filter-query";
import { ApiError } from "@/lib/api/client";
import { isDateInFilterRange } from "@/lib/date-filter";
import { getNumberLocale, t, tStatus } from "@/lib/i18n";
import { formatDateTime } from "@/lib/presentation";
import { getBackendHref } from "@/lib/api/origin";
import { isOfferFlowStatus } from "@/lib/product-flow";
import { cn } from "@/lib/utils";

/** Matches dashboard workspace panels: white on canvas, border-led depth. */
function OfferWorkspacePanel({
  className,
  children,
}: {
  className?: string;
  children: ReactNode;
}) {
  return (
    <div className={cn("overflow-hidden rounded-xl border border-zinc-200/75 bg-white p-3 shadow-[0_1px_0_rgba(15,23,42,0.03)] sm:p-3.5", className)}>
      {children}
    </div>
  );
}

function formatEuro(value: number | null) {
  if (value === null) {
    return t("offers.list.amount.not_calculated");
  }
  return new Intl.NumberFormat(getNumberLocale(), {
    style: "currency",
    currency: "EUR",
    maximumFractionDigits: 2,
  }).format(value);
}

function getOffersErrorMessage(error: unknown) {
  if (error instanceof ApiError) {
    if (error.status === 401) {
      return t("offers.errors.unauthenticated");
    }
    if (error.status === 403) {
      return t("offers.errors.forbidden");
    }
    if (error.code === "NETWORK_ERROR" || error.status === 0) {
      return t("offers.errors.network");
    }
    return t("offers.errors.server_error");
  }
  return t("offers.errors.unknown");
}

export function OffersTable() {
  const session = useSessionContext();
  const { value: dateFilter, setValue: setDateFilter } = useDateFilterQuery();
  const offersQuery = useOffers(session.user?.tenant_id, dateFilter);
  const allOfferCandidates = offersQuery.data ?? [];
  const offers = (offersQuery.data ?? [])
    .filter((offer) => isOfferFlowStatus(offer.status))
    .filter((offer) => isDateInFilterRange(offer.updatedAt ?? offer.createdAt, dateFilter));
  const quoteAmountFailures = offers.filter((item) => item.amountLoadFailed).length;
  const sentCount = offers.filter((item) => {
    const status = item.status.toLowerCase();
    return status === "sent" || status === "viewed" || status === "pending_response";
  }).length;
  const activeDraftCount = offers.filter((item) => {
    const status = item.status.toLowerCase();
    return status === "new" || status === "processing" || status === "quote_ready" || status === "ready";
  }).length;
  const displayCustomerName = (value: string) => {
    const normalized = value.trim();
    return normalized || t("offers.list.unknown_customer");
  };

  if (session.isLoading) {
    return (
      <div className="space-y-2.5">
        <Skeleton className="h-[42px] w-full rounded-[11px] bg-zinc-100/90 motion-reduce:animate-none" />
        <OfferWorkspacePanel>
          <div className="space-y-2 p-3 sm:p-3.5">
            <Skeleton className="h-3 w-28 rounded bg-zinc-100/90 motion-reduce:animate-none" />
            <Skeleton className="h-[180px] w-full rounded-[8px] bg-zinc-100/90 motion-reduce:animate-none" />
          </div>
        </OfferWorkspacePanel>
      </div>
    );
  }

  if (offersQuery.isLoading && !offersQuery.data) {
    return (
      <div className="space-y-2.5">
        <Skeleton className="h-[42px] w-full rounded-[11px] bg-zinc-100/90 motion-reduce:animate-none" />
        <OfferWorkspacePanel>
          <div className="space-y-2 p-3 sm:p-3.5">
            <Skeleton className="h-3 w-28 rounded bg-zinc-100/90 motion-reduce:animate-none" />
            <Skeleton className="h-[180px] w-full rounded-[8px] bg-zinc-100/90 motion-reduce:animate-none" />
          </div>
        </OfferWorkspacePanel>
      </div>
    );
  }

  if (!session.isAuthenticated) {
    return (
      <Alert variant="destructive">
        <AlertTitle>{t("common.auth.not_logged_in")}</AlertTitle>
        <AlertDescription>
          {t("offers.errors.not_logged_in_description")}
        </AlertDescription>
      </Alert>
    );
  }

  if (offersQuery.error) {
    return (
      <Alert variant="destructive">
        <AlertTitle>{t("offers.errors.load_failed_title")}</AlertTitle>
        <AlertDescription>
          <div className="space-y-3">
            <p>{getOffersErrorMessage(offersQuery.error)}</p>
            <Button variant="outline" size="sm" onClick={() => void offersQuery.refetch()}>
              {t("common.actions.retry")}
            </Button>
          </div>
        </AlertDescription>
      </Alert>
    );
  }

  return (
    <div className="space-y-2.5">
      <DateFilter value={dateFilter} onChange={setDateFilter} />
      {offers.length === 0 ? (
        <OfferWorkspacePanel>
          <div className="border-b border-zinc-200/70 pb-3">
            <h3 className="text-[13px] font-semibold leading-tight tracking-[-0.02em] text-zinc-950">{t("offers.empty.title")}</h3>
            <p className="mt-1.5 max-w-xl text-[12px] font-medium leading-snug text-zinc-600">
              {t("offers.empty.description")}
            </p>
          </div>
          <div className="space-y-3 pt-3">
            <div className="grid gap-2.5 sm:grid-cols-2">
              <div className="flex gap-2.5 rounded-lg border border-zinc-200/70 p-3">
                <span className="mt-0.5 flex h-7 w-7 shrink-0 items-center justify-center rounded-md border border-zinc-200/80 bg-white text-zinc-500">
                  <ClipboardList className="size-4" aria-hidden />
                </span>
                <div className="min-w-0 space-y-1">
                  <p className="text-[10px] font-semibold uppercase leading-none tracking-[0.05em] text-zinc-500">
                    {t("offers.list.empty_help.what_you_see_title")}
                  </p>
                  <p className="text-[12px] font-medium leading-snug text-zinc-600">
                    {t("offers.list.empty_help.what_you_see_body")}
                  </p>
                </div>
              </div>
              <div className="flex gap-2.5 rounded-lg border border-zinc-200/70 p-3">
                <span className="mt-0.5 flex h-7 w-7 shrink-0 items-center justify-center rounded-md border border-zinc-200/80 bg-white text-zinc-500">
                  <Database className="size-4" aria-hidden />
                </span>
                <div className="min-w-0 space-y-1">
                  <p className="text-[10px] font-semibold uppercase leading-none tracking-[0.05em] text-zinc-500">
                    {t("offers.list.empty_help.data_check_title")}
                  </p>
                  <p className="text-[12px] font-medium leading-snug text-zinc-600">
                    {allOfferCandidates.length === 0
                      ? t("offers.list.empty_help.data_check_no_runs")
                      : t("offers.list.empty_help.data_check_outside_statuses")}
                  </p>
                </div>
              </div>
            </div>
            <div className="flex flex-wrap items-center gap-1.5 border-t border-zinc-200/70 pt-3">
              <Link
                href="/dashboard"
                className={buttonVariants({ size: "sm", className: "h-8 min-w-[7.5rem] rounded-md px-2.5 text-[12px] font-semibold" })}
              >
                {t("offers.list.empty_actions.open_dashboard")}
              </Link>
              <Link
                href="/review"
                className={buttonVariants({
                  variant: "outline",
                  size: "sm",
                  className: "h-8 min-w-[7.5rem] rounded-md border-zinc-300/85 bg-white px-2.5 text-[12px] font-semibold text-zinc-700 hover:bg-zinc-50/90",
                })}
              >
                {t("offers.list.empty_actions.open_review")}
              </Link>
            </div>
          </div>
        </OfferWorkspacePanel>
      ) : (
        <>
          <div className="overflow-hidden rounded-xl border border-zinc-200/75 bg-white shadow-[0_1px_0_rgba(15,23,42,0.03)]">
            <div className="grid grid-cols-1 divide-y divide-zinc-200/70 sm:grid-cols-3 sm:divide-x sm:divide-y-0">
              <div className="flex min-h-[62px] flex-col justify-center gap-0.5 px-3 py-2">
                <p className="text-[10px] font-semibold uppercase leading-none tracking-[0.05em] text-zinc-500">
                  {t("offers.list.stats.open_quotes")}
                </p>
                <p className="text-[1.35rem] font-semibold leading-tight tracking-[-0.02em] text-zinc-900 tabular-nums">
                  {offers.length}
                </p>
              </div>
              <div className="flex min-h-[62px] flex-col justify-center gap-0.5 px-3 py-2">
                <p className="text-[10px] font-semibold uppercase leading-none tracking-[0.05em] text-zinc-500">
                  {t("offers.list.stats.in_preparation")}
                </p>
                <p className="text-[1.35rem] font-semibold leading-tight tracking-[-0.02em] text-zinc-900 tabular-nums">
                  {activeDraftCount}
                </p>
              </div>
              <div className="flex min-h-[62px] flex-col justify-center gap-0.5 px-3 py-2">
                <p className="text-[10px] font-semibold uppercase leading-none tracking-[0.05em] text-zinc-500">
                  {t("offers.list.stats.sent_or_followed")}
                </p>
                <p className="text-[1.35rem] font-semibold leading-tight tracking-[-0.02em] text-zinc-900 tabular-nums">
                  {sentCount}
                </p>
              </div>
            </div>
        </div>
          {quoteAmountFailures > 0 ? (
            <Alert className="rounded-xl border border-zinc-200/75 bg-white shadow-[0_1px_0_rgba(15,23,42,0.03)]">
              <AlertTitle>{t("offers.partial.title")}</AlertTitle>
              <AlertDescription>
                {t("offers.partial.description", { count: quoteAmountFailures })}
              </AlertDescription>
            </Alert>
          ) : null}
          <OfferWorkspacePanel>
            <Table>
              <TableHeader className="[&_tr]:border-gray-200 [&_tr]:hover:bg-transparent">
                <TableRow className="border-gray-200 hover:bg-transparent">
                  <TableHead className="bg-gray-50 text-xs uppercase tracking-wide text-gray-500">
                    {t("offers.list.table.customer_project")}
                  </TableHead>
                  <TableHead className="bg-gray-50 text-xs uppercase tracking-wide text-gray-500">
                    {t("offers.list.table.status")}
                  </TableHead>
                  <TableHead className="bg-gray-50 text-xs uppercase tracking-wide text-gray-500">
                    {t("offers.list.table.value")}
                  </TableHead>
                  <TableHead className="bg-gray-50 text-xs uppercase tracking-wide text-gray-500">
                    {t("offers.list.table.created")}
                  </TableHead>
                  <TableHead className="bg-gray-50 text-xs uppercase tracking-wide text-gray-500">
                    {t("offers.list.table.updated")}
                  </TableHead>
                  <TableHead className="bg-gray-50 text-right text-xs uppercase tracking-wide text-gray-500">
                    {t("offers.list.table.action")}
                  </TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {offers.map((offer) => (
                  <TableRow key={`${offer.runId}-${offer.leadId}`} className="border-zinc-100 hover:bg-zinc-50/70">
                    <TableCell>
                      <div className="space-y-0.5">
                        <p className="text-[13px] font-semibold leading-tight text-zinc-900">
                          {displayCustomerName(offer.customerName)}
                        </p>
                        <p className="text-[12px] font-medium leading-snug text-zinc-600">
                          {offer.projectDescription || t("offers.list.project_details_unavailable")}
                        </p>
                      </div>
                    </TableCell>
                    <TableCell>
                      <StatusBadge status={offer.status}>{tStatus(offer.status)}</StatusBadge>
                    </TableCell>
                    <TableCell className="tabular-nums text-[12px] font-medium text-zinc-600">{formatEuro(offer.amount)}</TableCell>
                    <TableCell className="tabular-nums text-[12px] font-medium text-zinc-600">{formatDateTime(offer.createdAt)}</TableCell>
                    <TableCell className="tabular-nums text-[12px] font-medium text-zinc-600">{formatDateTime(offer.updatedAt)}</TableCell>
                    <TableCell className="text-right">
                      <div className="inline-flex flex-col items-end gap-1">
                        <Link
                          href={offer.detailHref}
                          className="text-[12px] font-semibold text-primary hover:text-[color:var(--primary-hover)]"
                        >
                          {t("offers.list.actions.open_offer")}
                        </Link>
                        <Link
                          href={getBackendHref(`/quotes/${offer.leadId}/html`)}
                          target="_blank"
                          className="text-[12px] font-medium text-zinc-600 hover:text-zinc-900"
                        >
                          {t("offers.list.actions.open_public_quote")}
                        </Link>
                      </div>
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          </OfferWorkspacePanel>
        </>
      )}
    </div>
  );
}
