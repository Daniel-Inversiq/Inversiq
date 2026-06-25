import { ArrowRight, Briefcase, FileText } from "lucide-react";
import Link from "next/link";
import { t } from "@/lib/i18n";
import { buttonVariants } from "@/components/ui/button";
import { cn } from "@/lib/utils";
import type { SectorDashboardComponentProps } from "@/verticals/dashboard/types";

export default function ConstructionDashboardTools({ metrics }: SectorDashboardComponentProps) {
  const quoteReadiness = Math.min(
    100,
    metrics.leadsCount > 0 ? Math.round((metrics.openQuotesCount / metrics.leadsCount) * 100) : 0,
  );

  return (
    <div className="w-full rounded-2xl border border-slate-200/70 bg-white p-4 shadow-sm sm:p-5">
      <div className="mb-4">
        <p className="text-[10px] font-semibold uppercase tracking-[0.05em] text-slate-500">Construction</p>
        <h2 className="text-lg font-semibold tracking-tight text-slate-900">Quote builder and project tracker</h2>
      </div>
      <div className="grid gap-3 md:grid-cols-2">
        <article className="flex flex-col rounded-2xl border border-slate-200/70 bg-white p-4 shadow-sm">
          <span className="inline-flex h-9 w-9 items-center justify-center rounded-lg border border-blue-200/80 bg-blue-50 text-blue-700">
            <FileText className="h-4 w-4" aria-hidden />
          </span>
          <p className="mt-3 text-sm font-semibold text-slate-900">Quote builder</p>
          <p className="mt-1 text-sm text-slate-600">
            {t("dashboard.operational.kpi.open_quotes.label")}: {metrics.openQuotesCount}
          </p>
          <p className="text-xs text-slate-500">
            {metrics.hasPipelineValue ? `Pipeline value: € ${metrics.pipelineValueTotal.toFixed(0)}` : "No pipeline value yet"}
          </p>
          <Link
            href="/offertes"
            className={cn(
              buttonVariants({ variant: "outline", size: "sm" }),
              "mt-auto pt-4",
              "h-9 w-full justify-center gap-2 rounded-lg border-slate-200/80 font-semibold text-slate-800 hover:bg-slate-50",
            )}
          >
            Open quote builder
            <ArrowRight className="h-4 w-4 shrink-0" aria-hidden />
          </Link>
        </article>
        <article className="flex flex-col rounded-2xl border border-slate-200/70 bg-white p-4 shadow-sm">
          <span className="inline-flex h-9 w-9 items-center justify-center rounded-lg border border-blue-200/80 bg-blue-50 text-blue-700">
            <Briefcase className="h-4 w-4" aria-hidden />
          </span>
          <p className="mt-3 text-sm font-semibold text-slate-900">Project tracker</p>
          <p className="mt-1 text-sm text-slate-600">Quote readiness: {quoteReadiness}%</p>
          <div className="mt-2 h-1.5 overflow-hidden rounded-full bg-slate-200/90">
            <div className="h-full bg-blue-600/70" style={{ width: `${quoteReadiness}%` }} />
          </div>
          <p className="mt-2 text-xs text-slate-500">
            Active jobs: {metrics.activeJobsCount}
          </p>
          <Link
            href="/jobs"
            className={cn(
              buttonVariants({ variant: "outline", size: "sm" }),
              "mt-auto pt-4",
              "h-9 w-full justify-center gap-2 rounded-lg border-slate-200/80 font-semibold text-slate-800 hover:bg-slate-50",
            )}
          >
            View projects
            <ArrowRight className="h-4 w-4 shrink-0" aria-hidden />
          </Link>
        </article>
      </div>
    </div>
  );
}
