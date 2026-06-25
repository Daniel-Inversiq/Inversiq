import { ReactNode } from "react";
import { AppSidebar } from "@/components/layout/app-sidebar";
import { AppUtilityBar } from "@/components/layout/app-utility-bar";

type AppShellProps = {
  children: ReactNode;
};

export function AppShell({ children }: AppShellProps) {
  return (
    <div className="min-h-screen bg-[#F7F8F7]">
      <div className="flex min-h-screen w-full flex-col gap-2 p-2 sm:p-3 lg:flex-row lg:items-stretch">
        <div className="hidden min-h-0 shrink-0 self-stretch lg:flex lg:flex-col">
          <AppSidebar />
        </div>
        <div className="flex min-h-0 min-w-0 flex-1 flex-col overflow-hidden rounded-2xl border border-zinc-200 bg-[#FFFFFF] shadow-[0_1px_3px_rgba(0,0,0,0.08)]">
          <AppUtilityBar />
          <main className="min-h-0 flex-1 overflow-auto bg-transparent px-4 pb-5 pt-3 sm:px-5 sm:pb-6 sm:pt-3 lg:px-6">
            {children}
          </main>
        </div>
      </div>
    </div>
  );
}
