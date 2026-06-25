"use client";

import { ActivityFeed } from "@/components/dashboard/activity-feed";
import { useSessionContext } from "@/components/shared/session-provider";
import { KpiCards } from "@/components/dashboard/kpi-cards";
import { StatusTable } from "@/components/dashboard/status-table";
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";
import { useDashboardActivity } from "@/hooks/use-dashboard-activity";
import { useDashboardSummary } from "@/hooks/use-dashboard-summary";
import {
  ApiError,
  getApiBaseUrl,
  getLastApiDebugSnapshot,
} from "@/lib/api/client";
import { getNumberLocale, t } from "@/lib/i18n";

function getDashboardErrorMessage(error: unknown) {
  if (error instanceof ApiError) {
    if (error.status === 401) {
      return t("dashboard.errors.unauthenticated");
    }
    if (error.status === 403) {
      return t("dashboard.errors.forbidden");
    }
    if (error.code === "NETWORK_ERROR" || error.status === 0) {
      return t("dashboard.errors.network");
    }
    return `${error.message} (${error.status})`;
  }

  if (error instanceof Error) {
    return error.message;
  }

  return t("dashboard.errors.unknown");
}

function DashboardLoadingState() {
  return (
    <div className="space-y-3">
      <div className="space-y-2">
        <Skeleton className="h-4 w-32 rounded-md bg-slate-200" />
        <Skeleton className="h-8 w-64 rounded-md bg-slate-200" />
        <Skeleton className="h-4 w-[32rem] rounded-md bg-slate-200" />
      </div>
      <div className="grid gap-3 xl:grid-cols-4">
        <Skeleton className="h-20 rounded-md bg-slate-200" />
        <Skeleton className="h-20 rounded-md bg-slate-200" />
        <Skeleton className="h-20 rounded-md bg-slate-200" />
        <Skeleton className="h-20 rounded-md bg-slate-200" />
      </div>
      <div className="grid gap-3 xl:grid-cols-12">
        <Skeleton className="h-[300px] rounded-md bg-slate-200 xl:col-span-8" />
        <Skeleton className="h-[300px] rounded-md bg-slate-200 xl:col-span-4" />
      </div>
    </div>
  );
}

