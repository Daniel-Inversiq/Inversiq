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
    <aside className="sticky top-3 flex h-[calc(100vh-1.5rem)] min-h-0 w-[240px] shrink-0 flex-col overflow-hidden rounded-[12px] border border-zinc-800/90 bg-zinc-900 shadow-[0_1px_3px_rgba(0,0,0,0.35)]">
      <div className="shrink-0 px-3 pb-2 pt-3">
        <WorkspaceSwitcher forDarkSidebar />
      </div>
      <div className="mx-3 h-px shrink-0 bg-zinc-700/80" aria-hidden />
      <nav className="min-h-0 flex-1 space-y-3 overflow-y-auto overscroll-contain px-3 pb-3 pt-2">
        {appNavigationGroups.map((group) => (
          <section key={group.labelKey} className="space-y-1.5">
            <p className="type-sidebar-section px-0.5 text-zinc-500">{t(group.labelKey)}</p>
            <div className="space-y-px">
              {group.items.map((item) => {
                const isActive = pathname === item.href || pathname.startsWith(`${item.href}/`);
                const Icon = item.icon;
                return (
                  <Link
                    key={item.href}
                    href={item.href}
                    className={cn(
                      "group type-sidebar-nav motion-interactive flex w-full min-w-0 items-center gap-2 rounded-[8px] px-2 py-1.5 text-[13px] font-medium leading-[18px]",
                      isActive
                        ? "bg-primary/10 text-white shadow-[inset_3px_0_0_0_rgba(31,122,62,0.72)] active:bg-primary/[0.14]"
                        : "text-zinc-300 hover:bg-zinc-800 hover:text-zinc-50 active:bg-zinc-800/90",
                    )}
                  >
                    <Icon
                      className={cn(
                        "h-[17px] w-[17px] shrink-0 stroke-[1.5] motion-interactive",
                        isActive ? "text-primary" : "text-zinc-400 group-hover:text-zinc-300",
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
      <div className="shrink-0 space-y-2 border-t border-zinc-800 bg-zinc-900 px-3 pb-2.5 pt-2.5">
        <SidebarProductUpdates />
        <div className="space-y-px">
          {appFooterNavigation.map((item) => {
              const Icon = item.icon;
              const isActive = pathname === item.href || pathname.startsWith(`${item.href}/`);
              if (item.href === AUTH_ROUTES.logout) {
                return (
                  <button
                    key={item.href}
                    type="button"
                    onClick={handleLogout}
                    className="group type-sidebar-nav motion-interactive flex w-full items-center gap-2 rounded-[8px] px-2 py-1.5 text-[13px] font-medium text-zinc-300 hover:bg-zinc-800 hover:text-zinc-50 active:bg-zinc-800/90"
                  >
                    <Icon className="h-[18px] w-[18px] shrink-0 text-zinc-400 group-hover:text-zinc-300" />
                    <span>{t(item.labelKey)}</span>
                  </button>
                );
              }
              return (
                <Link
                  key={item.href}
                  href={item.href}
                  className={cn(
                    "group type-sidebar-nav motion-interactive flex items-center gap-2 rounded-[8px] px-2 py-1.5 text-[13px] font-medium",
                    isActive
                      ? "bg-primary/10 text-white shadow-[inset_3px_0_0_0_rgba(31,122,62,0.72)] active:bg-primary/[0.14]"
                      : "text-zinc-300 hover:bg-zinc-800 hover:text-zinc-50 active:bg-zinc-800/90",
                  )}
                >
                  <Icon
                    className={cn(
                      "h-[18px] w-[18px] shrink-0 motion-interactive",
                      isActive ? "text-primary" : "text-zinc-400 group-hover:text-zinc-300",
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
