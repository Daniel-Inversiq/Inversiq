"use client";

import { Menu } from "@base-ui/react/menu";
import {
  Building2,
  ChevronDown,
  CreditCard,
  HelpCircle,
  LogOut,
  Settings,
  UserRound,
} from "lucide-react";
import { useRouter } from "next/navigation";
import { useCompanySettings } from "@/hooks/use-company-settings";
import { useSessionContext } from "@/components/shared/session-provider";
import { t } from "@/lib/i18n";
import { cn } from "@/lib/utils";

function workspaceInitials(name: string): string {
  const trimmed = name.trim();
  if (!trimmed) {
    return "IN";
  }
  const parts = trimmed.split(/\s+/).filter(Boolean);
  if (parts.length >= 2) {
    return `${parts[0][0] ?? ""}${parts[1][0] ?? ""}`.toUpperCase().slice(0, 2);
  }
  const word = parts[0] ?? trimmed;
  if (word.length >= 2) {
    return word.slice(0, 2).toUpperCase();
  }
  return "IN";
}

/** Two-letter initials from account email (e.g. d.van@ → DV), for the identity avatar. */
function accountInitialsFromEmail(email: string): string {
  const local = email.split("@")[0]?.trim() ?? "";
  if (!local) {
    return "IN";
  }
  const split = local.split(/[._+\-]/).filter(Boolean);
  if (split.length >= 2) {
    const a = split[0]?.[0] ?? "";
    const b = split[1]?.[0] ?? "";
    const pair = `${a}${b}`.toUpperCase();
    if (pair.length >= 2) {
      return pair.slice(0, 2);
    }
  }
  const alnum = local.replace(/[^a-zA-Z0-9]/g, "");
  if (alnum.length >= 2) {
    return alnum.slice(0, 2).toUpperCase();
  }
  if (alnum.length === 1) {
    return `${alnum}`.toUpperCase();
  }
  return "IN";
}

const menuItemClass =
  "motion-interactive flex cursor-pointer items-center gap-2.5 rounded-[10px] px-2.5 py-2 text-[13px] font-medium text-zinc-700 outline-none select-none hover:bg-zinc-100/90 data-[highlighted]:bg-zinc-100/90 data-[disabled]:cursor-not-allowed data-[disabled]:opacity-45 active:scale-[0.99]";

const menuLinkClass =
  "motion-interactive flex items-center gap-2.5 rounded-[10px] px-2.5 py-2 text-[13px] font-medium text-zinc-700 outline-none hover:bg-zinc-100/90 data-[highlighted]:bg-zinc-100/90 active:scale-[0.99]";

type WorkspaceSwitcherProps = {
  /** Dark chrome (e.g. app sidebar) — zinc-900 surface, light text */
  forDarkSidebar?: boolean;
};

