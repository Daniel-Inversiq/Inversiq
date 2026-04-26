"use client";

import Link from "next/link";
import { type ReactNode, useEffect, useMemo, useState } from "react";
import {
  AlertCircle,
  ArrowRight,
  CheckCircle2,
  ChevronRight,
  ClipboardList,
  Copy,
  ExternalLink,
  Inbox,
  Link2,
} from "lucide-react";
import {
  IntakeLineChart,
  mapApiIntakeSeriesToChart,
  StatusStackedBar,
} from "@/components/dashboard/dashboard-charts";
import { useSessionContext } from "@/components/shared/session-provider";
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
import { Button, buttonVariants } from "@/components/ui/button";
import { HelpTooltip } from "@/components/ui/help-tooltip";
import { PageHeader } from "@/components/ui/page-header";
import { Skeleton } from "@/components/ui/skeleton";
import { StatusBadge } from "@/components/ui/status-badge";
import { useJobs } from "@/hooks/use-jobs";
import { useOperationalDashboard } from "@/hooks/use-operational-dashboard";
import { usePipelineRuns } from "@/hooks/use-pipeline-runs";
import { useTenantLeads } from "@/hooks/use-tenant-leads";
import { buildOfferRowsSummaryFromPipelineAndLeads } from "@/lib/offers/offer-rows-summary";
import { OFFERS_PIPELINE_FETCH_LIMIT } from "@/lib/offers/query-keys";
import { buildTenantIntakeUrl } from "@/lib/api/client";
import { getDateLocale, t, tStatus } from "@/lib/i18n";
import { cn } from "@/lib/utils";
import { formatDateTime } from "@/lib/presentation";
import { isExecutionFlowStatus, isOfferFlowStatus } from "@/lib/product-flow";
import type { JobListItem } from "@/types/jobs";
import type { OperationalKpiBlock } from "@/types/operational-dashboard";
import type { ReviewQueueRow, TenantLeadListItem } from "@/types/offers";

/** Avoids a flash of pulsing skeletons when requests resolve in a few milliseconds. */
const LOADING_INDICATOR_DELAY_MS = 130;

function useDelayedLoadingIndicator(loading: boolean, delayMs = LOADING_INDICATOR_DELAY_MS): boolean {
  const [show, setShow] = useState(false);
  useEffect(() => {
    if (!loading) {
      setShow(false);
      return;
    }
    const t = window.setTimeout(() => setShow(true), delayMs);
    return () => window.clearTimeout(t);
  }, [loading, delayMs]);
  return show;
}

function parseTime(value: string | null | undefined): number {
  if (!value) {
    return 0;
  }
  const t = new Date(value).getTime();
  return Number.isNaN(t) ? 0 : t;
}

/** Shared max width so header, KPIs, and grids align on one vertical edge. */
const DASHBOARD_PAGE_CLASS = "mx-auto w-full max-w-[min(1480px,100%)]";

const shortcutLinkClass =
  "h-7 gap-1 rounded-md px-2 text-[12px] font-semibold text-zinc-700 motion-safe:transition-[background-color,color,box-shadow] motion-safe:duration-[120ms] hover:bg-white hover:text-zinc-950 hover:shadow-[inset_0_0_0_1px_rgba(15,23,42,0.06)] focus-visible:ring-2 focus-visible:ring-primary/28 focus-visible:ring-offset-2 active:bg-zinc-100/80";

function DashboardShortcuts() {
  return (
    <nav
      aria-label={t("dashboard.operational.shortcuts.aria_label")}
      className="flex flex-wrap items-center gap-0.5 rounded-lg border border-zinc-200/65 bg-zinc-50/90 px-1 py-1 shadow-[inset_0_1px_0_rgba(255,255,255,0.65)] sm:gap-1"
    >
      <Link href="/review" className={cn(buttonVariants({ variant: "ghost", size: "sm" }), shortcutLinkClass)}>
        {t("dashboard.operational.shortcuts.review_queue")}
      </Link>
      <span className="hidden h-3.5 w-px shrink-0 bg-zinc-200/55 sm:block" aria-hidden />
      <Link href="/offertes" className={cn(buttonVariants({ variant: "ghost", size: "sm" }), shortcutLinkClass)}>
        {t("dashboard.operational.shortcuts.create_quote")}
      </Link>
      <span className="hidden h-3.5 w-px shrink-0 bg-zinc-200/55 sm:block" aria-hidden />
      <Link href="/jobs" className={cn(buttonVariants({ variant: "ghost", size: "sm" }), shortcutLinkClass)}>
        {t("dashboard.operational.shortcuts.open_jobs")}
      </Link>
    </nav>
  );
}

/** Softer than default `muted` — reads as structure, not a spotlight. */
function DashSkeleton({ className, ...props }: React.ComponentProps<typeof Skeleton>) {
  return <Skeleton className={cn("bg-zinc-100/90 motion-reduce:animate-none", className)} {...props} />;
}

function FadeIn({ children }: { children: ReactNode }) {
  const [visible, setVisible] = useState(false);
  useEffect(() => {
    const id = requestAnimationFrame(() => {
      requestAnimationFrame(() => setVisible(true));
    });
    return () => cancelAnimationFrame(id);
  }, []);
  return (
    <div
      className={cn(
        "motion-safe:transition-opacity motion-safe:duration-[180ms] motion-safe:ease-out",
        visible ? "opacity-100" : "opacity-0",
      )}
    >
      {children}
    </div>
  );
}

function KpiValueStatic() {
  return (
    <span
      className="inline-block h-5 min-w-[2ch] rounded bg-zinc-100/80 tabular-nums sm:h-6"
      aria-hidden
    />
  );
}

function DashboardHeaderSkeleton() {
  return (
    <div className="flex flex-col gap-2 sm:flex-row sm:items-end sm:justify-between sm:gap-4">
      <div className="min-w-0 space-y-2">
        <DashSkeleton className="h-2.5 w-24 rounded" />
        <DashSkeleton className="h-7 w-52 max-w-full rounded" />
        <DashSkeleton className="h-3.5 w-full max-w-md rounded" />
      </div>
      <DashSkeleton className="h-4 w-36 shrink-0 rounded" />
    </div>
  );
}

