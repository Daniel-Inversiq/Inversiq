"use client";

import Link from "next/link";
import { type ReactNode, useMemo } from "react";
import { DateFilter } from "@/components/shared/date-filter";
import { useSessionContext } from "@/components/shared/session-provider";
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import { EmptyState } from "@/components/ui/empty-state";
import { PageHeader } from "@/components/ui/page-header";
import { Skeleton } from "@/components/ui/skeleton";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { StatusBadge } from "@/components/ui/status-badge";
import { useDateFilterQuery } from "@/hooks/use-date-filter-query";
import { usePipelineRuns } from "@/hooks/use-pipeline-runs";
import { useTenantLeads } from "@/hooks/use-tenant-leads";
import { isDateInFilterRange } from "@/lib/date-filter";
import { buildReviewQueueRowsFromPipelineAndLeads } from "@/lib/offers/review-queue-summary";
import { t, tStatus } from "@/lib/i18n";
import { formatDateTime } from "@/lib/presentation";
import { cn } from "@/lib/utils";

function WorkspacePanel({ className, children }: { className?: string; children: ReactNode }) {
  return (
    <div className={cn("overflow-hidden rounded-xl border border-zinc-200/75 bg-white p-3 shadow-[0_1px_0_rgba(15,23,42,0.03)] sm:p-3.5", className)}>
      {children}
    </div>
  );
}

function reviewKpiBuckets(rows: { status: string }[]) {
  let required = 0;
  let failed = 0;
  for (const row of rows) {
    const s = String(row.status ?? "").toLowerCase();
    if (s === "review_required" || s === "needs_review") {
      required += 1;
    } else if (s.includes("failed")) {
      failed += 1;
    }
  }
  const flagged = Math.max(rows.length - required - failed, 0);
  return { required, failed, flagged };
}

