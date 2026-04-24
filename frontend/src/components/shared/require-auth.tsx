"use client";

import { ReactNode, useEffect } from "react";
import { usePathname, useRouter } from "next/navigation";
import { useSessionContext } from "@/components/shared/session-provider";
import { APP_ROUTES } from "@/lib/routes";

type RequireAuthProps = {
  children: ReactNode;
};

export function RequireAuth({ children }: RequireAuthProps) {
  const { isLoading, isAuthenticated } = useSessionContext();
  const router = useRouter();
  const pathname = usePathname();

  useEffect(() => {
    if (isLoading || isAuthenticated) {
      return;
    }
    const next = pathname || APP_ROUTES.dashboard;
    router.replace(`${APP_ROUTES.login}?next=${encodeURIComponent(next)}`);
  }, [isAuthenticated, isLoading, pathname, router]);

  if (isLoading) {
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