export function WorkspaceSwitcher({ forDarkSidebar = false }: WorkspaceSwitcherProps) {
  const router = useRouter();
  const session = useSessionContext();
  const settingsQuery = useCompanySettings(session.isAuthenticated);

  const tenantName =
    settingsQuery.data?.company_name?.trim() ||
    session.user?.email?.split("@")[0] ||
    t("nav.tenant_workspace");
  const emailLine = session.user?.email?.trim() || "";
  const accountLine = emailLine || tenantName;
  const initials = emailLine
    ? accountInitialsFromEmail(emailLine)
    : workspaceInitials(tenantName);

  const handleLogout = async () => {
    await fetch("/auth/logout", {
      method: "POST",
      credentials: "include",
    });
    window.location.href = "/auth/login";
  };

  return (
    <Menu.Root modal={false}>
      <Menu.Trigger
        type="button"
        aria-label="Account- en werkruimtemenu"
        className={cn(
          "group/workspace font-sans motion-interactive flex w-full cursor-pointer items-center gap-2.5 rounded-lg border border-transparent bg-transparent px-2 py-2 text-left outline-none",
          "active:scale-[0.995]",
          forDarkSidebar
            ? "hover:bg-zinc-800/90 focus-visible:ring-2 focus-visible:ring-primary/25 data-[popup-open]:bg-zinc-800"
            : "hover:bg-zinc-950/[0.04] focus-visible:ring-2 focus-visible:ring-primary/15 data-[popup-open]:bg-zinc-950/[0.05]",
          "data-[popup-open]:[&_.switcher-chevron]:rotate-180",
        )}
      >
        <span className="relative shrink-0" aria-hidden>
          <span
            className={cn(
              "switcher-avatar flex h-8 w-8 items-center justify-center rounded-md text-[11px] font-semibold tracking-[-0.02em]",
              "transition-transform duration-200 ease-out will-change-transform",
              "group-hover/workspace:scale-[1.01] group-data-[popup-open]/workspace:scale-[1.01]",
              forDarkSidebar
                ? "border border-zinc-600/90 bg-zinc-800 text-zinc-100"
                : "border border-zinc-200/90 bg-white text-zinc-800",
            )}
          >
            {initials}
          </span>
          <span
            className="pointer-events-none absolute bottom-px right-px z-[1] h-1.5 w-1.5 rounded-full border border-white bg-primary shadow-[0_0_0_1px_rgba(255,255,255,0.9)]"
            aria-hidden
          />
        </span>
        <span className="min-w-0 flex-1 py-0">
          <span
            className={cn(
              "block truncate text-[17px] font-semibold leading-tight tracking-[-0.02em]",
              forDarkSidebar ? "text-zinc-100" : "text-zinc-950",
            )}
          >
            Inversiq
          </span>
          <span
            className={cn(
              "mt-1 block truncate text-[11px] font-medium leading-snug",
              forDarkSidebar ? "text-zinc-400" : "text-zinc-500",
            )}
          >
            {accountLine}
          </span>
        </span>
        <ChevronDown
          className={cn(
            "switcher-chevron h-[18px] w-[18px] shrink-0 transition-all duration-200 ease-out",
            forDarkSidebar
              ? "text-zinc-500 group-hover/workspace:text-zinc-400 group-data-[popup-open]/workspace:text-zinc-400"
              : "text-zinc-400 group-hover/workspace:text-zinc-500 group-data-[popup-open]/workspace:text-zinc-500",
          )}
          aria-hidden
          strokeWidth={2}
        />
      </Menu.Trigger>

      <Menu.Portal>
        <Menu.Positioner className="z-[100] outline-none" side="bottom" sideOffset={6} align="start">
          <Menu.Popup className="app-popover-animate min-w-[220px] origin-top-left rounded-[12px] border border-zinc-200/90 bg-white p-1 shadow-[0_8px_28px_-6px_rgba(15,23,42,0.12),0_4px_12px_-8px_rgba(15,23,42,0.08)] outline-none">
            <Menu.Item
              className={menuItemClass}
              onClick={() => {
                router.push("/settings");
              }}
            >
              <Settings className="h-4 w-4 shrink-0 text-zinc-500" aria-hidden />
              Instellingen
            </Menu.Item>
            <Menu.Item
              className={menuItemClass}
              onClick={() => {
                router.push("/settings");
              }}
            >
              <UserRound className="h-4 w-4 shrink-0 text-zinc-500" aria-hidden />
              Profiel
            </Menu.Item>
            <Menu.Item
              className={menuItemClass}
              onClick={() => {
                router.push("/billing");
              }}
            >
              <CreditCard className="h-4 w-4 shrink-0 text-zinc-500" aria-hidden />
              Abonnement
            </Menu.Item>

            <Menu.Separator className="my-1 h-px bg-zinc-100" />

            <Menu.Item className={menuItemClass} disabled>
              <Building2 className="h-4 w-4 shrink-0 text-zinc-400" aria-hidden />
              <span className="flex flex-col gap-0.5">
                <span>Werkruimte wisselen</span>
                <span className="text-[11px] font-normal text-zinc-400">Binnenkort beschikbaar</span>
              </span>
            </Menu.Item>

            <Menu.LinkItem
              className={menuLinkClass}
              href="mailto:support@inversiq.com?subject=Support%20Inversiq"
              closeOnClick={true}
            >
              <HelpCircle className="h-4 w-4 shrink-0 text-zinc-500" aria-hidden />
              Help
            </Menu.LinkItem>

            <Menu.Separator className="my-1 h-px bg-zinc-100" />

            <Menu.Item
              className={cn(menuItemClass, "text-zinc-800")}
              onClick={() => {
                void handleLogout();
              }}
            >
              <LogOut className="h-4 w-4 shrink-0 text-zinc-500" aria-hidden />
              Afmelden
            </Menu.Item>
          </Menu.Popup>
        </Menu.Positioner>
      </Menu.Portal>
    </Menu.Root>
  );
}