function SessionLoadingPlaceholder() {
  return (
    <div className="space-y-2.5">
      <DashboardHeaderSkeleton />
      <div className="overflow-hidden rounded-[11px] border border-zinc-300/85 bg-white p-2">
        <div className="grid grid-cols-1 gap-2 md:grid-cols-2 xl:grid-cols-4">
          {Array.from({ length: 4 }).map((_, i) => (
            <div key={i} className="flex min-h-[40px] flex-col justify-center gap-1 rounded-lg border border-zinc-200/80 bg-zinc-50/30 px-2.5 py-1.5 sm:min-h-[40px] sm:px-3 sm:py-2">
              <DashSkeleton className="h-2.5 w-14 rounded" />
              <DashSkeleton className="h-5 w-9 rounded sm:h-6" />
            </div>
          ))}
        </div>
      </div>
      <div className="flex flex-col gap-1.5 rounded-[11px] border border-zinc-300/85 bg-white px-2.5 py-1.5 sm:flex-row sm:items-center sm:gap-2.5">
        <div className="flex min-w-0 flex-1 items-center gap-2">
          <span className="h-7 w-7 shrink-0 rounded-md border border-zinc-300/85 bg-zinc-50/90" />
          <div className="min-w-0 flex-1 space-y-1">
            <DashSkeleton className="h-2 w-24 rounded" />
            <DashSkeleton className="h-3.5 w-full max-w-[min(100%,320px)] rounded" />
          </div>
        </div>
        <div className="flex shrink-0 gap-2">
          <DashSkeleton className="h-7 w-[4.5rem] rounded-md" />
          <DashSkeleton className="h-7 w-[4.5rem] rounded-md" />
        </div>
      </div>
      <div className="grid grid-cols-1 gap-2 lg:grid-cols-[minmax(0,1fr)_360px] lg:items-start">
        <div className="min-w-0 overflow-hidden rounded-[11px] border border-zinc-300/85 bg-white">
          <div className="border-b border-zinc-300/75 px-3 py-2.5">
            <DashSkeleton className="h-2 w-20 rounded" />
            <DashSkeleton className="mt-2 h-4 w-48 max-w-full rounded" />
            <DashSkeleton className="mt-1.5 h-3 w-full max-w-md rounded" />
          </div>
          <div className="space-y-2.5 p-2.5 sm:p-3">
            <div>
              <DashSkeleton className="h-2.5 w-28 rounded" />
              <DashSkeleton className="mt-1 h-3 w-full max-w-xs rounded" />
              <DashSkeleton className="mt-1.5 h-[200px] w-full rounded-[8px]" />
            </div>
            <div className="border-t border-zinc-300/75 pt-2.5">
              <DashSkeleton className="h-2.5 w-32 rounded" />
              <DashSkeleton className="mt-1 h-3 w-full max-w-sm rounded" />
              <div className="mt-2 space-y-2">
                <DashSkeleton className="h-4 w-44 rounded" />
                <DashSkeleton className="h-2.5 w-full rounded-full" />
              </div>
            </div>
          </div>
        </div>
        <div className="flex min-w-0 flex-col gap-2">
          <div className="overflow-hidden rounded-[11px] border border-zinc-300/85 bg-white">
            <div className="border-b border-zinc-300/75 px-3 py-2">
              <div className="flex items-start justify-between gap-2">
                <div className="flex min-w-0 items-start gap-2">
                  <span className="mt-0.5 h-6 w-6 shrink-0 rounded-md border border-zinc-300/85 bg-white" />
                  <div className="min-w-0 space-y-1">
                    <DashSkeleton className="h-3.5 w-36 rounded" />
                    <DashSkeleton className="h-3 w-full max-w-[200px] rounded" />
                  </div>
                </div>
                <DashSkeleton className="h-5 w-7 shrink-0 rounded-[10px]" />
              </div>
            </div>
            <div className="space-y-1.5 px-2.5 py-2">
              <DashSkeleton className="h-[34px] w-full rounded-[8px]" />
              <DashSkeleton className="h-[34px] w-full rounded-[8px]" />
            </div>
            <div className="border-t border-zinc-300/75 px-3 py-2">
              <DashSkeleton className="h-3.5 w-28 rounded" />
            </div>
          </div>
          <div className="overflow-hidden rounded-[11px] border border-zinc-300/85 bg-white">
            <div className="flex flex-col gap-1 border-b border-zinc-300/75 px-3 py-2 sm:flex-row sm:items-start sm:justify-between sm:gap-2">
              <div className="min-w-0 space-y-1">
                <DashSkeleton className="h-2 w-16 rounded" />
                <DashSkeleton className="h-3.5 w-40 rounded" />
                <DashSkeleton className="mt-1 h-2.5 w-36 rounded" />
              </div>
              <div className="flex shrink-0 items-baseline gap-1.5 rounded-md border border-zinc-200/80 bg-zinc-50/90 px-2 py-0.5">
                <DashSkeleton className="h-2 w-16 rounded" />
                <DashSkeleton className="h-4 w-5 rounded" />
              </div>
            </div>
            <div className="px-3 py-2.5">
              <DashSkeleton className="h-3 w-full max-w-[280px] rounded" />
            </div>
          </div>
        </div>
      </div>
      <div className="grid grid-cols-1 gap-2 lg:grid-cols-2 lg:items-start">
        <div className="overflow-hidden rounded-[11px] border border-zinc-300/85 bg-white">
          <div className="border-b border-zinc-300/75 px-3 py-2">
            <div className="flex items-start justify-between gap-2">
              <div className="flex min-w-0 items-start gap-2">
                <span className="mt-0.5 h-6 w-6 shrink-0 rounded-md border border-zinc-300/85 bg-white" />
                <div className="min-w-0 space-y-1">
                  <DashSkeleton className="h-3.5 w-40 rounded" />
                  <DashSkeleton className="h-3 w-full max-w-[220px] rounded" />
                </div>
              </div>
              <DashSkeleton className="h-5 w-7 shrink-0 rounded-[10px]" />
            </div>
          </div>
          <div className="space-y-1.5 px-2.5 py-2">
            <DashSkeleton className="h-[34px] w-full rounded-[8px]" />
            <DashSkeleton className="h-[34px] w-full rounded-[8px]" />
          </div>
          <div className="border-t border-zinc-300/75 px-3 py-2">
            <DashSkeleton className="h-3.5 w-32 rounded" />
          </div>
        </div>
        <div className="overflow-hidden rounded-[11px] border border-zinc-300/85 bg-white">
          <div className="border-b border-zinc-300/75 px-3 py-2">
            <div className="flex items-start justify-between gap-2">
              <div className="flex min-w-0 items-start gap-2">
                <span className="mt-0.5 h-6 w-6 shrink-0 rounded-md border border-zinc-300/85 bg-white" />
                <div className="min-w-0 space-y-1">
                  <DashSkeleton className="h-3.5 w-44 rounded" />
                  <DashSkeleton className="h-3 w-full max-w-[220px] rounded" />
                </div>
              </div>
              <DashSkeleton className="h-5 w-7 shrink-0 rounded-[10px]" />
            </div>
          </div>
          <div className="space-y-1.5 px-2.5 py-2">
            <DashSkeleton className="h-[34px] w-full rounded-[8px]" />
            <DashSkeleton className="h-[34px] w-full rounded-[8px]" />
          </div>
          <div className="border-t border-zinc-300/75 px-3 py-2">
            <DashSkeleton className="h-3 w-full max-w-[200px] rounded" />
          </div>
        </div>
      </div>
    </div>
  );
}

const kpiCardInteractive =
  "motion-safe:transition-[border-color,box-shadow,background-color] motion-safe:duration-[150ms] motion-safe:ease-out hover:border-zinc-300/80 hover:bg-zinc-50/40 hover:shadow-[0_1px_0_rgba(15,23,42,0.04)] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary/25 focus-visible:ring-offset-2";

function KpiStrip({
  items,
}: {
  items: {
    label: string;
    value: ReactNode;
    hint?: string;
    context?: ReactNode;
    href?: string;
    ariaGoTo?: string;
    /** Short inline help (“?”); rendered outside the card link so the trigger stays valid. */
    contextHelp?: string;
  }[];
}) {
  return (
    <div className="grid grid-cols-1 items-stretch gap-2.5 md:grid-cols-2 xl:grid-cols-4">
      {items.map((item) => {
        const body = (
          <>
            <div className="flex items-start justify-between gap-2">
              <div className="type-kpi-value text-[1.5rem] sm:text-[1.65rem]">
                {item.value}
              </div>
              {item.href ? (
                <ChevronRight
                  className="mt-0.5 h-3.5 w-3.5 shrink-0 text-zinc-400 opacity-0 transition-[opacity,transform] duration-[150ms] motion-reduce:transition-none group-hover:translate-x-0.5 group-hover:opacity-100"
                  aria-hidden
                />
              ) : null}
            </div>
            <div className="flex items-center gap-1.5">
              <p className="type-kicker min-w-0 flex-1 text-zinc-600">{item.label}</p>
              {item.contextHelp ? (
                <span className="pointer-events-auto shrink-0" onPointerDown={(e) => e.stopPropagation()}>
                  <HelpTooltip content={item.contextHelp} />
                </span>
              ) : null}
            </div>
            {item.hint || item.context ? (
              <div className="mt-0.5 space-y-0.5">
                {item.hint ? (
                  <p className="text-[11px] font-medium leading-snug text-zinc-500/95">{item.hint}</p>
                ) : null}
                {item.context ? (
                  <p className="text-[10px] font-medium leading-snug text-zinc-500/75">{item.context}</p>
                ) : null}
              </div>
            ) : null}
          </>
        );

        const shellClass = cn(
          "group relative flex h-full min-h-[5rem] flex-col gap-1 surface-card p-3 sm:min-h-[5.25rem] sm:p-3.5",
          item.href ? ["cursor-pointer", kpiCardInteractive] : "cursor-default",
        );

        if (item.href) {
          return (
            <div key={item.label} className={shellClass}>
              <Link
                href={item.href}
                className="absolute inset-0 z-0 rounded-[inherit] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary/25 focus-visible:ring-offset-2"
                aria-label={item.ariaGoTo}
              >
                <span className="sr-only">{item.ariaGoTo}</span>
              </Link>
              <div className="relative z-[1] flex flex-col gap-1 pointer-events-none">{body}</div>
            </div>
          );
        }

        return (
          <div key={item.label} className={shellClass}>
            {body}
          </div>
        );
      })}
    </div>
  );
}

