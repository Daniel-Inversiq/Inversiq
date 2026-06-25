"use client";

import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { useQueryClient } from "@tanstack/react-query";
import { SidebarProductUpdates } from "@/components/layout/sidebar-product-updates";
import { WorkspaceSwitcher } from "@/components/layout/workspace-switcher";
import { t } from "@/lib/i18n";
import { appFooterNavigation, appNavigationGroups } from "@/lib/navigation";
import { logout } from "@/lib/api/session";
import { APP_ROUTES, AUTH_ROUTES } from "@/lib/routes";
import { cn } from "@/lib/utils";

export function AppSidebar() {
  const pathname = usePathname();
  const router = useRouter();
  const queryClient = useQueryClient();

  async function handleLogout() {
    try {
      await logout();
    } finally {
      queryClient.setQueryData(["session", "me"], null);
      router.replace(APP_ROUTES.login);
    }
  }

  return (
    <aside className="sticky top-3 flex h-[calc(100vh-1.5rem)] min-h-0 w-[244px] shrink-0 flex-col overflow-hidden rounded-lg border border-[#2A312B] bg-[#1A1D1A] shadow-sm">
      <div className="shrink-0 px-2.5 pb-1.5 pt-2.5">
        <WorkspaceSwitcher forDarkSidebar />
      </div>
      <div className="mx-2.5 h-px shrink-0 bg-[#2E3630]" aria-hidden />
      <nav className="min-h-0 flex-1 space-y-2.5 overflow-y-auto overscroll-contain px-2.5 pb-2.5 pt-2">
        {appNavigationGroups.map((group) => (
          <section key={group.labelKey} className="space-y-1">
            <p className="type-sidebar-section px-1 text-[#A79E93]">{t(group.labelKey)}</p>
            <div className="space-y-1">
              {group.items.map((item) => {
                const isActive = pathname === item.href || pathname.startsWith(`${item.href}/`);
                const Icon = item.icon;
                return (
                  <Link
                    key={item.href}
                    href={item.href}
                    className={cn(
                      "group type-sidebar-nav flex w-full min-w-0 items-center gap-2 rounded-lg px-3 py-2 text-[13px] font-medium leading-[18px] transition-all duration-150",
                      isActive
                        ? "bg-[rgba(59,130,246,0.12)] text-white"
                        : "text-slate-400 hover:bg-[rgba(255,255,255,0.04)] hover:text-slate-200 active:bg-[rgba(255,255,255,0.06)]",
                    )}
                  >
                    <Icon
                      className={cn(
                        "h-[17px] w-[17px] shrink-0 stroke-[1.5] transition-all duration-150",
                        isActive ? "text-blue-400" : "text-slate-500 group-hover:text-slate-300",
                      )}
                    />
                    <span className="min-w-0 flex-1 truncate font-medium">{t(item.labelKey)}</span>
                  </Link>
                );
              })}
            </div>
          </section>
        ))}
      </nav>
      <div className="shrink-0 space-y-1.5 border-t border-[#2A312B] bg-[#1A1D1A] px-2.5 pb-2 pt-2">
        <SidebarProductUpdates forDarkSidebar />
        <div className="space-y-1">
          {appFooterNavigation.map((item) => {
              const Icon = item.icon;
              const isActive = pathname === item.href || pathname.startsWith(`${item.href}/`);
              if (item.href === AUTH_ROUTES.logout) {
                return (
                  <button
                    key={item.href}
                    type="button"
                    onClick={handleLogout}
                    className="group type-sidebar-nav flex w-full items-center gap-2 rounded-lg px-3 py-2 text-[13px] font-medium text-slate-400 transition-all duration-150 hover:bg-[rgba(255,255,255,0.04)] hover:text-slate-200 active:bg-[rgba(255,255,255,0.06)]"
                  >
                    <Icon className="h-[18px] w-[18px] shrink-0 text-slate-500 transition-all duration-150 group-hover:text-slate-300" />
                    <span>{t(item.labelKey)}</span>
                  </button>
                );
              }
              return (
                <Link
                  key={item.href}
                  href={item.href}
                    className={cn(
                    "group type-sidebar-nav flex w-full items-center gap-2 rounded-lg px-3 py-2 text-[13px] font-medium transition-all duration-150",
                    isActive
                      ? "bg-[rgba(59,130,246,0.12)] text-white"
                      : "text-slate-400 hover:bg-[rgba(255,255,255,0.04)] hover:text-slate-200 active:bg-[rgba(255,255,255,0.06)]",
                  )}
                >
                  <Icon
                    className={cn(
                      "h-[18px] w-[18px] shrink-0 transition-all duration-150",
                      isActive ? "text-blue-400" : "text-slate-500 group-hover:text-slate-300",
                    )}
                  />
                  <span>{t(item.labelKey)}</span>
                </Link>
              );
            })}
        </div>
      </div>
    </aside>
  );
}
