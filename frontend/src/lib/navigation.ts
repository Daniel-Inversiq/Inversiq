import {
  BriefcaseBusiness,
  CalendarDays,
  CreditCard,
  FileText,
  FolderOpen,
  Home,
  LifeBuoy,
  LogOut,
  ShieldCheck,
  Settings,
} from "lucide-react";
import type { LucideIcon } from "lucide-react";
import { APP_ROUTES, AUTH_ROUTES } from "@/lib/routes";

export type AppNavigationItem = {
  labelKey: string;
  href: string;
  icon: LucideIcon;
};

export type AppNavigationGroup = {
  labelKey: string;
  items: AppNavigationItem[];
};

export const appNavigationGroups: AppNavigationGroup[] = [
  {
    labelKey: "nav.groups.core",
    items: [
      { labelKey: "nav.items.dashboard", href: APP_ROUTES.dashboard, icon: Home },
      { labelKey: "nav.items.quotes", href: "/quotes", icon: FileText },
      { labelKey: "nav.items.jobs", href: "/jobs", icon: BriefcaseBusiness },
      { labelKey: "nav.items.review", href: "/review", icon: ShieldCheck },
      { labelKey: "nav.items.agenda", href: "/agenda", icon: CalendarDays },
      { labelKey: "nav.items.workspaces", href: "/workspaces", icon: FolderOpen },
    ],
  },
  {
    labelKey: "nav.groups.system",
    items: [{ labelKey: "nav.items.settings", href: "/settings", icon: Settings }],
  },
];

export const appFooterNavigation: AppNavigationItem[] = [
  {
    labelKey: "nav.footer.subscription",
    href: "/billing",
    icon: CreditCard,
  },
  { labelKey: "nav.footer.support", href: "mailto:support@inversiq.com", icon: LifeBuoy },
  { labelKey: "nav.footer.logout", href: AUTH_ROUTES.logout, icon: LogOut },
];