function kpiContextNewRequests(k: OperationalKpiBlock | undefined): ReactNode {
  if (!k || k.inflow_last_7d === undefined) {
    return null;
  }
  const parts: string[] = [t("dashboard.operational.kpi.context_period_new", { count: k.inflow_last_7d })];
  const d = k.inflow_delta;
  if (d !== undefined) {
    if (d > 0) {
      parts.push(t("dashboard.operational.kpi.context_delta_up", { n: d }));
    } else if (d < 0) {
      parts.push(t("dashboard.operational.kpi.context_delta_down", { n: Math.abs(d) }));
    } else {
      parts.push(t("dashboard.operational.kpi.context_stable"));
    }
  }
  return parts.join(" · ");
}

function kpiContextOpenQuotes(k: OperationalKpiBlock | undefined): ReactNode {
  if (!k || k.touched_last_7d === undefined) {
    return null;
  }
  const parts: string[] = [
    t("dashboard.operational.kpi.context_quotes_touched", { count: k.touched_last_7d }),
  ];
  const d = k.touched_delta;
  if (d !== undefined) {
    if (d > 0) {
      parts.push(t("dashboard.operational.kpi.context_delta_up", { n: d }));
    } else if (d < 0) {
      parts.push(t("dashboard.operational.kpi.context_delta_down", { n: Math.abs(d) }));
    } else {
      parts.push(t("dashboard.operational.kpi.context_stable"));
    }
  }
  return parts.join(" · ");
}

function kpiContextActiveJobs(k: OperationalKpiBlock | undefined): ReactNode {
  if (!k || k.updated_last_7d === undefined) {
    return null;
  }
  const parts: string[] = [
    t("dashboard.operational.kpi.context_jobs_updated", { count: k.updated_last_7d }),
  ];
  const d = k.updated_delta;
  if (d !== undefined) {
    if (d > 0) {
      parts.push(t("dashboard.operational.kpi.context_delta_up", { n: d }));
    } else if (d < 0) {
      parts.push(t("dashboard.operational.kpi.context_delta_down", { n: Math.abs(d) }));
    } else {
      parts.push(t("dashboard.operational.kpi.context_stable"));
    }
  }
  return parts.join(" · ");
}

function kpiContextReview(k: OperationalKpiBlock | undefined): ReactNode {
  if (!k || !k.high_urgency || k.high_urgency <= 0) {
    return null;
  }
  return t("dashboard.operational.kpi.context_review_urgency", { count: k.high_urgency });
}

function KpiValueSkeleton({ className }: { className?: string }) {
  return <DashSkeleton className={className ?? "h-5 min-w-[2ch] rounded-md sm:h-6"} />;
}

function PanelCountStatic() {
  return (
    <span
      className="inline-flex min-h-[22px] min-w-[1.5rem] items-center justify-center rounded-lg bg-zinc-100/85"
      aria-hidden
    />
  );
}

function ListPanelRowsSkeleton({ showPulse }: { showPulse: boolean }) {
  return (
    <div className="px-0.5 py-1">
      <ul className="divide-y divide-zinc-200/70">
        {Array.from({ length: 2 }).map((_, i) => (
          <li key={i}>
            <div className="flex items-center justify-between gap-2 px-1.5 py-1">
              <div className="min-w-0 flex-1 space-y-1 py-0.5">
                {showPulse ? (
                  <>
                    <DashSkeleton className="h-3.5 max-w-[min(100%,220px)] rounded" />
                    <DashSkeleton className="h-2.5 max-w-[140px] rounded" />
                  </>
                ) : (
                  <>
                    <div className="h-3.5 max-w-[min(100%,220px)] rounded bg-zinc-100/75" />
                    <div className="h-2.5 max-w-[140px] rounded bg-zinc-100/65" />
                  </>
                )}
              </div>
              {showPulse ? (
                <DashSkeleton className="h-5 w-[3.25rem] shrink-0 rounded-[6px]" />
              ) : (
                <span className="h-5 w-[3.25rem] shrink-0 rounded-[6px] bg-zinc-100/80" aria-hidden />
              )}
            </div>
          </li>
        ))}
      </ul>
    </div>
  );
}

function WhatsappGlyph({ className }: { className?: string }) {
  return (
    <svg
      viewBox="0 0 24 24"
      className={className}
      aria-hidden
      focusable="false"
      fill="currentColor"
    >
      <path d="M17.472 14.382c-.297-.149-1.758-.867-2.03-.967-.273-.099-.471-.148-.67.15-.197.297-.767.966-.94 1.164-.173.199-.347.223-.644.075-.297-.15-1.255-.463-2.39-1.475-.883-.788-1.48-1.761-1.653-2.059-.173-.297-.018-.458.13-.606.134-.133.298-.347.446-.52.149-.174.198-.298.298-.497.099-.198.05-.371-.025-.52-.075-.149-.669-1.612-.916-2.207-.242-.579-.487-.5-.669-.51-.173-.008-.371-.01-.57-.01-.198 0-.52.074-.792.372-.272.297-1.04 1.016-1.04 2.479 0 1.462 1.065 2.875 1.213 3.074.149.198 2.096 3.2 5.077 4.487.709.306 1.262.489 1.694.625.712.227 1.36.195 1.871.118.571-.085 1.758-.719 2.006-1.413.248-.694.248-1.289.173-1.413-.074-.124-.272-.198-.57-.347m-5.421 7.403h-.004a9.87 9.87 0 01-5.031-1.378l-.361-.214-3.741.982.998-3.648-.235-.374a9.86 9.86 0 01-1.51-5.26c.001-5.45 4.436-9.884 9.888-9.884 2.64 0 5.122 1.03 6.988 2.898a9.825 9.825 0 012.893 6.994c-.003 5.45-4.435 9.884-9.885 9.884m8.413-18.297A11.815 11.815 0 0012.05 0C5.495 0 .16 5.335.157 11.892c0 2.096.547 4.142 1.588 5.945L.057 24l6.305-1.654a11.882 11.882 0 005.683 1.448h.005c6.554 0 11.89-5.335 11.893-11.893a11.821 11.821 0 00-3.48-8.413z" />
    </svg>
  );
}

function intakeUrlPresentation(url: string): { hostLine: string; pathLine: string | null } {
  try {
    if (/^https?:\/\//i.test(url)) {
      const u = new URL(url);
      const path = `${u.pathname}${u.search}`;
      return {
        hostLine: u.host,
        pathLine: path.length > 0 && path !== "/" ? path : null,
      };
    }
  } catch {
    // ignore
  }
  const trimmed = url.length > 64 ? `${url.slice(0, 60)}…` : url;
  return { hostLine: trimmed, pathLine: null };
}

