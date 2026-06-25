"use client";

import { Sparkles } from "lucide-react";
import Link from "next/link";
import { t } from "@/lib/i18n";
import { cn } from "@/lib/utils";

type SidebarProductUpdatesProps = {
  /** Dark sidebar chrome */
  forDarkSidebar?: boolean;
};

export function SidebarProductUpdates({ forDarkSidebar = false }: SidebarProductUpdatesProps) {
  return (
    <div
      className={cn(
        "rounded-xl border px-2.5 py-2 shadow-sm",
        forDarkSidebar
          ? "border-slate-700/55 bg-slate-800/35 text-slate-400 shadow-none"
          : "border-blue-100/90 bg-blue-50/80 text-blue-900/80",
      )}
      role="note"
    >
      <div className="flex gap-1.5">
        <Sparkles
          className={cn(
            "mt-0.5 h-3 w-3 shrink-0",
            forDarkSidebar ? "text-slate-500" : "text-blue-600",
          )}
          strokeWidth={1.75}
          aria-hidden
        />
        <div className="min-w-0 space-y-0.5">
          <p
            className={cn(
              "text-[11px] font-medium leading-tight",
              forDarkSidebar ? "text-slate-200" : "text-blue-900",
            )}
          >
            {t("nav.product_updates.title")}
          </p>
          <p
            className={cn(
              "text-[10px] font-normal leading-snug",
              forDarkSidebar ? "text-slate-500" : "text-blue-800/80",
            )}
          >
            {t("nav.product_updates.body")}
          </p>
          <p
            className={cn(
              "text-[9px] leading-snug",
              forDarkSidebar ? "text-slate-600" : "text-blue-700/70",
            )}
          >
            {t("nav.product_updates.latest")}
          </p>
        </div>
      </div>
      <Link
        href="/updates"
        className={cn(
          "motion-interactive mt-1 block text-[10px] font-semibold underline-offset-2",
          forDarkSidebar
            ? "text-slate-300 hover:text-slate-100 hover:underline focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-slate-500/30 focus-visible:ring-offset-2 focus-visible:ring-offset-[#111827]"
            : "text-blue-700 hover:text-blue-800 hover:underline focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary/25 focus-visible:ring-offset-2 focus-visible:ring-offset-blue-50",
        )}
      >
        {t("nav.product_updates.see_whats_new")}
      </Link>
    </div>
  );
}