export default function ReviewPage() {
  const session = useSessionContext();
  const { value: dateFilter, setValue: setDateFilter } = useDateFilterQuery();
  const tenantId = session.user?.tenant_id?.trim() ?? "";
  const canLoadTenantData = session.isAuthenticated && tenantId.length > 0;
  const runsQuery = usePipelineRuns({
    tenantId: canLoadTenantData ? tenantId : undefined,
    enabled: canLoadTenantData,
    limit: 100,
  });
  const leadsQuery = useTenantLeads(tenantId, canLoadTenantData, dateFilter);
  const runs = useMemo(
    () => (runsQuery.data?.items ?? []).filter((run) => run.tenant_id === tenantId),
    [runsQuery.data?.items, tenantId],
  );
  const queue = useMemo(() => {
    const leadsList = leadsQuery.data ?? [];
    return buildReviewQueueRowsFromPipelineAndLeads(runs, leadsList, tenantId).filter((row) =>
      isDateInFilterRange(row.createdAt, dateFilter),
    );
  }, [runs, leadsQuery.data, tenantId, dateFilter]);
  const { required, failed, flagged } = reviewKpiBuckets(queue);

  if (session.isLoading || ((runsQuery.isLoading && !runsQuery.data) || (leadsQuery.isLoading && !leadsQuery.data))) {
    return (
      <div className="mx-auto w-full max-w-[min(1480px,100%)] space-y-2.5">
        <div className="space-y-2">
          <Skeleton className="h-3 w-28 rounded-md bg-zinc-100/90" />
          <Skeleton className="h-8 w-64 max-w-full rounded-md bg-zinc-100/90" />
          <Skeleton className="h-4 w-full max-w-xl rounded-md bg-zinc-100/90" />
        </div>
        <Skeleton className="h-14 w-full rounded-xl bg-zinc-100/90" />
        <div className="h-[min(400px,50vh)] overflow-hidden rounded-xl border border-gray-200 bg-white p-6 shadow-sm">
          <Skeleton className="h-full w-full rounded-lg bg-zinc-100/80" />
        </div>
      </div>
    );
  }

  if (!session.isAuthenticated) {
    return (
      <Alert variant="destructive">
        <AlertTitle>{t("common.auth.not_logged_in")}</AlertTitle>
        <AlertDescription>{t("review_queue.errors.not_logged_in_description")}</AlertDescription>
      </Alert>
    );
  }

  if (runsQuery.error) {
    return (
      <div className="mx-auto w-full max-w-[min(1480px,100%)] space-y-2.5">
        <Alert variant="destructive">
          <AlertTitle>{t("review_queue.errors.load_failed_title")}</AlertTitle>
          <AlertDescription>
            <div className="space-y-3">
              <p className="type-supporting">{t("review_queue.errors.load_failed_description")}</p>
              <Button variant="outline" size="sm" onClick={() => void runsQuery.refetch()}>
                {t("common.actions.retry")}
              </Button>
            </div>
          </AlertDescription>
        </Alert>
      </div>
    );
  }

  return (
    <section className="mx-auto w-full max-w-[min(1480px,100%)] space-y-2.5">
      <PageHeader
        kicker={t("review_queue.header.kicker")}
        title={t("review_queue.header.title")}
        description={t("review_queue.header.subtitle")}
      />

      <div className="overflow-hidden rounded-xl border border-zinc-200/75 bg-white shadow-[0_1px_0_rgba(15,23,42,0.03)]">
        <div className="grid grid-cols-1 divide-y divide-zinc-200/70 sm:grid-cols-3 sm:divide-x sm:divide-y-0">
          {[
            { label: t("review_queue.kpi.review_required"), value: required },
            { label: t("review_queue.kpi.processing_failed"), value: failed },
            { label: t("review_queue.kpi.other_flags"), value: Math.max(flagged, 0) },
          ].map((item) => (
            <div
              key={item.label}
              className="flex min-h-[62px] flex-col justify-center gap-0.5 px-3 py-2 sm:min-h-0"
            >
              <p className="text-[10px] font-semibold uppercase leading-none tracking-[0.05em] text-zinc-500">{item.label}</p>
              <p className="text-[1.35rem] font-semibold leading-tight tracking-[-0.02em] text-zinc-900">{item.value}</p>
            </div>
          ))}
        </div>
      </div>
      <DateFilter value={dateFilter} onChange={setDateFilter} />

      {queue.length === 0 ? (
        <EmptyState
          title={t("review_queue.empty.title")}
          description={t("review_queue.empty.description")}
          hint={t("review_queue.empty.hint")}
        />
      ) : (
        <WorkspacePanel>
          <Table>
            <TableHeader className="[&_tr]:border-zinc-200/80">
              <TableRow className="border-zinc-200/80 hover:bg-transparent">
                <TableHead className="w-12 bg-zinc-50/75 text-[10px] font-semibold uppercase tracking-[0.05em] text-zinc-500">{t("review_queue.table.nr")}</TableHead>
                <TableHead className="bg-zinc-50/75 text-[10px] font-semibold uppercase tracking-[0.05em] text-zinc-500">{t("review_queue.table.customer")}</TableHead>
                <TableHead className="bg-zinc-50/75 text-[10px] font-semibold uppercase tracking-[0.05em] text-zinc-500">{t("review_queue.table.status")}</TableHead>
                <TableHead className="bg-zinc-50/75 text-[10px] font-semibold uppercase tracking-[0.05em] text-zinc-500">{t("review_queue.table.created")}</TableHead>
                <TableHead className="bg-zinc-50/75 text-[10px] font-semibold uppercase tracking-[0.05em] text-zinc-500">{t("review_queue.table.updated")}</TableHead>
                <TableHead className="bg-zinc-50/75 text-right text-[10px] font-semibold uppercase tracking-[0.05em] text-zinc-500">{t("review_queue.table.action")}</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {queue.map((row, index) => (
                <TableRow
                  key={row.runId > 0 ? `run-${row.runId}` : `lead-${row.leadId}`}
                  className="border-zinc-100 hover:bg-zinc-50/70"
                >
                  <TableCell className="tabular-nums text-[12px] font-medium text-zinc-600">{index + 1}</TableCell>
                  <TableCell className="text-[13px] font-semibold text-zinc-900">
                    {row.customerName.trim() || t("review_queue.table.customer_placeholder")}
                  </TableCell>
                  <TableCell>
                    <StatusBadge status={row.status}>{tStatus(row.status)}</StatusBadge>
                  </TableCell>
                  <TableCell className="tabular-nums text-[12px] font-medium text-zinc-600">{formatDateTime(row.createdAt)}</TableCell>
                  <TableCell className="tabular-nums text-[12px] font-medium text-zinc-600">{formatDateTime(row.updatedAt)}</TableCell>
                  <TableCell className="text-right">
                    <div className="inline-flex flex-wrap items-center justify-end gap-x-3 gap-y-1">
                      {row.runId > 0 ? (
                        <Link
                          href={`/workflows/${row.runId}`}
                          className="text-[12px] font-semibold text-primary hover:text-[color:var(--primary-hover)]"
                        >
                          {t("review_queue.actions.view_flow")}
                        </Link>
                      ) : null}
                      <Link
                        href={`/reviews/${row.leadId}`}
                        className="text-[12px] font-semibold text-primary hover:text-[color:var(--primary-hover)]"
                      >
                        {t("common.actions.open")}
                      </Link>
                    </div>
                  </TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        </WorkspacePanel>
      )}
    </section>
  );
}