function IntakeCompact({
  intakeUrl,
  copied,
  onCopy,
}: {
  intakeUrl: string;
  copied: boolean;
  onCopy: () => void;
}) {
  const { hostLine, pathLine } = intakeUrlPresentation(intakeUrl);
  const whatsappPrefill = t("dashboard.operational.intake.whatsapp_prefill", { url: intakeUrl });
  const whatsappHref = `https://wa.me/?text=${encodeURIComponent(whatsappPrefill)}`;

  return (
    <div className="surface-card flex flex-col gap-2.5 rounded-xl px-3 py-2.5 sm:flex-row sm:items-center sm:justify-between sm:gap-4">
      <div className="flex min-w-0 flex-1 items-start gap-2.5">
        <span className="mt-0.5 flex h-8 w-8 shrink-0 items-center justify-center rounded-lg border border-zinc-200/80 bg-zinc-50/90 text-zinc-600">
          <Link2 className="h-3.5 w-3.5" aria-hidden />
        </span>
        <div className="min-w-0 flex-1">
          <p className="text-[11px] font-semibold leading-tight text-zinc-500">{t("dashboard.operational.intake.label")}</p>
          <p className="mt-0.5 truncate text-[13px] font-semibold leading-snug tracking-[-0.015em] text-zinc-800" title={intakeUrl}>
            {hostLine}
          </p>
          {pathLine ? (
            <p className="mt-0.5 truncate font-mono text-[10px] font-medium leading-snug text-zinc-400" title={intakeUrl}>
              {pathLine}
            </p>
          ) : null}
          <p className="sr-only">{intakeUrl}</p>
        </div>
      </div>
      <div className="flex shrink-0 flex-wrap items-center gap-1.5 sm:justify-end">
        <div className="inline-flex items-center gap-1.5 rounded-lg border border-zinc-200/65 bg-zinc-50/70 p-0.5">
          <Button
            size="sm"
            type="button"
            className="h-7 gap-1 rounded-md border-0 px-2.5 text-[12px] font-semibold !bg-primary !text-primary-foreground shadow-none motion-safe:transition-[background-color,color] motion-safe:duration-[120ms] hover:!bg-[color:var(--primary-hover)] hover:!text-primary-foreground focus-visible:ring-2 focus-visible:ring-primary/30 focus-visible:ring-offset-1 [&_svg]:!text-primary-foreground"
            onClick={() => void onCopy()}
          >
            <Copy className="h-3 w-3" aria-hidden />
            {t("common.actions.copy_link")}
          </Button>
          <Link
            href={intakeUrl}
            target="_blank"
            rel="noopener noreferrer"
            className={buttonVariants({
              variant: "outline",
              size: "sm",
              className:
                "h-7 gap-1 rounded-md border-zinc-200/80 bg-white px-2.5 text-[12px] font-semibold text-zinc-800 shadow-none hover:bg-white hover:text-zinc-950",
            })}
          >
            <ExternalLink className="h-3 w-3" aria-hidden />
            {t("common.actions.open")}
          </Link>
          <a
            href={whatsappHref}
            target="_blank"
            rel="noopener noreferrer"
            title={t("dashboard.operational.intake.whatsapp_aria")}
            aria-label={t("dashboard.operational.intake.whatsapp_aria")}
            className={buttonVariants({
              variant: "outline",
              size: "icon-sm",
              className:
                "h-7 w-7 shrink-0 rounded-md border-zinc-200/80 bg-white text-primary hover:bg-zinc-50 hover:text-[color:var(--primary-hover)]",
            })}
          >
            <WhatsappGlyph className="h-3.5 w-3.5" />
          </a>
        </div>
        <span
          className={cn(
            "min-w-[4.5rem] text-right text-[10px] font-semibold leading-none text-primary motion-safe:transition-opacity motion-safe:duration-[150ms]",
            copied ? "opacity-100" : "opacity-0",
          )}
          aria-live="polite"
        >
          {copied ? t("common.actions.copied") : "\u00a0"}
        </span>
      </div>
    </div>
  );
}

function attentionFriendlyStatus(status: string | null | undefined): string {
  const u = (status ?? "").trim().toUpperCase();
  if (u === "NEEDS_REVIEW" || u === "REVIEW_REQUIRED") {
    return t("dashboard.operational.attention.badge_needs_review");
  }
  if (u === "FAILED" || u === "PROCESSING_FAILED" || u === "ERROR" || u === "UNCERTAIN") {
    return t("dashboard.operational.attention.badge_missing_details");
  }
  if (u === "FLAGGED_DAMAGE") {
    return t("dashboard.operational.attention.badge_check_photos");
  }
  return tStatus(status);
}

function ListRow({
  href,
  primary,
  secondary,
  tertiary,
  badge,
  emphasis,
}: {
  href: string;
  primary: string;
  secondary: string | null;
  /** Extra line (e.g. timestamp) — attention rows use issue summary in `secondary`. */
  tertiary?: string | null;
  badge?: ReactNode;
  emphasis?: "none" | "attention_high" | "attention_mid";
}) {
  return (
    <Link
      href={href}
      className={cn(
        "group motion-interactive flex items-start justify-between gap-2 rounded-md border border-transparent px-1.5 py-1.5 -mx-1.5 motion-safe:transition-[background-color,border-color] motion-safe:duration-[130ms] hover:border-zinc-200/70 hover:bg-zinc-950/[0.03] active:bg-zinc-950/[0.05] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary/22 focus-visible:ring-offset-2",
        emphasis === "attention_high" && "border-l-2 border-l-rose-300/85 bg-rose-50/30 pl-2",
        emphasis === "attention_mid" && "border-l-2 border-l-amber-300/80 bg-amber-50/25 pl-2",
      )}
    >
      <div className="min-w-0 flex-1 space-y-0">
        <p className="truncate text-[13px] font-semibold leading-tight tracking-[-0.01em] text-zinc-900 group-hover:text-zinc-950">
          {primary}
        </p>
        {secondary ? (
          <p className="truncate text-[11.5px] font-medium leading-snug text-zinc-600">{secondary}</p>
        ) : null}
        {tertiary ? (
          <p className="type-meta truncate text-[10px] tabular-nums text-zinc-500/90">{tertiary}</p>
        ) : null}
      </div>
      <div className="flex shrink-0 items-center gap-1 self-start pt-0.5">
        {badge}
        <ChevronRight
          className="h-3.5 w-3.5 shrink-0 text-zinc-400 opacity-0 transition-[opacity,transform] duration-[150ms] motion-reduce:transition-none group-hover:translate-x-0.5 group-hover:opacity-70"
          aria-hidden
        />
      </div>
    </Link>
  );
}

function OperationalPanel({
  icon: Icon,
  title,
  description,
  count,
  children,
  footer,
  emphasis,
  variant = "default",
}: {
  icon: React.ComponentType<{ className?: string }>;
  title: string;
  description: string;
  count: ReactNode;
  children: ReactNode;
  footer: ReactNode;
  emphasis?: boolean;
  variant?: "default" | "attention";
}) {
  const isAttention = variant === "attention";
  return (
    <section
      className={
        isAttention
          ? `flex min-h-0 flex-col overflow-hidden rounded-xl border border-zinc-200/75 bg-white shadow-[0_1px_0_rgba(15,23,42,0.03)] motion-safe:transition-[border-color,box-shadow] motion-safe:duration-200 motion-safe:ease-out ${
              emphasis ? "ring-1 ring-rose-200/45" : ""
            }`
          : "flex min-h-0 flex-col overflow-hidden rounded-xl border border-zinc-200/75 bg-white shadow-[0_1px_0_rgba(15,23,42,0.03)] motion-safe:transition-[border-color,box-shadow] motion-safe:duration-200 motion-safe:ease-out"
      }
    >
      <div className="border-b border-zinc-200/65 bg-white px-3 py-2">
        <div className="flex items-start justify-between gap-2">
          <div className="flex min-w-0 items-start gap-2">
            <span
              className={
                isAttention
                  ? "mt-px flex h-6 w-6 shrink-0 items-center justify-center rounded-md bg-rose-50 text-rose-700 ring-1 ring-rose-200/55"
                  : "mt-0.5 flex h-6 w-6 shrink-0 items-center justify-center rounded-md border border-zinc-200/80 bg-white text-zinc-600"
              }
            >
              <Icon className={isAttention ? "h-3 w-3" : "h-3 w-3"} aria-hidden />
            </span>
            <div className="min-w-0 space-y-0.5">
              <h3 className="text-[13px] font-semibold leading-[1.25] tracking-[-0.02em] text-zinc-950">{title}</h3>
              <p className="type-body-secondary text-[12px] leading-[1.4] text-zinc-500">{description}</p>
            </div>
          </div>
          <span
            className={
              emphasis
                ? "inline-flex min-h-[22px] min-w-[1.5rem] shrink-0 items-center justify-center rounded-lg bg-rose-700 px-2 text-[10px] font-semibold tabular-nums text-white"
                : "inline-flex min-h-[22px] min-w-[1.5rem] shrink-0 items-center justify-center rounded-lg bg-zinc-100/90 px-2 text-[10px] font-semibold tabular-nums text-zinc-800"
            }
          >
            {count}
          </span>
        </div>
      </div>
      <div className="flex flex-col px-2 py-0.5">{children}</div>
      <div
        className={
          isAttention
            ? "border-t border-zinc-200/65 bg-zinc-50/50 px-3 py-2"
            : "border-t border-zinc-200/65 px-3 py-2"
        }
      >
        {footer}
      </div>
    </section>
  );
}

