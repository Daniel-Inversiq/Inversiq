"use client";

import Link from "next/link";
import { useSessionContext } from "@/components/shared/session-provider";
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
import { StatusBadge } from "@/components/ui/status-badge";
import { Skeleton } from "@/components/ui/skeleton";
import { t, tStatus } from "@/lib/i18n";
import { usePipelineRunDebug } from "@/hooks/use-pipeline-run-debug";

type WorkflowRunDetailProps = {
  runId: number;
};

export function WorkflowRunDetail({ runId }: WorkflowRunDetailProps) {
  const session = useSessionContext();
  const debugQuery = usePipelineRunDebug(runId, session.isAuthenticated);

  if (!Number.isFinite(runId)) {
    return (
      <Alert variant="destructive">
        <AlertTitle>{t("workflow_detail.errors.invalid_run_id_title")}</AlertTitle>
        <AlertDescription>{t("workflow_detail.errors.invalid_run_id_description")}</AlertDescription>
      </Alert>
    );
  }

  if (session.isLoading || (debugQuery.isLoading && !debugQuery.data)) {
    return (
      <div className="space-y-3">
        <Skeleton className="h-10 w-80 rounded-xl" />
        <Skeleton className="h-36 w-full rounded-xl" />
        <Skeleton className="h-36 w-full rounded-xl" />
      </div>
    );
  }

  if (!session.isAuthenticated) {
    return (
      <Alert variant="destructive">
        <AlertTitle>{t("common.auth.not_logged_in")}</AlertTitle>
        <AlertDescription>{t("workflow_detail.errors.not_logged_in_description")}</AlertDescription>
      </Alert>
    );
  }

  if (debugQuery.error || !debugQuery.data) {
    return (
      <Alert variant="destructive">
        <AlertTitle>{t("workflow_detail.errors.load_failed_title")}</AlertTitle>
        <AlertDescription>
          {t("workflow_detail.errors.load_failed_description", { run_id: runId })}
        </AlertDescription>
      </Alert>
    );
  }

  const { run, summary } = debugQuery.data;

  return (
    <section className="space-y-5">
      <header className="space-y-0">
        <p className="type-eyebrow-md text-slate-500">{t("workflow_detail.header.kicker")}</p>
        <h1 className="type-page-title mt-0.5 text-slate-900">
          {t("workflow_detail.header.run", { run_id: run.id })}
        </h1>
        <p className="type-body-secondary mt-1 text-slate-500">
          {t("workflow_detail.header.meta", { tenant_id: run.tenant_id, lead_id: run.lead_id })}
        </p>
      </header>

      <div className="grid gap-4 lg:grid-cols-4">
        <article className="rounded-2xl border border-slate-200 bg-white p-4 shadow-sm">
          <p className="type-eyebrow text-slate-500">{t("workflow_detail.cards.status")}</p>
          <div className="mt-1.5">
            <StatusBadge status={run.status}>{tStatus(run.status)}</StatusBadge>
          </div>
        </article>
        <article className="rounded-2xl border border-slate-200 bg-white p-4 shadow-sm">
          <p className="type-eyebrow text-slate-500">{t("workflow_detail.cards.recoverability")}</p>
          <p className="mt-1 text-sm font-medium leading-[1.45] text-slate-900">
            {summary.recoverability || t("status.unknown")}
          </p>
        </article>
        <article className="rounded-2xl border border-slate-200 bg-white p-4 shadow-sm">
          <p className="type-eyebrow text-slate-500">{t("workflow_detail.cards.events")}</p>
          <p className="type-kpi-value mt-0.5 text-slate-900">{summary.event_count}</p>
        </article>
        <article className="rounded-2xl border border-slate-200 bg-white p-4 shadow-sm">
          <p className="type-eyebrow text-slate-500">{t("workflow_detail.cards.review")}</p>
          <p className="mt-1 text-sm font-semibold leading-[1.45] text-slate-900">
            {summary.review_recommended ? t("common.yes") : t("common.no")}
          </p>
        </article>
      </div>

      <section className="rounded-2xl border border-slate-200 bg-white p-4 shadow-sm">
        <h2 className="type-section-title text-slate-900">{t("workflow_detail.steps.title")}</h2>
        <dl className="mt-2 grid gap-2.5 text-sm leading-[1.45] text-slate-600 lg:grid-cols-2">
          <div>
            <dt className="type-eyebrow text-slate-500">{t("workflow_detail.steps.total")}</dt>
            <dd>{summary.total_steps}</dd>
          </div>
          <div>
            <dt className="type-eyebrow text-slate-500">{t("workflow_detail.steps.completed")}</dt>
            <dd>{summary.completed_steps}</dd>
          </div>
          <div>
            <dt className="type-eyebrow text-slate-500">{t("workflow_detail.steps.failed")}</dt>
            <dd>{summary.failed_steps}</dd>
          </div>
          <div>
            <dt className="type-eyebrow text-slate-500">{t("workflow_detail.steps.skipped")}</dt>
            <dd>{summary.skipped_steps}</dd>
          </div>
          <div>
            <dt className="type-eyebrow text-slate-500">{t("workflow_detail.steps.failure_step")}</dt>
            <dd>{run.failure_step || "—"}</dd>
          </div>
          <div>
            <dt className="type-eyebrow text-slate-500">{t("workflow_detail.steps.error_category")}</dt>
            <dd>{run.error_category || "—"}</dd>
          </div>
        </dl>
      </section>

      <Link href={`/quotes/${run.lead_id}`} className="inline-flex text-[13px] font-semibold text-primary hover:text-primary/80">
        {t("workflow_detail.actions.open_linked_offer")}
      </Link>
    </section>
  );
}
