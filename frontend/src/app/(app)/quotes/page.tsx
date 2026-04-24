"use client";

import { OffersTable } from "@/components/offers/offers-table";
import { HelpTooltip } from "@/components/ui/help-tooltip";
import { t } from "@/lib/i18n";

export default function QuotesPage() {
  return (
    <section className="mx-auto w-full max-w-[min(1480px,100%)] space-y-2.5">
      <header className="space-y-1">
        <p className="text-[10px] font-semibold uppercase leading-none tracking-[0.05em] text-zinc-500">{t("offers.list.header.kicker")}</p>
        <div className="flex items-center gap-2">
          <h1 className="min-w-0 flex-1 text-[22px] font-semibold leading-tight tracking-[-0.02em] text-zinc-950">{t("offers.list.header.title")}</h1>
          <HelpTooltip content={t("context_help.quotes_overview")} className="shrink-0" />
        </div>
        <div className="max-w-[min(100%,40rem)] space-y-0.5">
          <p className="text-[12px] font-medium leading-snug text-zinc-500">{t("offers.list.header.subtitle")}</p>
          <p className="text-[12px] font-medium leading-snug text-zinc-500">{t("offers.list.header.detail_line")}</p>
        </div>
      </header>
      <OffersTable />
    </section>
  );
}