function OutcomeSplit({
  acceptedCount,
  rejectedCount,
  acceptedRate,
  rejectedRate,
  totalRequests,
  days,
}: {
  acceptedCount: number;
  rejectedCount: number;
  acceptedRate: number;
  rejectedRate: number;
  totalRequests: number;
  days: number;
}) {
  if (totalRequests === 0) {
    return (
      <div className="rounded-lg border border-zinc-200/80 bg-zinc-50/40 px-3 py-2.5">
        <p className="text-[12px] font-semibold leading-snug text-zinc-700">
          {t("dashboard.operational.outcomes.empty_title")}
        </p>
        <p className="mt-1 text-[11px] leading-snug text-zinc-500">
          {t("dashboard.operational.outcomes.empty_description", { days })}
        </p>
      </div>
    );
  }

  const decidedTotal = acceptedCount + rejectedCount;
  const acceptedWidth = decidedTotal > 0 ? (acceptedCount / decidedTotal) * 100 : 0;
  const rejectedWidth = decidedTotal > 0 ? (rejectedCount / decidedTotal) * 100 : 0;

  return (
    <div className="rounded-lg border border-zinc-200/70 bg-zinc-50/30 px-3 py-2.5">
      <div className="flex items-start justify-between gap-3">
        <div>
          <p className="text-[10px] font-semibold uppercase tracking-[0.04em] text-zinc-500">
            {t("dashboard.operational.outcomes.accepted_label")}
          </p>
          <p className="mt-0.5 text-[22px] font-semibold leading-none tracking-[-0.02em] text-zinc-950">
            {acceptedRate.toFixed(1)}%
          </p>
        </div>
        <div className="text-right">
          <p className="text-[10px] font-semibold uppercase tracking-[0.04em] text-zinc-500">
            {t("dashboard.operational.outcomes.rejected_label")}
          </p>
          <p className="mt-0.5 text-[16px] font-semibold leading-none tabular-nums text-zinc-700">
            {rejectedRate.toFixed(1)}%
          </p>
        </div>
      </div>

      <div className="mt-2.5 h-2 w-full overflow-hidden rounded-full bg-zinc-200/85">
        {decidedTotal > 0 ? (
          <div className="flex h-full w-full">
            <div className="h-full" style={{ width: `${acceptedWidth}%`, backgroundColor: "#1F7A3E" }} />
            <div className="h-full bg-zinc-400/80" style={{ width: `${rejectedWidth}%` }} />
          </div>
        ) : (
          <div className="h-full w-full bg-zinc-300/70" />
        )}
      </div>

      <p className="mt-2 text-[11px] font-medium leading-snug text-zinc-600">
        {t("dashboard.operational.outcomes.counts_line", {
          accepted: acceptedCount,
          rejected: rejectedCount,
        })}
      </p>
      <p className="mt-0.5 text-[10px] leading-snug text-zinc-500">
        {t("dashboard.operational.outcomes.total_line", { total: totalRequests, days })}
      </p>
    </div>
  );
}

