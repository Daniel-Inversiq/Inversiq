"use client";

import Link from "next/link";
import { type ReactNode, useEffect, useMemo, useState } from "react";
import {
  AlertCircle,
  ArrowRight,
  Briefcase,
  ChevronRight,
  ClipboardList,
  Copy,
  ExternalLink,
  Home,
  Inbox,
  Link2,
  PaintBucket,
  Send,
  Sun,
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
import { Skeleton } from "@/components/ui/skeleton";
import { StatusBadge } from "@/components/ui/status-badge";
import { useJobs } from "@/hooks/use-jobs";
import { useOperationalDashboard } from "@/hooks/use-operational-dashboard";
import { usePipelineRuns } from "@/hooks/use-pipeline-runs";
import { useTenantLeads } from "@/hooks/use-tenant-leads";
import { useTenantMe } from "@/hooks/use-tenant-me";
import { buildOfferRowsSummaryFromPipelineAndLeads } from "@/lib/offers/offer-rows-summary";
import { OFFERS_PIPELINE_FETCH_LIMIT } from "@/lib/offers/query-keys";
import { buildTenantIntakeUrl } from "@/lib/api/client";
import { getDateLocale, t, tStatus } from "@/lib/i18n";
import type { Sector } from "@/lib/tenant";
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
      const id = requestAnimationFrame(() => {
        setShow(false);
      });
      return () => cancelAnimationFrame(id);
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

/** Signed % label for intake vs prior period (e.g. +18%, −5%). */
function formatIntakeTrendPctLabel(pct: number, trend: "up" | "down"): string {
  const rounded = Math.round(pct * 10) / 10;
  const abs = Math.abs(rounded);
  const body = Number.isInteger(abs) ? String(abs) : abs.toFixed(1);
  return trend === "up" ? `+${body}%` : `−${body}%`;
}

/** Shared max width so header, KPIs, and grids align on one vertical edge. */
const DASHBOARD_PAGE_CLASS = "mx-auto w-full max-w-[min(1480px,100%)]";

function resolveDashboardSector(sector: string | null | undefined): Sector {
  if (sector === "construction" || sector === "insurance" || sector === "logistics" || sector === "real_estate") {
    return sector;
  }
  return "construction";
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
    <div className="space-y-4">
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
      <div className="flex flex-col gap-2 rounded-lg border border-slate-200 bg-white px-3 py-2.5 shadow-sm sm:flex-row sm:items-center sm:gap-3">
        <div className="flex min-w-0 flex-1 items-center gap-2.5">
          <span className="h-8 w-8 shrink-0 rounded-lg border border-blue-200/70 bg-white/80" />
          <div className="min-w-0 flex-1 space-y-1">
            <DashSkeleton className="h-2 w-24 rounded" />
            <DashSkeleton className="h-3.5 w-full max-w-[min(100%,360px)] rounded" />
          </div>
        </div>
        <div className="flex shrink-0 gap-2">
          <DashSkeleton className="h-8 w-[5.25rem] rounded-md" />
          <DashSkeleton className="h-8 w-[5.25rem] rounded-md" />
        </div>
      </div>
      <div className="grid grid-cols-1 gap-4 lg:grid-cols-[minmax(0,2fr)_minmax(0,1fr)] lg:items-start">
        <div className="flex min-w-0 flex-col gap-4">
          <div className="min-w-0 overflow-hidden rounded-[11px] border border-zinc-300/85 bg-white">
            <div className="border-b border-zinc-300/75 px-3 py-2.5">
              <DashSkeleton className="h-2 w-20 rounded" />
              <DashSkeleton className="mt-2 h-4 w-48 max-w-full rounded" />
              <DashSkeleton className="mt-1.5 h-3 w-full max-w-md rounded" />
            </div>
            <div className="min-h-[200px] space-y-2 px-2.5 py-3 sm:px-3">
              <DashSkeleton className="h-[34px] w-full rounded-[8px]" />
              <DashSkeleton className="h-[34px] w-full rounded-[8px]" />
            </div>
            <div className="border-t border-zinc-300/75 px-3 py-2">
              <DashSkeleton className="h-3.5 w-32 rounded" />
            </div>
          </div>
          <div className="min-w-0 overflow-hidden rounded-[11px] border border-zinc-300/85 bg-white">
            <div className="border-b border-zinc-300/75 px-3 py-2">
              <DashSkeleton className="h-3 w-40 rounded" />
              <DashSkeleton className="mt-1 h-2.5 w-56 rounded" />
            </div>
            <div className="space-y-2 p-2.5 sm:p-3">
              <DashSkeleton className="h-[192px] w-full rounded-[8px]" />
              <DashSkeleton className="h-[100px] w-full rounded-[8px]" />
              <DashSkeleton className="h-2.5 w-full rounded-full" />
            </div>
          </div>
        </div>
        <div className="flex min-w-0 flex-col gap-4">
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
            <div className="border-b border-zinc-200/70 px-3 py-2">
              <DashSkeleton className="h-3 w-full max-w-[280px] rounded" />
            </div>
            <div className="flex items-center justify-between gap-2 border-b border-zinc-200/70 px-3 py-2">
              <DashSkeleton className="h-3.5 w-32 rounded" />
              <DashSkeleton className="h-5 w-7 rounded-[10px]" />
            </div>
            <div className="space-y-1.5 px-2.5 py-2">
              <DashSkeleton className="h-[34px] w-full rounded-[8px]" />
              <DashSkeleton className="h-[34px] w-full rounded-[8px]" />
            </div>
            <div className="border-t border-zinc-300/75 px-3 py-2">
              <DashSkeleton className="h-3 w-full max-w-[220px] rounded" />
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}

const KPI_CARD_INTERACTIVE =
  "cursor-pointer text-inherit no-underline motion-safe:transition-[border-color,box-shadow,background-color,transform] motion-safe:duration-150 motion-safe:ease-out motion-reduce:transition-none hover:border-zinc-300 hover:bg-white hover:shadow-md hover:-translate-y-0.5 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-slate-300/60 focus-visible:ring-offset-1";

const KPI_VARIANT_STYLES = [
  {
    shell: "border-t border-t-zinc-200",
    iconWrap: "bg-blue-50 text-blue-700",
    chevron: "text-zinc-400 group-hover:text-blue-600",
    hint: "text-zinc-500",
    ctx: "text-zinc-500",
    Icon: Inbox,
  },
  {
    shell: "border-t border-t-zinc-200",
    iconWrap: "bg-blue-50 text-blue-700",
    chevron: "text-zinc-400 group-hover:text-blue-600",
    hint: "text-zinc-500",
    ctx: "text-zinc-500",
    Icon: Send,
  },
  {
    shell: "border-t border-t-zinc-200",
    iconWrap: "bg-blue-50 text-blue-700",
    chevron: "text-zinc-400 group-hover:text-blue-600",
    hint: "text-zinc-500",
    ctx: "text-zinc-500",
    Icon: Briefcase,
  },
  {
    shell: "border-t border-t-zinc-200",
    iconWrap: "bg-blue-50 text-blue-700",
    chevron: "text-zinc-400 group-hover:text-blue-600",
    hint: "text-zinc-500",
    ctx: "text-zinc-500",
    Icon: AlertCircle,
  },
] as const;

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
    <div className="grid grid-cols-1 items-stretch gap-3 md:grid-cols-2 md:gap-4 xl:grid-cols-4">
      {items.map((item, index) => {
        const vis = KPI_VARIANT_STYLES[index] ?? KPI_VARIANT_STYLES[0];
        const Icon = vis.Icon;
        const body = (
          <div
            className={cn(
              "flex min-h-0 min-w-0 flex-1 flex-col gap-1.5",
              item.hint || item.context ? "justify-between" : "justify-start",
            )}
          >
            <div className="min-w-0 space-y-1">
              <div className="flex shrink-0 items-start justify-between gap-2">
                <span
                  className={cn(
                    "flex h-6 w-6 shrink-0 items-center justify-center rounded-md sm:h-7 sm:w-7",
                    vis.iconWrap,
                  )}
                >
                  <Icon className="h-3 w-3 sm:h-3.5 sm:w-3.5" aria-hidden />
                </span>
                {item.href ? (
                  <ChevronRight
                    className={cn(
                      "mt-0.5 h-3.5 w-3.5 shrink-0 opacity-0 transition-[opacity,transform] duration-150 motion-reduce:transition-none group-hover:translate-x-0.5 group-hover:opacity-70",
                      vis.chevron,
                    )}
                    aria-hidden
                  />
                ) : null}
              </div>
              <div className="min-w-0 break-words text-4xl font-bold leading-none tracking-[-0.03em] text-gray-900">
                {item.value}
              </div>
              <div className="flex min-w-0 items-center gap-1.5">
                <p className="min-w-0 flex-1 text-sm font-medium leading-snug text-gray-500">
                  {item.label}
                </p>
                {item.contextHelp ? (
                  <span className="shrink-0" onPointerDown={(e) => e.stopPropagation()}>
                    <HelpTooltip content={item.contextHelp} />
                  </span>
                ) : null}
              </div>
            </div>
            {item.hint || item.context ? (
              <div className="min-w-0 space-y-0.5 border-t border-zinc-200 pt-1.5">
                {item.hint ? (
                  <p className={cn("text-[11px] font-medium leading-snug", vis.hint)}>{item.hint}</p>
                ) : null}
                {item.context ? (
                  <p className={cn("text-[11px] font-medium leading-snug", vis.ctx)}>{item.context}</p>
                ) : null}
              </div>
            ) : null}
          </div>
        );

        const shellClass = cn(
          "group flex h-full min-h-[118px] flex-col rounded-2xl border border-zinc-200 bg-[#FFFFFF] p-4 shadow-[0_1px_3px_rgba(0,0,0,0.08)] sm:min-h-[118px] sm:p-4",
          vis.shell,
          item.href ? KPI_CARD_INTERACTIVE : "cursor-default",
        );

        if (item.href) {
          return (
            <Link
              key={item.label}
              href={item.href}
              className={shellClass}
              aria-label={item.ariaGoTo ?? item.label}
            >
              {body}
            </Link>
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
      <ul className="divide-y divide-slate-100">
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

function IntakePrimaryBar({
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
    <div
      role="region"
      aria-label={t("dashboard.operational.intake.label")}
      className="flex flex-col gap-2 rounded-2xl border border-zinc-200 bg-white px-3 py-2.5 shadow-sm sm:flex-row sm:items-center sm:justify-between sm:gap-3"
    >
      <div className="flex min-w-0 flex-1 items-start gap-2.5 sm:items-center">
        <span className="mt-0.5 flex h-7 w-7 shrink-0 items-center justify-center rounded-md border border-zinc-200 bg-white text-blue-700 sm:mt-0">
          <Link2 className="h-3.5 w-3.5" aria-hidden />
        </span>
        <div className="min-w-0 flex-1">
          <p className="text-[10px] font-semibold uppercase tracking-[0.05em] text-zinc-500">
            {t("dashboard.operational.intake.label")}
          </p>
          <p className="mt-0.5 truncate text-[13px] font-semibold leading-snug tracking-[-0.02em] text-zinc-900" title={intakeUrl}>
            {hostLine}
          </p>
          {pathLine ? (
            <p className="mt-0.5 truncate font-mono text-[10px] font-medium leading-snug text-zinc-500" title={intakeUrl}>
              {pathLine}
            </p>
          ) : null}
          <p className="sr-only">{intakeUrl}</p>
        </div>
      </div>
      <div className="flex shrink-0 flex-wrap items-center gap-2 sm:justify-end">
        <div className="inline-flex items-center gap-1 rounded-md border border-zinc-200 bg-white p-0.5">
          <Button
            size="sm"
            type="button"
            className="h-8 gap-1.5 rounded-[6px] border-0 px-3 text-[12px] font-semibold !bg-primary !text-white shadow-none motion-safe:transition-[background-color,color] motion-safe:duration-[120ms] hover:!bg-[#1D4ED8] hover:!text-white focus-visible:ring-2 focus-visible:ring-primary/30 focus-visible:ring-offset-1 [&_svg]:!text-white"
            onClick={() => void onCopy()}
          >
            <Copy className="h-3.5 w-3.5" aria-hidden />
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
                "h-8 gap-1.5 rounded-[6px] border-zinc-200 bg-[#FFFFFF] px-3 text-[12px] font-semibold text-zinc-700 shadow-none hover:bg-[#EEF4F0] hover:text-zinc-900",
            })}
          >
            <ExternalLink className="h-3.5 w-3.5" aria-hidden />
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
                "h-8 w-8 shrink-0 rounded-[6px] border-zinc-200 bg-[#FFFFFF] text-zinc-600 hover:bg-[#EEF4F0] hover:text-zinc-800",
            })}
          >
            <WhatsappGlyph className="h-3.5 w-3.5" />
          </a>
        </div>
        <span
          className={cn(
            "min-w-[4.5rem] text-right text-[10px] font-semibold leading-none text-zinc-500 motion-safe:transition-opacity motion-safe:duration-[150ms]",
            copied ? "text-zinc-600 opacity-100" : "opacity-0",
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
        "group motion-interactive flex items-start justify-between gap-2 rounded-md border border-transparent px-1.5 py-2 -mx-1.5 motion-safe:transition-[background-color,border-color] motion-safe:duration-[130ms] hover:border-zinc-200 hover:bg-[#EEF4F0] active:bg-zinc-100 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-slate-300/60 focus-visible:ring-offset-2",
        emphasis === "attention_high" && "border-l-2 border-l-rose-500 pl-2",
        emphasis === "attention_mid" && "border-l-2 border-l-[#4A7C59] pl-2",
      )}
    >
      <div className="min-w-0 flex-1 space-y-0">
        <p className="truncate text-[13px] font-semibold leading-tight tracking-[-0.01em] text-zinc-900 group-hover:text-zinc-950">
          {primary}
        </p>
        {secondary ? (
          <p className="truncate text-[11px] font-medium leading-snug text-zinc-500">{secondary}</p>
        ) : null}
        {tertiary ? (
          <p className="type-meta truncate text-[10px] tabular-nums text-slate-400">{tertiary}</p>
        ) : null}
      </div>
      <div className="flex shrink-0 items-center gap-1 self-start pt-0.5">
        {badge}
        <ChevronRight
          className="h-3.5 w-3.5 shrink-0 text-slate-300 opacity-0 transition-[opacity,transform] duration-[150ms] motion-reduce:transition-none group-hover:translate-x-0.5 group-hover:opacity-60"
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
  headerTone = "default",
  compact = false,
  className,
}: {
  icon: React.ComponentType<{ className?: string }>;
  title: string;
  description: string;
  count: ReactNode;
  children: ReactNode;
  footer: ReactNode;
  emphasis?: boolean;
  variant?: "default" | "attention";
  headerTone?: "default" | "slate";
  compact?: boolean;
  className?: string;
}) {
  const isAttention = variant === "attention";
  const headerBarClass = cn(
    "border-b border-slate-200 bg-white",
    compact ? "px-2.5 py-1.5" : "px-3 py-2",
  );

  return (
    <section
      className={cn(
        "flex min-h-0 flex-col overflow-hidden rounded-2xl border border-zinc-200 bg-[#FFFFFF] shadow-[0_1px_3px_rgba(0,0,0,0.08)] motion-safe:transition-[border-color,box-shadow] motion-safe:duration-150 motion-safe:ease-out",
        isAttention && emphasis && "border-l-2 border-l-rose-500/90",
        className,
      )}
    >
      <div className={headerBarClass}>
        <div className="flex items-start justify-between gap-2">
          <div className="flex min-w-0 items-start gap-2">
            {isAttention ? (
              <span
                className={cn("h-1.5 w-1.5 shrink-0 rounded-full bg-rose-500", compact ? "mt-1" : "mt-1.5")}
                aria-hidden
              />
            ) : (
              <span
                className={
                  headerTone === "slate"
                    ? "mt-0.5 flex h-6 w-6 shrink-0 items-center justify-center rounded-md border border-slate-200 bg-slate-50 text-slate-600"
                    : "mt-0.5 flex h-6 w-6 shrink-0 items-center justify-center rounded-md border border-slate-200 bg-white text-slate-600"
                }
              >
                <Icon className="h-3 w-3" aria-hidden />
              </span>
            )}
            <div className="min-w-0 space-y-0.5">
              <h3
                className={cn(
                  "font-semibold leading-[1.25] tracking-[-0.02em] text-slate-900",
                  compact ? "text-[12px]" : "text-[12.5px]",
                )}
              >
                {title}
              </h3>
              {compact && isAttention ? null : (
                <p
                  className={cn(
                    "font-medium leading-[1.35] text-slate-500",
                    compact ? "text-[10px]" : "text-[11px]",
                  )}
                >
                  {description}
                </p>
              )}
            </div>
          </div>
          <span
            className={
              emphasis && isAttention
                ? "inline-flex min-h-[20px] min-w-[1.5rem] shrink-0 items-center justify-center rounded-md border border-rose-200 bg-rose-50 px-1.5 text-[10px] font-semibold tabular-nums text-rose-800"
                : "inline-flex min-h-[20px] min-w-[1.5rem] shrink-0 items-center justify-center rounded-md border border-slate-200 bg-slate-50 px-1.5 text-[10px] font-semibold tabular-nums text-slate-700"
            }
          >
            {count}
          </span>
        </div>
      </div>
      <div className={cn("flex flex-col", compact ? "px-1.5 py-0" : "px-2 py-0.5")}>{children}</div>
      <div className={cn("border-t border-slate-200", compact ? "px-2.5 py-1" : "px-3 py-1.5")}>{footer}</div>
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
      <div className="rounded-md border border-slate-200 bg-white px-3 py-2">
        <p className="text-[11px] font-semibold leading-snug text-slate-800">
          {t("dashboard.operational.outcomes.empty_title")}
        </p>
        <p className="mt-0.5 text-[10px] leading-snug text-slate-500">
          {t("dashboard.operational.outcomes.empty_description", { days })}
        </p>
      </div>
    );
  }

  const decidedTotal = acceptedCount + rejectedCount;
  const acceptedWidth = decidedTotal > 0 ? (acceptedCount / decidedTotal) * 100 : 0;
  const rejectedWidth = decidedTotal > 0 ? (rejectedCount / decidedTotal) * 100 : 0;

  return (
    <div className="rounded-md border border-slate-200 bg-white px-3 py-2">
      <div className="flex items-start justify-between gap-3">
        <div>
          <p className="text-[9px] font-semibold uppercase tracking-[0.05em] text-slate-400">
            {t("dashboard.operational.outcomes.accepted_label")}
          </p>
          <p className="mt-0.5 text-lg font-semibold leading-none tracking-[-0.02em] text-slate-900">
            {acceptedRate.toFixed(1)}%
          </p>
        </div>
        <div className="text-right">
          <p className="text-[9px] font-semibold uppercase tracking-[0.05em] text-slate-400">
            {t("dashboard.operational.outcomes.rejected_label")}
          </p>
          <p className="mt-0.5 text-sm font-semibold leading-none tabular-nums text-slate-600">
            {rejectedRate.toFixed(1)}%
          </p>
        </div>
      </div>

      <div className="mt-2 h-1.5 w-full overflow-hidden rounded-full bg-slate-100">
        {decidedTotal > 0 ? (
          <div className="flex h-full w-full">
            <div className="h-full" style={{ width: `${acceptedWidth}%`, backgroundColor: "#1F7A3E" }} />
            <div className="h-full bg-zinc-400/80" style={{ width: `${rejectedWidth}%` }} />
          </div>
        ) : (
          <div className="h-full w-full bg-slate-200/90" />
        )}
      </div>

      <p className="mt-1.5 text-[10px] font-medium leading-snug text-slate-600">
        {t("dashboard.operational.outcomes.counts_line", {
          accepted: acceptedCount,
          rejected: rejectedCount,
        })}
      </p>
      <p className="mt-0.5 text-[10px] leading-snug text-slate-500">
        {t("dashboard.operational.outcomes.total_line", { total: totalRequests, days })}
      </p>
    </div>
  );
}

