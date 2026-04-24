"use client";

import Link from "next/link";
import { useSessionContext } from "@/components/shared/session-provider";
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import { PageHeader } from "@/components/ui/page-header";
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
import { usePipelineRuns } from "@/hooks/use-pipeline-runs";
import { t, tStatus } from "@/lib/i18n";
import { formatDateTime } from "@/lib/presentation";

export default function WorkflowsPage() {
  const session = useSessionContext();
  const canLoadRuns = session.isAuthenticated && Boolean(session.user?.tenant_id);
  const runsQuery = usePipelineRuns({
    tenantId: session.user?.tenant_id,
    enabled: canLoadRuns,
    limit: 100,
  });
  const runs = (runsQuery.data?.items ?? []).filter(
    (run) => run.tenant_id === session.user?.tenant_id,
  );

  if (session.isLoading || (runsQuery.isLoading && !runsQuery.data)) {
    return (
      <div className="app-page space-y-4">
        <Skeleton className="h-8 w-48 rounded-lg bg-zinc-100/90" />
        <Skeleton className="h-40 w-full rounded-xl bg-zinc-100/90" />
      </div>
    );
  }

  if (!session.isAuthenticated) {
    return (
      <Alert variant="destructive">
        <AlertTitle>{t("common.auth.not_logged_in")}</AlertTitle>
        <AlertDescription>{t("workflows.errors.not_logged_in_description")}</AlertDescription>
      </Alert>
    );
  }

  if (runsQuery.error) {
    return (
      <Alert variant="destructive">
        <AlertTitle>{t("workflows.errors.load_failed_title")}</AlertTitle>
        <AlertDescription>
          <div className="space-y-3">
            <p>{t("workflows.errors.load_failed_description")}</p>
            <Button variant="outline" size="sm" onClick={() => void runsQuery.refetch()}>
              {t("common.actions.retry")}
            </Button>
          </div>
        </AlertDescription>
      </Alert>
    );
  }

  return (
    <section className="app-page">
      <PageHeader kicker={t("workflows.header.kicker")} title={t("workflows.header.title")} />
      {runs.length === 0 ? (
        <Alert className="surface-card border-zinc-200/90">
          <AlertTitle>{t("workflows.empty.title")}</AlertTitle>
          <AlertDescription className="type-supporting">
            {t("workflows.empty.description", { tenant_id: session.user?.tenant_id ?? "—" })}
          </AlertDescription>
        </Alert>
      ) : (
        <div className="surface-card overflow-hidden p-4 sm:p-5">
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>{t("workflows.table.run")}</TableHead>
                <TableHead>{t("workflows.table.lead")}</TableHead>
                <TableHead>{t("workflows.table.status")}</TableHead>
                <TableHead>{t("workflows.table.created")}</TableHead>
                <TableHead>{t("offers.list.table.updated")}</TableHead>
                <TableHead className="text-right">{t("workflows.table.action")}</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {runs.map((run) => (
                <TableRow key={run.id}>
                  <TableCell className="font-medium">#{run.id}</TableCell>
                  <TableCell>{run.lead_id}</TableCell>
                  <TableCell>
                    <StatusBadge status={run.status}>{tStatus(run.status)}</StatusBadge>
                  </TableCell>
                  <TableCell>{formatDateTime(run.created_at)}</TableCell>
                  <TableCell>{formatDateTime(run.updated_at ?? run.completed_at)}</TableCell>
                  <TableCell className="text-right">
                    <div className="inline-flex items-center gap-3">
                      <Link
                        href={`/workflows/${run.id}`}
                        className="text-sm font-medium text-primary hover:text-primary/80"
                      >
                        {t("workflows.actions.open_run")}
                      </Link>
                      <Link
                        href={`/customers/${run.lead_id}`}
                        className="text-sm font-medium text-primary hover:text-primary/80"
                      >
                        {t("workflows.actions.open_lead")}
                      </Link>
                      <Link
                        href={`/quotes/${run.lead_id}`}
                        className="text-sm font-medium text-primary hover:text-primary/80"
                      >
                        {t("dashboard.activity.actions.open_offer")}
                      </Link>
                    </div>
                  </TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        </div>
      )}
    </section>
  );
}
