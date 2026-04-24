"use client";

import Link from "next/link";
import { ClipboardList } from "lucide-react";
import { type ReactNode } from "react";
import { DateFilter } from "@/components/shared/date-filter";
import { useSessionContext } from "@/components/shared/session-provider";
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
import { Button, buttonVariants } from "@/components/ui/button";
import { EmptyState } from "@/components/ui/empty-state";
import { PageHeader } from "@/components/ui/page-header";
import { Skeleton } from "@/components/ui/skeleton";
import { StatusBadge } from "@/components/ui/status-badge";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { useDateFilterQuery } from "@/hooks/use-date-filter-query";
import { useJobs } from "@/hooks/use-jobs";
import { t, tStatus } from "@/lib/i18n";
import { formatDateTime } from "@/lib/presentation";
import { isExecutionFlowStatus } from "@/lib/product-flow";
import { cn } from "@/lib/utils";
import type { JobListItem } from "@/types/jobs";

function WorkspacePanel({ className, children }: { className?: string; children: ReactNode }) {
  return <div className={cn("overflow-hidden rounded-xl border border-zinc-200/75 bg-white p-3 shadow-[0_1px_0_rgba(15,23,42,0.03)] sm:p-3.5", className)}>{children}</div>;
}

function klusLabel(job: JobListItem) {
  const n = job.notes?.trim();
  if (n) {
    return n.length > 90 ? `${n.slice(0, 87)}…` : n;
  }
  return job.lead_name || t("jobs.table.klus_fallback");
}

