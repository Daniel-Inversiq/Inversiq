"use client";

import { ReactNode } from "react";
import Link from "next/link";

export function DemoShell({ children }: { children: ReactNode }) {
  return (
    <div className="flex min-h-screen flex-col bg-zinc-50">
      {/* Top bar */}
      <header className="sticky top-0 z-40 flex h-14 items-center justify-between border-b border-zinc-200 bg-white px-6 shadow-sm">
        <div className="flex items-center gap-3">
          <Link href="/workspaces" className="flex items-center gap-2.5">
            <span className="text-[15px] font-semibold tracking-tight text-zinc-900">
              Inversiq
            </span>
          </Link>
          <span className="hidden h-4 w-px bg-zinc-200 sm:block" />
          <span className="hidden text-[13px] text-zinc-500 sm:block">
            Workspace Intelligence
          </span>
        </div>
        <div className="flex items-center gap-2">
          <span className="rounded-full bg-zinc-100 px-3 py-1 text-[11px] font-medium text-zinc-500">
            Demo
          </span>
        </div>
      </header>

      {/* Page content */}
      <main className="flex-1">{children}</main>
    </div>
  );
}
