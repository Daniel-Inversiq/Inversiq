import { ReactNode } from "react";
import { RequireAuth } from "@/components/shared/require-auth";
import { DemoShell } from "@/components/layout/demo-shell";

export default function DemoLayout({ children }: { children: ReactNode }) {
  return (
    <RequireAuth>
      <DemoShell>{children}</DemoShell>
    </RequireAuth>
  );
}
