"use client";

import { Menu } from "@base-ui/react/menu";
import { Bell, BookOpen, LayoutGrid, Search, Settings } from "lucide-react";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { useEffect, useRef } from "react";
import { t } from "@/lib/i18n";
import { shellPageTitle } from "@/lib/shell-page-title";
import { cn } from "@/lib/utils";

const iconLinkClass =
  "motion-interactive flex h-8 w-8 shrink-0 items-center justify-center rounded-lg border border-transparent bg-transparent text-zinc-500 hover:bg-zinc-950/[0.055] hover:text-zinc-800 active:translate-y-px active:bg-zinc-950/[0.08] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary/22 focus-visible:ring-offset-0";

/** Placeholder: wire to real notification feed later */
function useNotificationCount(): number {
  return 0;
}

export function AppUtilityBar() {
  const pathname = usePathname() ?? "";
  const isDashboardRoute = pathname === "/dashboard" || pathname.startsWith("/dashboard/");
  const pageTitle = isDashboardRoute ? "" : shellPageTitle(pathname);
  const searchRef = useRef<HTMLInputElement>(null);
  const notificationCount = useNotificationCount();
  const hasNotifications = notificationCount > 0;

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      const tag = document.activeElement?.tagName;
      if (e.key !== "/" || tag === "INPUT" || tag === "TEXTAREA" || tag === "SELECT") {
        return;
      }
      e.preventDefault();
      searchRef.current?.focus();
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, []);

  return (
    <header className="sticky top-0 z-30 shrink-0 border-b border-zinc-200/75 bg-white">
      <div className="flex h-11 items-center gap-2 px-3 sm:gap-2.5 sm:px-3.5">
        {pageTitle ? (
          <div className="min-w-0 max-w-[42%] shrink sm:max-w-[min(40vw,320px)]">
            <h1 className="truncate text-[14px] font-semibold leading-tight tracking-[-0.02em] text-zinc-950 sm:text-[15px]">
              {pageTitle}
            </h1>
          </div>
        ) : null}

        {/* Search */}
        <div className="relative min-w-0 flex-1 max-w-md">
          <Search
            className="pointer-events-none absolute left-2.5 top-1/2 h-3.5 w-3.5 -translate-y-1/2 text-zinc-400"
            aria-hidden
          />
          <input
            ref={searchRef}
            type="search"
            name="app-search"
            placeholder={t("shell.search_placeholder")}
            autoComplete="off"
            className={cn(
              "motion-interactive h-8 w-full rounded-lg border border-zinc-200/85 bg-[#f8f9fb] py-1.5 pl-8 pr-[2.75rem] text-[13px] font-medium text-zinc-800 shadow-none outline-none",
              "placeholder:text-zinc-400",
              "hover:border-zinc-300/75 hover:bg-white",
              "focus:border-primary/40 focus:bg-white focus:shadow-[0_0_0_3px_rgba(31,122,62,0.14)] focus:ring-0 focus:outline-none",
            )}
          />
          <kbd
            className="pointer-events-none absolute right-2 top-1/2 hidden h-[22px] -translate-y-1/2 select-none items-center rounded border border-zinc-200/70 bg-white px-1.5 font-mono text-[10px] font-medium leading-[14px] text-zinc-400 sm:inline-flex"
            aria-hidden
          >
            /
          </kbd>
        </div>

        <div className="ml-auto flex shrink-0 items-center gap-1">
          {/* Apps / quick nav */}
          <Menu.Root modal={false}>
            <Menu.Trigger
              type="button"
              className={cn(
                iconLinkClass,
                "data-[popup-open]:bg-zinc-950/[0.07] data-[popup-open]:text-zinc-800",
              )}
              aria-label={t("shell.apps_aria")}
            >
              <LayoutGrid className="h-4 w-4" strokeWidth={1.75} aria-hidden />
            </Menu.Trigger>
            <Menu.Portal>
              <Menu.Positioner className="z-[100] outline-none" side="bottom" align="end" sideOffset={6}>
                <Menu.Popup className="app-popover-animate min-w-[200px] origin-top rounded-[12px] border border-zinc-200/90 bg-white p-1 shadow-[0_8px_28px_-6px_rgba(15,23,42,0.12),0_4px_12px_-8px_rgba(15,23,42,0.08)] outline-none">
                  <Menu.LinkItem
                    className="motion-interactive flex items-center rounded-[10px] px-2.5 py-2 text-[13px] font-medium text-zinc-700 outline-none hover:bg-zinc-100/90 data-[highlighted]:bg-zinc-100/90"
                    href="/dashboard"
                    closeOnClick={true}
                  >
                    {t("nav.items.dashboard")}
                  </Menu.LinkItem>
                  <Menu.LinkItem
                    className="motion-interactive flex items-center rounded-[10px] px-2.5 py-2 text-[13px] font-medium text-zinc-700 outline-none hover:bg-zinc-100/90 data-[highlighted]:bg-zinc-100/90"
                    href="/quotes"
                    closeOnClick={true}
                  >
                    {t("nav.items.quotes")}
                  </Menu.LinkItem>
                  <Menu.LinkItem
                    className="motion-interactive flex items-center rounded-[10px] px-2.5 py-2 text-[13px] font-medium text-zinc-700 outline-none hover:bg-zinc-100/90 data-[highlighted]:bg-zinc-100/90"
                    href="/jobs"
                    closeOnClick={true}
                  >
                    {t("nav.items.jobs")}
                  </Menu.LinkItem>
                  <Menu.LinkItem
                    className="motion-interactive flex items-center rounded-[10px] px-2.5 py-2 text-[13px] font-medium text-zinc-700 outline-none hover:bg-zinc-100/90 data-[highlighted]:bg-zinc-100/90"
                    href="/agenda"
                    closeOnClick={true}
                  >
                    {t("nav.items.agenda")}
                  </Menu.LinkItem>
                </Menu.Popup>
              </Menu.Positioner>
            </Menu.Portal>
          </Menu.Root>

          {/* Notifications */}
          <Menu.Root modal={false}>
            <Menu.Trigger
              type="button"
              className={cn(iconLinkClass, "relative", "data-[popup-open]:bg-zinc-950/[0.07]")}
              aria-label={t("shell.notifications_aria")}
            >
              <Bell className="h-4 w-4" strokeWidth={1.75} aria-hidden />
              {hasNotifications ? (
                <span className="absolute right-1.5 top-1.5 h-2 w-2 rounded-full border-2 border-white bg-primary" />
              ) : null}
            </Menu.Trigger>
            <Menu.Portal>
              <Menu.Positioner className="z-[100] outline-none" side="bottom" align="end" sideOffset={6}>
                <Menu.Popup className="app-popover-animate w-[min(100vw-2rem,20rem)] origin-top rounded-[12px] border border-zinc-200/90 bg-white p-0 shadow-[0_8px_28px_-6px_rgba(15,23,42,0.12),0_4px_12px_-8px_rgba(15,23,42,0.08)] outline-none">
                  <div className="border-b border-zinc-100 px-3 py-2">
                    <p className="text-[12px] font-semibold tracking-[-0.01em] text-zinc-900">
                      {t("shell.notifications_title")}
                    </p>
                  </div>
                  <div className="max-h-[min(60vh,320px)] overflow-y-auto p-3">
                    {hasNotifications ? (
                      <ul className="space-y-1">
                        <li>
                          <button
                            type="button"
                            className="motion-interactive w-full rounded-[10px] px-2 py-2 text-left text-[13px] text-zinc-700 hover:bg-zinc-50 active:scale-[0.99]"
                          >
                            {t("shell.notifications_sample")}
                          </button>
                        </li>
                      </ul>
                    ) : (
                      <p className="py-6 text-center text-[13px] leading-relaxed text-zinc-500">
                        {t("shell.notifications_empty")}
                      </p>
                    )}
                  </div>
                </Menu.Popup>
              </Menu.Positioner>
            </Menu.Portal>
          </Menu.Root>

          <Link href="/settings" className={iconLinkClass} aria-label={t("shell.settings_aria")}>
            <Settings className="h-4 w-4" strokeWidth={1.75} aria-hidden />
          </Link>

          <Link
            href="/handleiding"
            className={cn(
              "motion-interactive ml-0.5 inline-flex h-8 shrink-0 items-center gap-1 rounded-lg px-2 text-[12px] font-medium leading-[14px] text-zinc-500",
              "hover:bg-zinc-950/[0.055] hover:text-zinc-800",
              "active:translate-y-px active:bg-zinc-950/[0.08]",
              "focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary/22 focus-visible:ring-offset-0",
            )}
          >
            <BookOpen className="h-3.5 w-3.5 shrink-0 text-zinc-400" strokeWidth={2} aria-hidden />
            <span className="hidden sm:inline">{t("shell.guide")}</span>
          </Link>
        </div>
      </div>
    </header>
  );
}
