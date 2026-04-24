"use client";

import { Sparkles } from "lucide-react";
import Link from "next/link";
import { t } from "@/lib/i18n";
import { cn } from "@/lib/utils";

export function SidebarProductUpdates() {
  return (
    <div
      className={cn(
        "rounded-[6px] border border-zinc-700/50 bg-zinc-800/25 px-2 py-1.5",
        "text-zinc-500",
      )}
      role="note"
    >
      <div className="flex gap-1.5">
        <Sparkles
          className="mt-0.5 h-3 w-3 shrink-0 text-zinc-600"
          strokeWidth={1.75}
          aria-hidden
        />
        <div className="min-w-0 space-y-0.5">
          <p className="text-[11px] font-medium leading-tight text-zinc-400">
            {t("nav.product_updates.title")}
          </p>
          <p className="text-[10px] font-normal leading-snug text-zinc-500">
            {t("nav.product_updates.body")}
          </p>
          <p className="text-[9px] leading-snug text-zinc-600">{t("nav.product_updates.latest")}</p>
        </div>
      </div>
      <Link
        href="/updates"
        className={cn(
          "motion-interactive mt-1 block text-[10px] font-medium text-zinc-500 underline-offset-2",
          "hover:text-zinc-400 hover:underline focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary/25 focus-visible:ring-offset-2 focus-visible:ring-offset-zinc-900",
        )}
      >
        {t("nav.product_updates.see_whats_new")}
      </Link>
    </div>
  );
}