export default function DashboardPage() {
  const session = useSessionContext();
  const tenantId = session.user?.tenant_id?.trim() ?? "";
  const canLoadTenantData = session.isAuthenticated && tenantId.length > 0;
  const [copied, setCopied] = useState(false);
  const [intakeRange, setIntakeRange] = useState<7 | 14 | 30 | 90>(30);

  const leadsQuery = useTenantLeads(tenantId, canLoadTenantData);
  const jobsQuery = useJobs(canLoadTenantData);
  const runsQuery = usePipelineRuns({
    tenantId: canLoadTenantData ? tenantId : undefined,
    enabled: canLoadTenantData,
    limit: OFFERS_PIPELINE_FETCH_LIMIT,
  });
  const operationalQuery = useOperationalDashboard({
    tenantId,
    chartDays: intakeRange,
    enabled: canLoadTenantData,
  });

  const runs = useMemo(
    () => (runsQuery.data?.items ?? []).filter((run) => run.tenant_id === tenantId),
    [runsQuery.data?.items, tenantId],
  );
  const leads = leadsQuery.data ?? [];
  const filteredOffers = useMemo(() => {
    const rows = buildOfferRowsSummaryFromPipelineAndLeads(runs, leads);
    return rows.filter((offer) => isOfferFlowStatus(offer.status));
  }, [runs, leads]);

  const operational = operationalQuery.data;

  /** Initial fetch in flight — used for per-section skeletons, not a global page gate. (`isLoading` = pending + fetching in TanStack Query v5.) */
  const leadsBoot = canLoadTenantData && leadsQuery.isLoading;
  const jobsBoot = canLoadTenantData && jobsQuery.isLoading;
  const operationalBoot = canLoadTenantData && operationalQuery.isLoading;
  /** Status + intake from unified operational endpoint. */
  const statusDistributionBoot = operationalBoot || jobsBoot;
  const intakeChartBoot = operationalBoot;

  const leadsDelay = useDelayedLoadingIndicator(leadsBoot);
  const jobsDelay = useDelayedLoadingIndicator(jobsBoot);
  const operationalDelay = useDelayedLoadingIndicator(operationalBoot);
  const statusDelay = useDelayedLoadingIndicator(statusDistributionBoot);

  /** Omit pipeline-runs: non-critical for the rest of the overview if it fails alone. */
  const hasPartialError = Boolean(
    leadsQuery.error || jobsQuery.error || operationalQuery.error,
  );

  const intakeUrl = useMemo(() => buildTenantIntakeUrl(tenantId), [tenantId]);

  const filteredJobs = (jobsQuery.data ?? []).filter((job) => isExecutionFlowStatus(job.status));

  const reviewItems: ReviewQueueRow[] = useMemo(() => {
    if (!operational?.attention?.items) {
      return [];
    }
    return operational.attention.items.map((row) => ({
      runId: row.run_id,
      leadId: row.lead_id,
      tenantId: row.tenant_id,
      status: row.status,
      createdAt: row.created_at,
      updatedAt: row.updated_at,
      customerName: row.customer_name,
      primaryHref: row.primary_href,
      urgencyScore: row.urgency_score,
    }));
  }, [operational?.attention?.items]);

  const acceptedToday =
    operational && !jobsBoot
      ? operational.activity_strip.scheduled_jobs
      : filteredJobs.filter((job) => job.status.toLowerCase() === "scheduled").length;
  const hasQuoteAmountsInPipeline = filteredOffers.some((offer) => typeof offer.amount === "number");
  const amountTotal = filteredOffers.reduce(
    (sum, offer) => sum + (typeof offer.amount === "number" ? offer.amount : 0),
    0,
  );

  const statusDistribution = useMemo(() => {
    if (operational?.status_distribution?.length) {
      return operational.status_distribution;
    }
    const allStatusItems = [...filteredOffers, ...filteredJobs];
    const byStatus = new Map<string, number>();
    for (const item of allStatusItems) {
      const key = String(item.status ?? "").trim().toLowerCase();
      if (!key) {
        continue;
      }
      byStatus.set(key, (byStatus.get(key) ?? 0) + 1);
    }
    return Array.from(byStatus.entries())
      .sort((a, b) => b[1] - a[1])
      .slice(0, 6);
  }, [operational?.status_distribution, filteredOffers, filteredJobs]);

  const doneJobs = [...filteredJobs.filter((job) => String(job.status ?? "").toLowerCase() === "done")].sort(
    (a, b) => parseTime(b.done_at) - parseTime(a.done_at),
  );

  const intakeSeries = useMemo(() => {
    if (operational?.intake?.series?.length) {
      return mapApiIntakeSeriesToChart(operational.intake.series, intakeRange);
    }
    return [];
  }, [operational?.intake?.series, intakeRange]);

  const chartSummary = operational?.intake.summary ?? null;

  const handleCopyIntake = async () => {
    try {
      await navigator.clipboard.writeText(intakeUrl);
      setCopied(true);
      window.setTimeout(() => setCopied(false), 1500);
    } catch {
      setCopied(false);
    }
  };

  if (session.isLoading) {
    return (
      <div className={cn(DASHBOARD_PAGE_CLASS, "space-y-2.5")}>
        <SessionLoadingPlaceholder />
      </div>
    );
  }

  if (!session.isAuthenticated) {
    return (
      <div className={DASHBOARD_PAGE_CLASS}>
        <div className="surface-card p-4 shadow-[var(--shadow-surface)] sm:p-5">
          <Alert variant="destructive">
            <AlertTitle>{t("common.auth.not_logged_in")}</AlertTitle>
            <AlertDescription>{t("customers.errors.not_logged_in_description")}</AlertDescription>
          </Alert>
        </div>
      </div>
    );
  }

  const attentionTotal = operational?.attention.summary.total ?? reviewItems.length;
  const needsAttentionEmpty = attentionTotal === 0;
  const kpiBoot = operationalBoot;
  const pipelineRunsInView = operational?.activity_strip.pipeline_runs_in_view ?? runs.length;

  return (
    <div className={cn(DASHBOARD_PAGE_CLASS, "space-y-2.5")}>
      {hasPartialError ? (
        <Alert
          variant="default"
          className="border-zinc-200/75 bg-zinc-50/65 text-zinc-800 shadow-[0_1px_0_rgba(15,23,42,0.02)]"
        >
          <AlertCircle className="size-4 text-zinc-500" aria-hidden />
          <AlertTitle className="text-[13px] font-semibold leading-snug text-zinc-800">
            {t("dashboard.operational.errors.load_failed_title")}
          </AlertTitle>
          <AlertDescription className="flex flex-col gap-3 text-zinc-600 sm:flex-row sm:flex-wrap sm:items-center">
            <p className="flex-1 text-[13px] leading-[1.5]">{t("dashboard.operational.errors.load_failed_description")}</p>
            <Button
              variant="outline"
              size="sm"
              className="shrink-0 border-zinc-300/85 bg-white text-zinc-800 hover:bg-zinc-50/90"
              onClick={() => {
                const tasks: Promise<unknown>[] = [];
                if (leadsQuery.error) {
                  tasks.push(leadsQuery.refetch());
                }
                if (runsQuery.error) {
                  tasks.push(runsQuery.refetch());
                }
                if (operationalQuery.error) {
                  tasks.push(operationalQuery.refetch());
                }
                if (jobsQuery.error) {
                  tasks.push(jobsQuery.refetch());
                }
                void Promise.all(tasks);
              }}
            >
              {t("common.actions.retry")}
            </Button>
          </AlertDescription>
        </Alert>
      ) : null}

      <PageHeader
        className="gap-1 sm:items-end sm:justify-between sm:gap-5"
        kicker={t("dashboard.operational.header_kicker")}
        title={t("dashboard.operational.title")}
        description={t("dashboard.operational.subtitle")}
        descriptionClassName="max-w-[min(100%,40rem)] text-[12.5px] leading-[1.45] text-zinc-500"
        aside={
          <p className="text-[12px] font-medium tabular-nums text-zinc-500">
            {new Date().toLocaleDateString(getDateLocale(), {
              weekday: "long",
              day: "numeric",
              month: "long",
            })}
          </p>
        }
      />

      <DashboardShortcuts />

      <section className="w-full">
        <KpiStrip
          items={[
            {
              label: t("dashboard.operational.kpi.new_requests.label"),
              value: kpiBoot ? (operationalDelay ? <KpiValueSkeleton /> : <KpiValueStatic />) : (operational?.kpis.new_requests.value ?? leads.length),
              hint: t("dashboard.operational.kpi.new_requests.hint"),
              context: !kpiBoot && operational ? kpiContextNewRequests(operational.kpis.new_requests) : undefined,
              contextHelp: t("context_help.dashboard_kpi_new_requests"),
              href: "/customers",
              ariaGoTo: t("dashboard.operational.kpi.go_to_aria", {
                label: t("dashboard.operational.kpi.new_requests.label"),
              }),
            },
            {
              label: t("dashboard.operational.kpi.open_quotes.label"),
              value: kpiBoot ? (operationalDelay ? <KpiValueSkeleton /> : <KpiValueStatic />) : (operational?.kpis.open_quotes.value ?? filteredOffers.length),
              hint: t("dashboard.operational.kpi.open_quotes.hint"),
              context: !kpiBoot && operational ? kpiContextOpenQuotes(operational.kpis.open_quotes) : undefined,
              href: "/offertes",
              ariaGoTo: t("dashboard.operational.kpi.go_to_aria", {
                label: t("dashboard.operational.kpi.open_quotes.label"),
              }),
            },
            {
              label: t("dashboard.operational.kpi.active_jobs.label"),
              value: kpiBoot ? (operationalDelay ? <KpiValueSkeleton /> : <KpiValueStatic />) : (operational?.kpis.active_jobs.value ?? filteredJobs.length),
              hint: t("dashboard.operational.kpi.active_jobs.hint"),
              context: !kpiBoot && operational ? kpiContextActiveJobs(operational.kpis.active_jobs) : undefined,
              href: "/jobs",
              ariaGoTo: t("dashboard.operational.kpi.go_to_aria", {
                label: t("dashboard.operational.kpi.active_jobs.label"),
              }),
            },
            {
              label: t("dashboard.operational.kpi.review_queue.label"),
              value: kpiBoot ? (operationalDelay ? <KpiValueSkeleton /> : <KpiValueStatic />) : (operational?.kpis.review_queue.value ?? reviewItems.length),
              hint: t("dashboard.operational.kpi.review_queue.hint"),
              context: !kpiBoot && operational ? kpiContextReview(operational.kpis.review_queue) : undefined,
              contextHelp: t("context_help.dashboard_kpi_review_queue"),
              href: "/review",
              ariaGoTo: t("dashboard.operational.kpi.go_to_aria", {
                label: t("dashboard.operational.kpi.review_queue.label"),
              }),
            },
          ]}
        />
      </section>

      <section className="w-full">
        <IntakeCompact intakeUrl={intakeUrl} copied={copied} onCopy={handleCopyIntake} />
      </section>

      {/* Chart (dominant) + attention rail (fixed width on large screens) */}
      <div className="grid grid-cols-1 gap-2.5 lg:grid-cols-[minmax(0,1fr)_minmax(300px,360px)] lg:items-start lg:gap-3">
        <div className="min-w-0">
          <section
            aria-labelledby="dash-analytics-heading"
            className="overflow-hidden rounded-xl border border-zinc-200/75 bg-white shadow-[0_1px_0_rgba(15,23,42,0.03)]"
          >
          <div className="border-b border-zinc-200/60 bg-gradient-to-b from-white to-zinc-50/35 px-3 py-2.5 sm:px-4 sm:py-3">
            <p className="text-[10px] font-semibold uppercase leading-none tracking-[0.05em] text-zinc-500">
              {t("dashboard.operational.analytics_section.kicker")}
            </p>
            <h2
              id="dash-analytics-heading"
              className="mt-1 text-[14px] font-semibold leading-tight tracking-[-0.02em] text-zinc-950"
            >
              {t("dashboard.operational.analytics_section.title")}
            </h2>
            <p className="mt-0.5 text-[12px] font-medium leading-snug text-zinc-500">
              {t("dashboard.operational.analytics_section.subtitle")}
            </p>
          </div>

          <div className="space-y-2.5 p-2.5 sm:p-3">
            <div>
              <div className="flex flex-col gap-2 sm:flex-row sm:items-center sm:justify-between sm:gap-3">
                <div className="min-w-0 flex-1">
                  <p className="text-[11px] font-semibold leading-snug tracking-tight text-zinc-600">
                    {t("dashboard.operational.analytics_section.line_title")}
                  </p>
                  <p className="mt-0.5 text-[12px] font-medium leading-snug text-zinc-500">
                    {t("dashboard.operational.analytics_section.line_description", { days: intakeRange })}
                  </p>
                </div>
                <div
                  className="flex w-full shrink-0 rounded-lg border border-zinc-200/70 bg-zinc-100/40 p-0.5 sm:w-auto"
                  role="group"
                  aria-label={t("dashboard.operational.chart.range_group_aria")}
                >
                  {([7, 14, 30, 90] as const).map((d) => (
                    <button
                      key={d}
                      type="button"
                      disabled={intakeChartBoot}
                      onClick={() => setIntakeRange(d)}
                      className={cn(
                        "flex-1 rounded-md px-2 py-1 text-[11px] font-semibold tabular-nums motion-safe:transition-[background-color,color,box-shadow] motion-safe:duration-[150ms] disabled:cursor-not-allowed disabled:opacity-50 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary/28 focus-visible:ring-offset-2 sm:flex-initial sm:px-2.5",
                        intakeRange === d
                          ? "bg-white text-zinc-950 shadow-[0_1px_2px_rgba(15,23,42,0.06)] ring-1 ring-zinc-200/90"
                          : "text-zinc-600 hover:bg-white/85 hover:text-zinc-900",
                      )}
                    >
                      {d === 7
                        ? t("dashboard.operational.chart.range_7")
                        : d === 14
                          ? t("dashboard.operational.chart.range_14")
                          : d === 30
                            ? t("dashboard.operational.chart.range_30")
                            : t("dashboard.operational.chart.range_90")}
                    </button>
                  ))}
                </div>
              </div>
              <div className="mt-1.5 min-h-0 rounded-lg border border-zinc-100/80 bg-zinc-50/30 p-0.5 sm:p-1">
                {intakeChartBoot ? (
                  operationalDelay ? (
                    <DashSkeleton className="h-[224px] w-full rounded-[10px]" />
                  ) : (
                    <div className="h-[224px] w-full rounded-[10px] bg-zinc-100/75" aria-hidden />
                  )
                ) : (
                  <FadeIn>
                    <IntakeLineChart
                      key={`${intakeRange}-${intakeSeries.map((s) => `${s.dayKey}:${s.count}`).join("|")}`}
                      series={intakeSeries}
                      dayRange={intakeRange}
                      chartSummary={chartSummary}
                    />
                  </FadeIn>
                )}
              </div>
              <div className="mt-2">
                {operationalBoot ? (
                  operationalDelay ? (
                    <DashSkeleton className="h-[118px] w-full rounded-[10px]" />
                  ) : (
                    <div className="h-[118px] w-full rounded-[10px] bg-zinc-100/75" aria-hidden />
                  )
                ) : (
                  <FadeIn>
                    <OutcomeSplit
                      acceptedCount={operational?.outcomes.accepted_count ?? 0}
                      rejectedCount={operational?.outcomes.rejected_count ?? 0}
                      acceptedRate={operational?.outcomes.accepted_rate ?? 0}
                      rejectedRate={operational?.outcomes.rejected_rate ?? 0}
                      totalRequests={operational?.outcomes.total_requests ?? 0}
                      days={intakeRange}
                    />
                  </FadeIn>
                )}
              </div>
            </div>

            <div className="border-t border-zinc-200/65 pt-2">
              <p className="text-[11px] font-semibold leading-snug tracking-tight text-zinc-600">
                {t("dashboard.operational.analytics_section.donut_title")}
              </p>
              <p className="mt-0.5 text-[12px] font-medium leading-snug text-zinc-500">
                {t("dashboard.operational.analytics_section.donut_description")}
              </p>
              <div className="mt-1.5">
                {statusDistributionBoot ? (
                  statusDelay ? (
                    <div className="space-y-2">
                      <DashSkeleton className="h-4 w-44 rounded" />
                      <DashSkeleton className="h-2.5 w-full rounded-full" />
                    </div>
                  ) : (
                    <div className="space-y-2" aria-hidden>
                      <div className="h-4 w-44 rounded bg-zinc-100/75" />
                      <div className="h-2.5 w-full rounded-full bg-zinc-100/70" />
                    </div>
                  )
                ) : statusDistribution.length === 0 ? (
                  <p className="type-body-secondary py-2 text-center text-[13px] leading-[1.45] text-zinc-600">
                    {t("dashboard.operational.distribution.no_data")}
                  </p>
                ) : (
                  <FadeIn>
                    <StatusStackedBar items={statusDistribution} />
                  </FadeIn>
                )}
              </div>
            </div>
          </div>
          </section>
        </div>

        <div className="flex min-w-0 flex-col gap-2.5">
          <OperationalPanel
            variant="attention"
            icon={AlertCircle}
            title={t("dashboard.operational.attention.title")}
            description={t("dashboard.operational.attention.description")}
            count={
              operationalBoot ? (
                operationalDelay ? (
                  <KpiValueSkeleton className="h-[22px] min-w-[1.5rem] rounded-[10px]" />
                ) : (
                  <PanelCountStatic />
                )
              ) : (
                attentionTotal
              )
            }
            emphasis={!operationalBoot && !needsAttentionEmpty}
            footer={
              <Link
                href="/review"
                className={cn(
                  buttonVariants({
                    variant: needsAttentionEmpty ? "outline" : "default",
                    size: "sm",
                  }),
                  needsAttentionEmpty
                    ? "w-full justify-center gap-1.5 border-zinc-300/85 font-semibold text-zinc-800 hover:bg-white hover:text-zinc-950 sm:w-auto"
                    : "w-full justify-center gap-1.5 font-semibold sm:w-auto",
                )}
              >
                {t("dashboard.operational.attention.footer_link")}
                <ArrowRight className="h-3.5 w-3.5" aria-hidden />
              </Link>
            }
          >
            <div className="flex flex-col">
              {operationalBoot ? (
                <ListPanelRowsSkeleton showPulse={operationalDelay} />
              ) : needsAttentionEmpty ? (
                <div className="flex flex-col items-center px-2 py-4 text-center">
                  <span className="flex h-9 w-9 items-center justify-center rounded-full border border-zinc-200/80 bg-zinc-50 text-primary">
                    <CheckCircle2 className="h-4 w-4" aria-hidden />
                  </span>
                  <p className="mt-2.5 text-[13px] font-semibold leading-[1.45] text-zinc-900">
                    {t("dashboard.operational.attention.empty_title")}
                  </p>
                  <p className="type-body-secondary mt-1 max-w-[200px] text-zinc-600">
                    {t("dashboard.operational.attention.empty_description")}
                  </p>
                </div>
              ) : (
                <>
                  {operational?.attention.summary ? (
                    <p className="px-1 pb-1.5 text-[11px] font-medium leading-snug text-zinc-500">
                      {t("dashboard.operational.attention.summary_line", {
                        shown: operational.attention.summary.shown,
                        total: operational.attention.summary.total,
                        urgent_suffix:
                          operational.attention.summary.high_urgency > 0
                            ? t("dashboard.operational.attention.summary_urgent_suffix", {
                                urgent: operational.attention.summary.high_urgency,
                              })
                            : "",
                      })}
                    </p>
                  ) : null}
                  <ul className="divide-y divide-zinc-200/70">
                    {reviewItems.map((item: ReviewQueueRow) => {
                      const meta = formatDateTime(item.updatedAt ?? item.createdAt);
                      const issueLine = attentionFriendlyStatus(item.status);
                      const primary =
                        item.customerName.trim() || t("dashboard.operational.fallback_customer_label");
                      const urgent = (item.urgencyScore ?? 0) >= 80;
                      const mid = !urgent && (item.urgencyScore ?? 0) >= 60;
                      return (
                        <li key={item.runId > 0 ? `run-${item.runId}` : `lead-${item.leadId}`}>
                          <ListRow
                            href={item.primaryHref}
                            primary={primary}
                            secondary={issueLine}
                            tertiary={meta !== "—" ? meta : null}
                            emphasis={urgent ? "attention_high" : mid ? "attention_mid" : "none"}
                            badge={
                              urgent ? (
                                <StatusBadge status={item.status} className="ring-1 ring-rose-200/65">
                                  {t("dashboard.operational.attention.urgency_high")}
                                </StatusBadge>
                              ) : mid ? (
                                <StatusBadge status={item.status} className="ring-1 ring-amber-200/60">
                                  {t("dashboard.operational.attention.urgency_mid")}
                                </StatusBadge>
                              ) : null
                            }
                          />
                        </li>
                      );
                    })}
                  </ul>
                </>
              )}
            </div>
          </OperationalPanel>

          <section className="overflow-hidden rounded-xl border border-zinc-200/75 bg-white shadow-[0_1px_0_rgba(15,23,42,0.03)]">
              <div className="flex flex-col gap-0.5 border-b border-zinc-200/65 bg-white px-3 py-2 sm:flex-row sm:items-start sm:justify-between sm:gap-2">
                <div className="min-w-0 space-y-0.5">
                  <p className="text-[10px] font-semibold uppercase leading-none tracking-[0.05em] text-zinc-500">
                    {t("dashboard.operational.activity.kicker")}
                  </p>
                  <h2 className="text-[13px] font-semibold leading-tight tracking-[-0.02em] text-zinc-950">
                    {t("dashboard.operational.activity.title")}
                  </h2>
                  {operationalBoot ? (
                    operationalDelay ? (
                      <DashSkeleton className="mt-0.5 h-3 w-[11rem] rounded" />
                    ) : (
                      <span className="mt-0.5 block h-3 w-[11rem] rounded bg-zinc-100/75" aria-hidden />
                    )
                  ) : (
                    <p className="text-[11px] font-medium leading-snug text-zinc-500">
                      {t("dashboard.operational.activity.subtitle", { count: pipelineRunsInView })}
                    </p>
                  )}
                </div>
                <div className="flex shrink-0 items-baseline gap-1 rounded-md border border-zinc-200/70 bg-zinc-50/90 px-2 py-0.5">
                  <span className="text-[9px] font-semibold uppercase leading-none tracking-wide text-zinc-500">
                    {t("dashboard.operational.activity.scheduled_label")}
                  </span>
                  {jobsBoot ? (
                    jobsDelay ? (
                      <DashSkeleton className="h-4 w-5 rounded" />
                    ) : (
                      <span className="inline-block h-4 w-5 rounded bg-zinc-100/75" aria-hidden />
                    )
                  ) : (
                    <span className="text-sm font-semibold tabular-nums tracking-[-0.02em] text-zinc-950">{acceptedToday}</span>
                  )}
                </div>
              </div>
              <div className="px-3 py-2">
                <p className="text-[12px] font-medium leading-snug text-zinc-500">{t("dashboard.operational.activity.body")}</p>
              </div>
          </section>
        </div>
      </div>

      <div className="grid grid-cols-1 gap-2.5 lg:grid-cols-2 lg:items-start lg:gap-3">
        <OperationalPanel
          icon={Inbox}
          title={t("dashboard.operational.new_requests_panel.title")}
          description={t("dashboard.operational.new_requests_panel.description")}
          count={
            leadsBoot ? (
              leadsDelay ? (
                <KpiValueSkeleton className="h-[22px] min-w-[1.5rem] rounded-[10px]" />
              ) : (
                <PanelCountStatic />
              )
            ) : (
              leads.length
            )
          }
          footer={
            <Link
              href="/customers"
              className="motion-interactive inline-flex items-center gap-1 text-[13px] font-semibold text-zinc-900 underline-offset-4 transition-[color,text-decoration-color] duration-[120ms] hover:underline focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary/25 focus-visible:ring-offset-2"
            >
              {t("dashboard.operational.new_requests_panel.footer_link")}
              <ArrowRight className="h-3.5 w-3.5" aria-hidden />
            </Link>
          }
        >
          <div className="flex flex-col">
            {leadsBoot ? (
              <ListPanelRowsSkeleton showPulse={leadsDelay} />
            ) : leads.length === 0 ? (
              <div className="flex flex-col items-center px-3 py-4 text-center">
                <span className="flex h-10 w-10 items-center justify-center rounded-full border border-zinc-200/80 bg-zinc-50 text-primary">
                  <Inbox className="h-4 w-4" aria-hidden />
                </span>
                <p className="mt-2.5 text-[13px] font-semibold leading-[1.45] text-zinc-900">
                  {t("dashboard.operational.new_requests_panel.empty_title")}
                </p>
                <p className="type-body-secondary mt-1 max-w-[220px] text-zinc-600">
                  {t("dashboard.operational.new_requests_panel.empty_description")}
                </p>
              </div>
            ) : (
              <ul className="divide-y divide-zinc-200/70">
                {leads.slice(0, 5).map((lead: TenantLeadListItem) => (
                  <li key={lead.id}>
                    <ListRow
                      href={`/customers/${lead.id}`}
                      primary={
                        (lead.name ?? "").trim()
                          ? (lead.name ?? "").trim()
                          : t("dashboard.operational.fallback_customer_label")
                      }
                      secondary={lead.email || null}
                      badge={<StatusBadge status={lead.status}>{tStatus(lead.status)}</StatusBadge>}
                    />
                  </li>
                ))}
              </ul>
            )}
          </div>
        </OperationalPanel>

        <OperationalPanel
          icon={ClipboardList}
          title={t("dashboard.operational.recent_done.title")}
          description={t("dashboard.operational.recent_done.description")}
          count={
            jobsBoot ? (
              jobsDelay ? (
                <KpiValueSkeleton className="h-[22px] min-w-[1.5rem] rounded-[10px]" />
              ) : (
                <PanelCountStatic />
              )
            ) : (
              doneJobs.length
            )
          }
          footer={
            <p className="type-body-secondary text-zinc-600">
              {t("dashboard.operational.recent_done.footer_pipeline")}{" "}
              <span className="font-semibold tabular-nums text-zinc-900">
                {hasQuoteAmountsInPipeline ? `€ ${amountTotal.toFixed(0)}` : "—"}
              </span>
            </p>
          }
        >
          <div className="flex flex-col">
            {jobsBoot ? (
              <ListPanelRowsSkeleton showPulse={jobsDelay} />
            ) : doneJobs.length === 0 ? (
              <div className="flex flex-col items-center px-3 py-4 text-center">
                <span className="flex h-10 w-10 items-center justify-center rounded-full border border-zinc-200/80 bg-zinc-50 text-primary">
                  <ClipboardList className="h-4 w-4" aria-hidden />
                </span>
                <p className="mt-2.5 text-[13px] font-semibold leading-[1.45] text-zinc-900">
                  {t("dashboard.operational.recent_done.empty_title")}
                </p>
                <p className="type-body-secondary mt-1 max-w-[220px] text-zinc-600">
                  {t("dashboard.operational.recent_done.empty_description")}
                </p>
              </div>
            ) : (
              <ul className="divide-y divide-zinc-200/70">
                {doneJobs.slice(0, 5).map((job: JobListItem) => {
                  const meta = formatDateTime(job.done_at);
                  return (
                    <li key={job.id}>
                      <ListRow
                        href={`/offertes/${job.lead_id}`}
                        primary={
                          job.lead_name?.trim()
                            ? job.lead_name
                            : t("dashboard.operational.fallback_customer_label")
                        }
                        secondary={
                          meta !== "—" ? t("dashboard.operational.job_done_secondary", { date: meta }) : null
                        }
                        badge={<StatusBadge status={job.status}>{tStatus(job.status)}</StatusBadge>}
                      />
                    </li>
                  );
                })}
              </ul>
            )}
          </div>
        </OperationalPanel>
      </div>
    </div>
  );
}