function DashboardActivityLiveRow({
  lastUpdatedMs,
  isRefreshing,
  visible,
}: {
  lastUpdatedMs: number;
  isRefreshing: boolean;
  visible: boolean;
}) {
  if (!visible) {
    return null;
  }
  const timeStr =
    lastUpdatedMs > 0
      ? new Date(lastUpdatedMs).toLocaleTimeString(getDateLocale(), {
          hour: "2-digit",
          minute: "2-digit",
        })
      : null;
  return (
    <div
      className="flex flex-wrap items-center justify-end gap-x-2 gap-y-1 text-[10px] font-medium text-slate-500"
      aria-live="polite"
    >
      <span className="inline-flex items-center gap-1.5 text-slate-500">
        <span
          className={cn(
            "h-1.5 w-1.5 shrink-0 rounded-full bg-emerald-500/90",
            isRefreshing && "motion-safe:animate-pulse",
          )}
          aria-hidden
        />
        <span>{t("dashboard.operational.activity.live_badge")}</span>
      </span>
      {timeStr ? (
        <span className="tabular-nums text-slate-400">{t("dashboard.operational.activity.last_updated", { time: timeStr })}</span>
      ) : null}
    </div>
  );
}

export default function DashboardPage() {
  const session = useSessionContext();
  const tenantId = session.user?.tenant_id?.trim() ?? "";
  const canLoadTenantData = session.isAuthenticated && tenantId.length > 0;
  const [copied, setCopied] = useState(false);
  const [intakeRange, setIntakeRange] = useState<7 | 14 | 30 | 90>(30);

  const leadsQuery = useTenantLeads(tenantId, canLoadTenantData, undefined, true);
  const jobsQuery = useJobs(canLoadTenantData, undefined, true);
  const runsQuery = usePipelineRuns({
    tenantId: canLoadTenantData ? tenantId : undefined,
    enabled: canLoadTenantData,
    limit: OFFERS_PIPELINE_FETCH_LIMIT,
    live: true,
  });
  const tenantMeQuery = useTenantMe(canLoadTenantData);
  const operationalQuery = useOperationalDashboard({
    tenantId,
    chartDays: intakeRange,
    enabled: canLoadTenantData,
    live: true,
  });

  const dashboardLiveDataUpdatedAt = useMemo(
    () => Math.max(leadsQuery.dataUpdatedAt, operationalQuery.dataUpdatedAt, jobsQuery.dataUpdatedAt),
    [leadsQuery.dataUpdatedAt, operationalQuery.dataUpdatedAt, jobsQuery.dataUpdatedAt],
  );
  const dashboardLiveHydrated =
    leadsQuery.dataUpdatedAt > 0 || operationalQuery.dataUpdatedAt > 0 || jobsQuery.dataUpdatedAt > 0;
  const dashboardLiveRefreshing =
    canLoadTenantData &&
    dashboardLiveHydrated &&
    (leadsQuery.isFetching || operationalQuery.isFetching || jobsQuery.isFetching);

  useEffect(() => {
    if (!canLoadTenantData) {
      return;
    }
    const onVisible = () => {
      if (document.visibilityState !== "visible") {
        return;
      }
      void Promise.all([
        leadsQuery.refetch(),
        operationalQuery.refetch(),
        jobsQuery.refetch(),
        runsQuery.refetch(),
      ]);
    };
    document.addEventListener("visibilitychange", onVisible);
    return () => document.removeEventListener("visibilitychange", onVisible);
  }, [canLoadTenantData, leadsQuery, operationalQuery, jobsQuery, runsQuery]);

  const runs = useMemo(
    () => (runsQuery.data?.items ?? []).filter((run) => run.tenant_id === tenantId),
    [runsQuery.data?.items, tenantId],
  );
  const leads = useMemo(() => leadsQuery.data ?? [], [leadsQuery.data]);
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
  }, [operational]);

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
  }, [operational, intakeRange]);

  const chartSummary = operational?.intake.summary ?? null;

  const intakePeriodSummary = useMemo(() => {
    if (!chartSummary) {
      return null;
    }
    const total = chartSummary.total;
    const prior = chartSummary.prior_range_total;
    if (prior > 0) {
      const rawPct = ((total - prior) / prior) * 100;
      const pct = Math.round(rawPct * 10) / 10;
      if (pct > 0) {
        return { total, trend: "up" as const, pct };
      }
      if (pct < 0) {
        return { total, trend: "down" as const, pct };
      }
      return { total, trend: "stable" as const, pct: 0 };
    }
    if (total > 0) {
      return { total, trend: "new" as const, pct: null as number | null };
    }
    return { total, trend: "empty" as const, pct: null as number | null };
  }, [chartSummary]);

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
      <div className={cn(DASHBOARD_PAGE_CLASS, "space-y-4")}>
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

  const dashSector = resolveDashboardSector(tenantMeQuery.data?.sector);
  const SectorGlyph = dashSector === "insurance" ? Home : dashSector === "logistics" ? Sun : Briefcase;
  const headerPrimaryTitle =
    tenantMeQuery.data?.vertical?.label?.trim() || t("dashboard.operational.title");

  return (
    <div className={cn(DASHBOARD_PAGE_CLASS, "space-y-5")}>
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

      <header className="flex flex-col gap-1 border-b border-slate-200/90 pb-2.5 sm:flex-row sm:items-baseline sm:justify-between sm:gap-3">
        <div className="flex min-w-0 items-center gap-2">
          <span className="flex h-7 w-7 shrink-0 items-center justify-center rounded-md border border-slate-200 bg-white text-slate-500">
            <SectorGlyph className="h-3.5 w-3.5" aria-hidden />
          </span>
          <h1 className="min-w-0 text-[1.05rem] font-semibold leading-tight tracking-[-0.02em] text-slate-900 sm:text-[1.125rem]">
            {headerPrimaryTitle}
          </h1>
        </div>
        <p className="shrink-0 text-[11px] font-medium tabular-nums text-slate-500">
          {new Date().toLocaleDateString(getDateLocale(), {
            weekday: "long",
            day: "numeric",
            month: "long",
          })}
        </p>
      </header>

      <section className="w-full">
        <KpiStrip
          items={[
            {
              label: t("dashboard.operational.kpi.new_requests.label"),
              value: kpiBoot ? (operationalDelay ? <KpiValueSkeleton /> : <KpiValueStatic />) : (operational?.kpis.new_requests.value ?? leads.length),
              hint: t("dashboard.operational.kpi.new_requests.hint"),
              context: !kpiBoot && operational ? kpiContextNewRequests(operational.kpis.new_requests) : undefined,
              contextHelp: t("context_help.dashboard_kpi_new_requests"),
              href: "/customers?filter=open",
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
              href: "/review?filter=attention",
              ariaGoTo: t("dashboard.operational.kpi.go_to_aria", {
                label: t("dashboard.operational.kpi.review_queue.label"),
              }),
            },
          ]}
        />
      </section>

      <IntakePrimaryBar intakeUrl={intakeUrl} copied={copied} onCopy={handleCopyIntake} />

      <div className="grid grid-cols-1 gap-5 lg:grid-cols-[minmax(0,2fr)_minmax(260px,1fr)] lg:items-start">
        <div className="flex min-w-0 flex-col gap-5">
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
            <div className="flex min-h-[min(220px,36vh)] flex-col">
              {leadsBoot ? (
                <ListPanelRowsSkeleton showPulse={leadsDelay} />
              ) : leads.length === 0 ? (
                <div className="flex flex-1 flex-col items-center justify-center px-4 py-10 text-center">
                  <span className="flex h-8 w-8 shrink-0 items-center justify-center rounded-md border border-slate-200 bg-white text-slate-400">
                    <Inbox className="h-3.5 w-3.5" aria-hidden />
                  </span>
                  <p className="mt-2.5 text-[12.5px] font-semibold leading-snug text-slate-900">
                    {t("dashboard.operational.new_requests_panel.empty_title")}
                  </p>
                  <p className="sr-only">{t("dashboard.operational.new_requests_panel.empty_description")}</p>
                </div>
              ) : (
                <ul className="divide-y divide-slate-100">
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

          <section
            aria-labelledby="dash-analytics-heading"
            className="overflow-hidden rounded-2xl border border-zinc-200 bg-[#FFFFFF] shadow-sm"
          >
          <div className="border-b border-zinc-200 px-4 py-3">
            <h2
              id="dash-analytics-heading"
              className="text-[15px] font-semibold leading-tight tracking-[-0.02em] text-zinc-900"
            >
              {t("dashboard.operational.analytics_section.title")}
            </h2>
            <p className="mt-0.5 text-[11px] font-medium leading-snug text-zinc-500">
              {t("dashboard.operational.analytics_section.subtitle")}
            </p>
          </div>

          <div className="space-y-2.5 p-2 sm:p-2.5">
            <div>
              <div className="flex flex-col gap-2 sm:flex-row sm:items-center sm:justify-between sm:gap-3">
                <div className="min-w-0 flex-1">
                  <p className="text-[12px] font-semibold leading-snug text-zinc-800">
                    {t("dashboard.operational.analytics_section.line_title")}
                  </p>
                  <p className="mt-0.5 text-[11px] font-medium leading-snug text-zinc-500">
                    {t("dashboard.operational.analytics_section.line_description", { days: intakeRange })}
                  </p>
                </div>
                <div
                  className="flex w-full shrink-0 rounded-full border border-zinc-200 bg-[#EEF4F0] p-0.5 sm:w-auto"
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
                        "flex-1 rounded-full px-2.5 py-1 text-[11px] font-semibold tabular-nums motion-safe:transition-[background-color,color,box-shadow] motion-safe:duration-[150ms] disabled:cursor-not-allowed disabled:opacity-50 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[#4A7C59]/28 focus-visible:ring-offset-2 sm:flex-initial sm:px-3",
                        intakeRange === d
                          ? "bg-[#4A7C59] text-white shadow-sm"
                          : "text-zinc-600 hover:bg-white hover:text-zinc-800",
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

              <div className="mt-2 border-t border-slate-200 pt-2">
                {intakeChartBoot ? (
                  operationalDelay ? (
                    <div className="space-y-2">
                      <DashSkeleton className="h-9 w-44 max-w-full rounded-md" />
                      <DashSkeleton className="h-4 w-56 max-w-full rounded-md" />
                    </div>
                  ) : (
                    <div className="space-y-2" aria-hidden>
                      <div className="h-9 w-44 max-w-full rounded-md bg-zinc-100/75" />
                      <div className="h-4 w-56 max-w-full rounded-md bg-zinc-100/75" />
                    </div>
                  )
                ) : intakePeriodSummary ? (
                  <div className="flex flex-col gap-1 sm:flex-row sm:items-baseline sm:justify-between sm:gap-4">
                    <div className="min-w-0">
                      <p className="text-xl font-semibold tabular-nums tracking-[-0.03em] text-slate-900">
                        {t("dashboard.operational.analytics_section.intake_headline", {
                          count: intakePeriodSummary.total,
                        })}
                      </p>
                      <p className="mt-0.5 text-[11px] font-medium tabular-nums text-zinc-500">
                        {t("dashboard.operational.analytics_section.intake_period_caption", { days: intakeRange })}
                      </p>
                    </div>
                    <p
                      className={cn(
                        "shrink-0 text-[13px] font-semibold tabular-nums leading-snug",
                        intakePeriodSummary.trend === "up" && "text-emerald-700",
                        intakePeriodSummary.trend === "down" && "text-rose-700",
                        intakePeriodSummary.trend === "stable" && "text-zinc-500",
                        (intakePeriodSummary.trend === "new" || intakePeriodSummary.trend === "empty") && "text-zinc-500",
                      )}
                    >
                      {intakePeriodSummary.trend === "up" || intakePeriodSummary.trend === "down" ? (
                        t("dashboard.operational.analytics_section.intake_trend_vs_prior", {
                          pct: formatIntakeTrendPctLabel(
                            intakePeriodSummary.pct ?? 0,
                            intakePeriodSummary.trend,
                          ),
                        })
                      ) : intakePeriodSummary.trend === "stable" ? (
                        t("dashboard.operational.analytics_section.intake_trend_stable")
                      ) : intakePeriodSummary.trend === "new" ? (
                        t("dashboard.operational.analytics_section.intake_trend_no_baseline")
                      ) : (
                        t("dashboard.operational.analytics_section.intake_trend_no_data")
                      )}
                    </p>
                  </div>
                ) : null}
              </div>

              <div className="mt-1.5 min-h-0 rounded-md border border-slate-200 bg-white p-0">
                {intakeChartBoot ? (
                  operationalDelay ? (
                    <DashSkeleton className="h-[264px] w-full rounded-md" />
                  ) : (
                    <div className="h-[264px] w-full rounded-md bg-slate-100/80" aria-hidden />
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
              <div className="mt-1.5">
                {operationalBoot ? (
                  operationalDelay ? (
                    <DashSkeleton className="h-[104px] w-full rounded-md" />
                  ) : (
                    <div className="h-[104px] w-full rounded-md bg-slate-100/80" aria-hidden />
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

            <div className="border-t border-zinc-200 pt-2">
              <p className="text-[11.5px] font-semibold leading-snug text-slate-800">
                {t("dashboard.operational.analytics_section.donut_title")}
              </p>
              <p className="mt-0.5 text-[11px] font-medium leading-snug text-slate-500">
                {t("dashboard.operational.analytics_section.donut_description")}
              </p>
              <div className="mt-2">
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
                  <p className="py-2 text-center text-[11px] font-medium leading-snug text-slate-500">
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

        <div className="flex min-w-0 flex-col gap-5">
          <section
            aria-labelledby="dash-activity-heading"
            className="flex min-h-0 flex-col overflow-hidden rounded-2xl border border-zinc-200 bg-white shadow-sm"
          >
            <div className="flex flex-col gap-0.5 border-b border-zinc-200 bg-white px-3 py-2 sm:flex-row sm:items-start sm:justify-between sm:gap-2">
              <div className="min-w-0 space-y-0.5">
                <p className="text-[9px] font-semibold uppercase leading-none tracking-[0.06em] text-slate-400">
                  {t("dashboard.operational.activity.kicker")}
                </p>
                <h2
                  id="dash-activity-heading"
                  className="text-[13px] font-semibold leading-tight tracking-[-0.02em] text-zinc-900"
                >
                  {t("dashboard.operational.activity.title")}
                </h2>
                {operationalBoot ? (
                  operationalDelay ? (
                    <DashSkeleton className="mt-0.5 h-2.5 w-[10rem] rounded" />
                  ) : (
                    <span className="mt-0.5 block h-2.5 w-[10rem] rounded bg-slate-100" aria-hidden />
                  )
                ) : (
                  <p className="text-[10px] font-medium leading-snug text-zinc-500">
                    {t("dashboard.operational.activity.subtitle", { count: pipelineRunsInView })}
                  </p>
                )}
              </div>
              <div className="flex shrink-0 flex-col items-stretch gap-1 sm:items-end">
                <DashboardActivityLiveRow
                  lastUpdatedMs={dashboardLiveDataUpdatedAt}
                  isRefreshing={dashboardLiveRefreshing}
                  visible={canLoadTenantData}
                />
                <div className="flex shrink-0 items-baseline gap-1 self-end rounded-md border border-zinc-200 bg-white px-1.5 py-0.5">
                  <span className="text-[9px] font-semibold uppercase leading-none tracking-wide text-slate-400">
                    {t("dashboard.operational.activity.scheduled_label")}
                  </span>
                  {jobsBoot ? (
                    jobsDelay ? (
                      <DashSkeleton className="h-3.5 w-5 rounded" />
                    ) : (
                      <span className="inline-block h-3.5 w-5 rounded bg-slate-100" aria-hidden />
                    )
                  ) : (
                    <span className="text-xs font-semibold tabular-nums tracking-[-0.02em] text-slate-900">{acceptedToday}</span>
                  )}
                </div>
              </div>
            </div>
            <div className="border-b border-slate-100 px-3 py-1.5">
              <p className="text-[10px] font-medium leading-snug text-slate-500">{t("dashboard.operational.activity.body")}</p>
            </div>

            <div className="flex items-start justify-between gap-2 border-b border-slate-100 px-3 py-1.5">
              <div className="flex min-w-0 items-start gap-2">
                <span className="mt-0.5 flex h-6 w-6 shrink-0 items-center justify-center rounded-md border border-slate-200 bg-white text-slate-500">
                  <ClipboardList className="h-3 w-3" aria-hidden />
                </span>
                <div className="min-w-0 space-y-0.5">
                  <h3 className="text-[11.5px] font-semibold leading-tight tracking-[-0.02em] text-slate-900">
                    {t("dashboard.operational.recent_done.title")}
                  </h3>
                  <p className="text-[10px] font-medium leading-snug text-slate-500">
                    {t("dashboard.operational.recent_done.description")}
                  </p>
                </div>
              </div>
              <span className="inline-flex min-h-[20px] min-w-[1.5rem] shrink-0 items-center justify-center rounded-md border border-slate-200 bg-slate-50 px-1.5 text-[10px] font-semibold tabular-nums text-slate-700">
                {jobsBoot ? (
                  jobsDelay ? (
                    <KpiValueSkeleton className="h-[20px] min-w-[1.5rem] rounded-md" />
                  ) : (
                    <PanelCountStatic />
                  )
                ) : (
                  doneJobs.length
                )}
              </span>
            </div>

            <div className="flex flex-col px-1.5 py-0">
              {jobsBoot ? (
                <ListPanelRowsSkeleton showPulse={jobsDelay} />
              ) : doneJobs.length === 0 ? (
                <div className="px-2 py-2 text-center">
                  <p className="text-[11px] font-medium leading-snug text-slate-600">
                    {t("dashboard.operational.recent_done.empty_title")}
                  </p>
                  <p className="sr-only">{t("dashboard.operational.recent_done.empty_description")}</p>
                </div>
              ) : (
                <ul className="divide-y divide-slate-100">
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

            <div className="border-t border-slate-100 px-3 py-1.5">
              <p className="text-[10px] leading-snug text-slate-500">
                {t("dashboard.operational.recent_done.footer_pipeline")}{" "}
                <span className="font-semibold tabular-nums text-slate-800">
                  {hasQuoteAmountsInPipeline ? `€ ${amountTotal.toFixed(0)}` : "—"}
                </span>
              </p>
            </div>
          </section>

          <OperationalPanel
            variant="attention"
            compact
            icon={AlertCircle}
            title={t("dashboard.operational.attention.title")}
            description={t("dashboard.operational.attention.description")}
            count={
              operationalBoot ? (
                operationalDelay ? (
                  <KpiValueSkeleton className="h-[20px] min-w-[1.5rem] rounded-md" />
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
                  "h-8",
                  needsAttentionEmpty
                    ? "w-full justify-center gap-1.5 border-slate-300 font-semibold text-slate-800 hover:bg-slate-50 hover:text-slate-950 sm:w-auto"
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
                <div className="px-2 py-2 text-center">
                  <p className="text-[12px] font-semibold text-slate-900">
                    {t("dashboard.operational.attention.empty_title")}
                  </p>
                  <p className="mt-0.5 text-[10px] font-medium leading-snug text-slate-500">
                    {t("dashboard.operational.attention.empty_description")}
                  </p>
                </div>
              ) : (
                <>
                  {operational?.attention.summary ? (
                    <p className="px-0.5 pb-1 text-[10px] font-medium leading-snug text-slate-500">
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
                  <ul className="divide-y divide-slate-100">
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
                                <StatusBadge status={item.status} className="ring-1 ring-[#4A7C59]/35">
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
        </div>
      </div>
    </div>
  );
}
