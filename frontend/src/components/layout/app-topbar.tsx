"use client";

import {
  Breadcrumb,
  BreadcrumbItem,
  BreadcrumbList,
  BreadcrumbPage,
  BreadcrumbSeparator,
} from "@/components/ui/breadcrumb";
import { t } from "@/lib/i18n";
import { usePathname } from "next/navigation";

const pageTitles: Record<string, string> = {
  "/dashboard": "nav.items.dashboard",
  "/review": "nav.items.review",
  "/workflows": "nav.items.review",
  "/quotes": "nav.items.quotes",
  "/agenda": "nav.items.agenda",
  "/jobs": "nav.items.jobs",
  "/settings": "nav.items.settings",
};

export function AppTopbar() {
  const pathname = usePathname();
  const title = t(pageTitles[pathname] ?? "nav.workspace");

  return (
    <header className="sticky top-0 z-20 border-b border-zinc-200/70 bg-white/90 backdrop-blur-sm">
      <div className="flex h-[52px] items-center justify-between px-4 lg:px-6">
        <Breadcrumb>
          <BreadcrumbList>
            <BreadcrumbItem className="type-meta text-zinc-500">{t("nav.workspace")}</BreadcrumbItem>
            <BreadcrumbSeparator />
            <BreadcrumbItem>
              <BreadcrumbPage className="text-[14px] font-semibold leading-[1.2] tracking-[-0.01em] text-zinc-950">
                {title}
              </BreadcrumbPage>
            </BreadcrumbItem>
          </BreadcrumbList>
        </Breadcrumb>
        <span className="type-meta tabular-nums text-zinc-400">v0</span>
      </div>
    </header>
  );
}
