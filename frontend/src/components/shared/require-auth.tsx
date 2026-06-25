"use client";

import { ReactNode, useEffect, useState } from "react";
import { usePathname, useRouter } from "next/navigation";
import { useSessionContext } from "@/components/shared/session-provider";
import { APP_ROUTES } from "@/lib/routes";
import { getTenantMe } from "@/lib/tenant";

type RequireAuthProps = {
  children: ReactNode;
};

export function RequireAuth({ children }: RequireAuthProps) {
  const { isLoading, isAuthenticated } = useSessionContext();
  const router = useRouter();
  const pathname = usePathname();
  const [isCheckingOnboarding, setIsCheckingOnboarding] = useState(false);

  useEffect(() => {
    if (isLoading || isAuthenticated) {
      return;
    }
    const next = pathname || APP_ROUTES.dashboard;
    router.replace(`${APP_ROUTES.login}?next=${encodeURIComponent(next)}`);
  }, [isAuthenticated, isLoading, pathname, router]);

  useEffect(() => {
    if (isLoading || !isAuthenticated || !pathname) {
      return;
    }

    let cancelled = false;
    const isOnboardingPath =
      pathname === APP_ROUTES.onboarding || pathname.startsWith(`${APP_ROUTES.onboarding}/`);

    async function checkTenantOnboardingState() {
      setIsCheckingOnboarding(true);
      try {
        const tenant = await getTenantMe();
        const hasSector = Boolean((tenant.sector ?? "").trim());
        const onboardingCompleted = tenant.onboarding_completed;

        if (!isOnboardingPath) {
          if (!hasSector || onboardingCompleted === false) {
            router.replace(APP_ROUTES.onboarding);
          }
          return;
        }

        // Prevent redirect loops: onboarding only serves users without a sector.
        if (hasSector) {
          router.replace(APP_ROUTES.dashboard);
        }
      } catch {
        // Keep existing behavior; page-level error boundaries can handle API errors.
      } finally {
        if (!cancelled) {
          setIsCheckingOnboarding(false);
        }
      }
    }

    void checkTenantOnboardingState();
    return () => {
      cancelled = true;
    };
  }, [isAuthenticated, isLoading, pathname, router]);

  if (isLoading || isCheckingOnboarding) {
    return <div className="p-6 text-sm text-zinc-500">Session laden...</div>;
  }
  if (!isAuthenticated) {
    return (
      <div className="p-6 text-sm text-zinc-500" role="status" aria-live="polite">
        Sessie niet gevonden, doorsturen naar inloggen...
      </div>
    );
  }
  return <>{children}</>;
}