export default function JobsPage() {
  const session = useSessionContext();
  const { value: dateFilter, setValue: setDateFilter } = useDateFilterQuery();
  const jobsQuery = useJobs(session.isAuthenticated, dateFilter);
  const jobs = (jobsQuery.data ?? []).filter((job) => isExecutionFlowStatus(job.status));
  const scheduled = jobs.filter((job) => String(job.status ?? "").toLowerCase() === "scheduled").length;
  const inProgress = jobs.filter((job) => String(job.status ?? "").toLowerCase() === "in_progress").length;
  const done = jobs.filter((job) => String(job.status ?? "").toLowerCase() === "done").length;

  if (session.isLoading || (jobsQuery.isLoading && !jobsQuery.data)) {
    return (
      <div className="mx-auto w-full max-w-[min(1480px,100%)] space-y-2.5">
        <div className="space-y-1.5">
          <Skeleton className="h-3 w-16 rounded bg-zinc-100/90 motion-reduce:animate-none" />
          <Skeleton className="h-7 w-48 rounded bg-zinc-100/90 motion-reduce:animate-none" />
          <Skeleton className="h-4 w-full max-w-md rounded bg-zinc-100/90 motion-reduce:animate-none" />
        </div>
        <Skeleton className="h-[42px] w-full rounded-[11px] bg-zinc-100/90 motion-reduce:animate-none" />
        <WorkspacePanel>
          <div className="space-y-2">
            <Skeleton className="h-3 w-28 rounded bg-zinc-100/90 motion-reduce:animate-none" />
            <Skeleton className="h-[180px] w-full rounded-[8px] bg-zinc-100/90 motion-reduce:animate-none" />
          </div>
        </WorkspacePanel>
      </div>
    );
  }

  if (!session.isAuthenticated) {
    return (
      <Alert variant="destructive">
        <AlertTitle>{t("common.auth.not_logged_in")}</AlertTitle>
        <AlertDescription>{t("jobs.errors.not_logged_in_description")}</AlertDescription>
      </Alert>
    );
  }

  if (jobsQuery.error) {
    return (
      <Alert variant="destructive">
        <AlertTitle>{t("jobs.errors.load_failed_title")}</AlertTitle>
        <AlertDescription>
          <div className="space-y-3">
            <p>{t("jobs.errors.load_failed_description")}</p>
            <Button variant="outline" size="sm" onClick={() => void jobsQuery.refetch()}>
              {t("common.actions.retry")}
            </Button>
          </div>
        </AlertDescription>
      </Alert>
    );
  }

  return (
    <section className="mx-auto w-full max-w-[min(1480px,100%)] space-y-2.5">
      <PageHeader
        kicker={t("jobs.header.kicker")}
        title={t("jobs.header.title")}
        description={t("jobs.header.subtitle")}
      />

      <div className="overflow-hidden rounded-xl border border-zinc-200/75 bg-white shadow-[0_1px_0_rgba(15,23,42,0.03)]">
        <div className="grid grid-cols-1 divide-y divide-zinc-200/70 sm:grid-cols-3 sm:divide-x sm:divide-y-0">
          {[
            { label: t("jobs.kpi.scheduled"), value: scheduled, hint: t("jobs.kpi.scheduled_hint") },
            { label: t("jobs.kpi.in_progress"), value: inProgress, hint: t("jobs.kpi.in_progress_hint") },
            { label: t("jobs.kpi.done"), value: done, hint: t("jobs.kpi.done_hint") },
          ].map((item) => (
            <div
              key={item.label}
              className="flex min-h-[62px] flex-col justify-center gap-0.5 px-3 py-2 sm:min-h-0"
            >
              <p className="text-[10px] font-semibold uppercase leading-none tracking-[0.05em] text-zinc-500">{item.label}</p>
              <p className="text-[1.35rem] font-semibold leading-tight tracking-[-0.02em] text-zinc-900">{item.value}</p>
              <p className="text-[11px] font-medium leading-snug text-zinc-500">{item.hint}</p>
            </div>
          ))}
        </div>
      </div>
      <DateFilter value={dateFilter} onChange={setDateFilter} />

      {jobs.length === 0 ? (
        <EmptyState
          icon={ClipboardList}
          title={t("jobs.empty.title")}
          description={t("jobs.empty.description")}
          hint={t("jobs.empty.hint")}
        >
          <Link href="/quotes" className={buttonVariants({ size: "sm", className: "h-8 min-w-[7.5rem] rounded-md px-2.5 text-[12px] font-semibold" })}>
            {t("jobs.empty.link_quotes")}
          </Link>
          <Link
            href="/agenda"
            className={buttonVariants({
              variant: "outline",
              size: "sm",
              className: "h-8 min-w-[7.5rem] rounded-md border-zinc-300/85 bg-white px-2.5 text-[12px] font-semibold text-zinc-700 hover:bg-zinc-50/90",
            })}
          >
            {t("jobs.empty.link_agenda")}
          </Link>
        </EmptyState>
      ) : (
        <WorkspacePanel>
          <Table>
            <TableHeader className="[&_tr]:border-zinc-200/80">
              <TableRow className="border-zinc-200/80 hover:bg-transparent">
                <TableHead className="bg-zinc-50/75 text-[10px] font-semibold uppercase tracking-[0.05em] text-zinc-500">{t("jobs.table.klus")}</TableHead>
                <TableHead className="bg-zinc-50/75 text-[10px] font-semibold uppercase tracking-[0.05em] text-zinc-500">{t("jobs.table.status")}</TableHead>
                <TableHead className="bg-zinc-50/75 text-[10px] font-semibold uppercase tracking-[0.05em] text-zinc-500">{t("jobs.table.customer")}</TableHead>
                <TableHead className="bg-zinc-50/75 text-[10px] font-semibold uppercase tracking-[0.05em] text-zinc-500">{t("jobs.table.scheduled")}</TableHead>
                <TableHead className="bg-zinc-50/75 text-[10px] font-semibold uppercase tracking-[0.05em] text-zinc-500">{t("jobs.table.started")}</TableHead>
                <TableHead className="bg-zinc-50/75 text-[10px] font-semibold uppercase tracking-[0.05em] text-zinc-500">{t("jobs.table.finished")}</TableHead>
                <TableHead className="bg-zinc-50/75 text-right text-[10px] font-semibold uppercase tracking-[0.05em] text-zinc-500">{t("jobs.table.action")}</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {jobs.map((job) => (
                <TableRow key={job.id} className="border-zinc-100 hover:bg-zinc-50/70">
                  <TableCell className="max-w-[220px] whitespace-normal text-zinc-900">
                    <span className="text-[13px] font-semibold leading-snug">{klusLabel(job)}</span>
                  </TableCell>
                  <TableCell>
                    <StatusBadge status={job.status}>{tStatus(job.status)}</StatusBadge>
                  </TableCell>
                  <TableCell className="text-[12px] font-medium text-zinc-600">
                    {job.lead_name || t("jobs.table.unknown_customer")}
                  </TableCell>
                  <TableCell className="tabular-nums text-[12px] font-medium text-zinc-600">{formatDateTime(job.scheduled_at)}</TableCell>
                  <TableCell className="tabular-nums text-[12px] font-medium text-zinc-600">{formatDateTime(job.started_at)}</TableCell>
                  <TableCell className="tabular-nums text-[12px] font-medium text-zinc-600">{formatDateTime(job.done_at)}</TableCell>
                  <TableCell className="text-right">
                    <Link
                      href={`/quotes/${job.lead_id}`}
                      className="text-[12px] font-semibold text-primary hover:text-[color:var(--primary-hover)]"
                    >
                      {t("jobs.actions.view_details")}
                    </Link>
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
