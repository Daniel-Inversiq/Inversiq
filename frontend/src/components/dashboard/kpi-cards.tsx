import { DashboardSummary } from "@/types/dashboard";
import { getNumberLocale, t } from "@/lib/i18n";

type KpiCardsProps = {
  summary: DashboardSummary;
};

function formatPercent(value: number) {
  return `${new Intl.NumberFormat(getNumberLocale(), { maximumFractionDigits: 1 }).format(
    value,
  )}%`;
}

export function KpiCards({ summary }: KpiCardsProps) {
  const accepted =
    summary.status_distribution.find((status) => status.label === "signed")
      ?.value ?? 0;
  const pending =
    summary.status_distribution.find((status) => status.label === "pending")
      ?.value ?? 0;
  const total = summary.status_distribution.reduce(
    (running, item) => running + item.value,
    0,
  );

  return (
    <div className="grid gap-x-6 gap-y-3 border-y border-zinc-200/95 py-3 md:grid-cols-2 xl:grid-cols-4">
      <article className="min-w-0 space-y-0">
        <p className="type-kpi-label">{t("dashboard.kpi.conversion.label")}</p>
        <p className="type-kpi-value mt-0.5">{formatPercent(summary.kpis.sign_rate ?? 0)}</p>
        <p className="type-body-secondary mt-0.5 text-zinc-600">{t("dashboard.kpi.conversion.description")}</p>
      </article>
      <article className="min-w-0 space-y-0">
        <p className="type-kpi-label">{t("dashboard.kpi.open_quotes.label")}</p>
        <p className="type-kpi-value mt-0.5">{summary.kpis.pending_count ?? 0}</p>
        <p className="type-body-secondary mt-0.5 text-zinc-600">{t("dashboard.kpi.open_quotes.description")}</p>
      </article>
      <article className="min-w-0 space-y-0">
        <p className="type-kpi-label">{t("dashboard.kpi.accepted.label")}</p>
        <p className="type-kpi-value mt-0.5">{accepted}</p>
        <p className="type-body-secondary mt-0.5 text-zinc-600">{t("dashboard.kpi.accepted.description")}</p>
      </article>
      <article className="min-w-0 space-y-0">
        <p className="type-kpi-label">{t("dashboard.kpi.total_status_rows.label")}</p>
        <p className="type-kpi-value mt-0.5">{total}</p>
        <p className="type-body-secondary mt-0.5 text-zinc-600">
          {t("dashboard.kpi.total_status_rows.pending", { pending })}
        </p>
      </article>
    </div>
  );
}