export function DashboardOverview() {
  const session = useSessionContext();
  const shouldFetchDashboard = session.isAuthenticated;
  const summaryQuery = useDashboardSummary({ enabled: shouldFetchDashboard });
  const activityQuery = useDashboardActivity({ enabled: shouldFetchDashboard });
  const hasError = Boolean(summaryQuery.error || activityQuery.error);
  const errorMessage = getDashboardErrorMessage(
    summaryQuery.error ?? activityQuery.error,
  );
  const debugSnapshot = getLastApiDebugSnapshot();
  const showDebugPanel =
    process.env.NODE_ENV !== "production" &&
    process.env.NEXT_PUBLIC_SHOW_DASHBOARD_DEBUG === "true";

  if (session.isLoading) {
    return <DashboardLoadingState />;
  }

  if (!session.isAuthenticated) {
    return (
      <Alert variant="destructive">
        <AlertTitle>{t("common.auth.not_logged_in")}</AlertTitle>
        <AlertDescription>
          {t("dashboard.errors.inactive_session")}
        </AlertDescription>
      </Alert>
    );
  }

  if (process.env.NODE_ENV !== "production" && summaryQuery.data) {
    console.debug("Dashboard summary response", summaryQuery.data);
  }
  if (process.env.NODE_ENV !== "production" && activityQuery.data) {
    console.debug("Dashboard activity response", activityQuery.data);
  }

  if (summaryQuery.isLoading || activityQuery.isLoading) {
    return <DashboardLoadingState />;
  }

  if (hasError) {
    return (
      <section className="space-y-3">
        <Alert variant="destructive">
          <AlertTitle>{t("dashboard.errors.load_failed_title")}</AlertTitle>
          <AlertDescription>
            <div className="space-y-3">
              <p>{errorMessage}</p>
              <Button
                variant="outline"
                size="sm"
                onClick={() => {
                  void summaryQuery.refetch();
                  void activityQuery.refetch();
                }}
              >
                {t("common.actions.retry")}
              </Button>
            </div>
          </AlertDescription>
        </Alert>
        {showDebugPanel ? (
          <Alert className="border-slate-200 bg-white">
            <AlertTitle>Dev debug</AlertTitle>
            <AlertDescription>
              <div className="space-y-1 text-xs text-slate-600">
                <p>API base URL: {getApiBaseUrl() || "(zelfde origin)"}</p>
                <p>
                  Auth status:{" "}
                  {session.isAuthenticated ? "logged in" : "not authenticated"}
                </p>
                <p>
                  Last API response:{" "}
                  {debugSnapshot
                    ? `${debugSnapshot.method} ${debugSnapshot.url} -> ${debugSnapshot.status} (${debugSnapshot.ok ? "ok" : "error"})`
                    : "none"}
                </p>
                {debugSnapshot?.payloadPreview ? (
                  <p className="line-clamp-2">
                    Payload: {debugSnapshot.payloadPreview}
                  </p>
                ) : null}
              </div>
            </AlertDescription>
          </Alert>
        ) : null}
      </section>
    );
  }

  if (!summaryQuery.data || !activityQuery.data) {
    return (
      <Alert className="border border-zinc-200/80 bg-white">
        <AlertTitle>{t("dashboard.empty.title")}</AlertTitle>
        <AlertDescription>
          {t("dashboard.empty.description")}
        </AlertDescription>
      </Alert>
    );
  }

  return (
    <section className="space-y-4">
      <header className="space-y-0">
        <p className="type-eyebrow-md text-zinc-600">{t("dashboard.header.kicker")}</p>
        <h1 className="type-page-title mt-0.5">{t("dashboard.header.title")}</h1>
        <p className="type-body-secondary mt-1 max-w-3xl text-zinc-600">{t("dashboard.header.subtitle")}</p>
      </header>

      <section className="space-y-1.5">
        <div className="flex items-baseline justify-between gap-3">
          <h2 className="type-section-title">{t("dashboard.kpi.section_title")}</h2>
          <p className="type-meta shrink-0 text-zinc-600">{t("dashboard.kpi.snapshot_label")}</p>
        </div>
        <KpiCards summary={summaryQuery.data} />
      </section>

      <section className="grid gap-4 xl:grid-cols-12">
        <div className="xl:col-span-8">
          <StatusTable summary={summaryQuery.data} />
        </div>
        <div className="xl:col-span-4">
          <ActivityFeed activity={activityQuery.data} />
        </div>
      </section>
      <div className="grid gap-4 lg:grid-cols-2">
        <div className="border-t border-zinc-200/95 pt-3">
          <p className="type-eyebrow text-zinc-600">{t("dashboard.meta.latest_revenue_point")}</p>
          <p className="type-body-secondary mt-1 leading-[1.45] text-zinc-600">
            {summaryQuery.data.revenue_series.at(-1)?.label ?? t("common.states.unknown")}
            :{" "}
            {new Intl.NumberFormat(getNumberLocale(), {
              style: "currency",
              currency: "EUR",
              maximumFractionDigits: 0,
            }).format(summaryQuery.data.revenue_series.at(-1)?.value ?? 0)}
          </p>
        </div>
        <div className="border-t border-zinc-200/95 pt-3">
          <p className="type-eyebrow text-zinc-600">{t("dashboard.meta.recent_events")}</p>
          <p className="type-body-secondary mt-1 leading-[1.45] text-zinc-600">
            {t("dashboard.meta.recent_events_count", {
              count: activityQuery.data.items.length,
            })}
          </p>
        </div>
      </div>
      {showDebugPanel ? (
        <div className="border-t border-dashed border-zinc-300/90 pt-3">
          <p className="type-eyebrow text-zinc-600">Dev debug</p>
          <div className="type-meta mt-1.5 space-y-1 text-zinc-600">
            <p>API base URL: {getApiBaseUrl() || "(zelfde origin)"}</p>
            <p>
              Auth status:{" "}
              {session.isAuthenticated ? "logged in" : "not authenticated"}
            </p>
            <p>
              Last API response:{" "}
              {debugSnapshot
                ? `${debugSnapshot.method} ${debugSnapshot.url} -> ${debugSnapshot.status} (${debugSnapshot.ok ? "ok" : "error"})`
                : "none"}
            </p>
            {debugSnapshot?.payloadPreview ? (
              <p className="line-clamp-2">Payload: {debugSnapshot.payloadPreview}</p>
            ) : null}
          </div>
        </div>
      ) : null}
    </section>
  );
}
