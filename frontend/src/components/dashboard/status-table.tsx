import { DashboardSummary } from "@/types/dashboard";
import { t, tStatus } from "@/lib/i18n";

type StatusTableProps = {
  summary: DashboardSummary;
};

export function StatusTable({ summary }: StatusTableProps) {
  const maxRevenueValue = Math.max(
    ...summary.revenue_series.map((point) => point.value),
    1,
  );
  const totalStatuses = summary.status_distribution.reduce(
    (running, item) => running + item.value,
    0,
  );

  return (
    <section className="space-y-2.5">
      <header className="space-y-0">
        <p className="type-eyebrow text-zinc-600">{t("dashboard.analytics.kicker")}</p>
        <h2 className="type-section-title mt-0.5">{t("dashboard.analytics.title")}</h2>
        <p className="type-body-secondary mt-0.5 text-zinc-600">{t("dashboard.analytics.subtitle")}</p>
      </header>

      <div className="grid gap-4 lg:grid-cols-5">
        <div className="lg:col-span-3">
          <p className="type-eyebrow text-zinc-600">{t("dashboard.analytics.revenue_trend")}</p>
          <div className="mt-2 flex h-36 items-end gap-2 border-b border-zinc-200/95 pb-2">
            {summary.revenue_series.map((point) => {
              const height = Math.max(
                14,
                Math.round((point.value / maxRevenueValue) * 100),
              );
              return (
                <div key={point.label} className="flex flex-1 flex-col items-center">
                  <div
                    className="w-full rounded-t-sm bg-primary/85"
                    style={{ height: `${height}%` }}
                    aria-label={`${point.label}: ${point.value}`}
                  />
                  <span className="type-meta mt-1 text-zinc-600">{point.label}</span>
                </div>
              );
            })}
          </div>
        </div>

        <div className="lg:col-span-2">
          <p className="type-eyebrow text-zinc-600">{t("dashboard.analytics.status_distribution")}</p>
          <div className="mt-1.5 space-y-2">
            {summary.status_distribution.map((item) => {
              const ratio = totalStatuses > 0 ? (item.value / totalStatuses) * 100 : 0;
              return (
                <div key={item.label} className="space-y-1">
                  <div className="flex items-center justify-between text-sm">
                    <p className="font-medium capitalize leading-[1.45] text-zinc-800">{tStatus(item.label)}</p>
                    <p className="tabular-nums text-zinc-600">{item.value}</p>
                  </div>
                  <div className="h-1.5 rounded-full bg-zinc-100">
                    <div
                      className="h-1.5 rounded-full bg-primary/80"
                      style={{ width: `${Math.max(6, ratio)}%` }}
                    />
                  </div>
                </div>
              );
            })}
          </div>
        </div>
      </div>
    </section>
  );
}
