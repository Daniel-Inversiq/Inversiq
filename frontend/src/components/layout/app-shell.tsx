import { ReactNode } from "react";
import { AppSidebar } from "@/components/layout/app-sidebar";
import { AppUtilityBar } from "@/components/layout/app-utility-bar";

type AppShellProps = {
  children: ReactNode;
};

export function AppShell({ children }: AppShellProps) {
  return (
    <div className="min-h-screen bg-background">
      {/* Same near-white canvas as tokens; depth from white panels + borders, not gray fills */}
      <div className="flex min-h-screen w-full flex-col gap-2.5 p-3 sm:p-3.5 lg:flex-row lg:items-stretch">
        <div className="hidden min-h-0 shrink-0 self-stretch lg:flex lg:flex-col">
          <AppSidebar />
        </div>
        {/* White chrome column; main uses bg-background for the working canvas */}
        <div className="flex min-h-0 min-w-0 flex-1 flex-col overflow-hidden rounded-xl border border-zinc-200/75 bg-white shadow-[0_1px_0_rgba(15,23,42,0.03)]">
          <AppUtilityBar />
          <main className="min-h-0 flex-1 overflow-auto bg-background px-4 pb-5 pt-3 sm:px-6 sm:pb-6 sm:pt-3.5 lg:px-8">
            {children}
          </main>
        </div>
      </div>
    </div>
  );
}
