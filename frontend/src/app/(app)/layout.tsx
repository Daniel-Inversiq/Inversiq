import { ReactNode } from "react";
import { AppShell } from "@/components/layout/app-shell";
import { RequireAuth } from "@/components/shared/require-auth";

export default function ApplicationLayout({
  children,
}: Readonly<{ children: ReactNode }>) {
  return (
    <RequireAuth>
      <AppShell>{children}</AppShell>
    </RequireAuth>
  );
}
