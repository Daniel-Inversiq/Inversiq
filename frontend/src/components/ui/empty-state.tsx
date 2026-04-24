import { type LucideIcon } from "lucide-react";
import { type ReactNode } from "react";

import { cn } from "@/lib/utils";

type EmptyStateProps = {
  icon?: LucideIcon;
  title: ReactNode;
  description?: ReactNode;
  /** Optional hint / secondary panel */
  hint?: ReactNode;
  children?: ReactNode;
  className?: string;
};

/**
 * Calm empty state: title + one sentence + optional hint block.
 */
export function EmptyState({ icon: Icon, title, description, hint, children, className }: EmptyStateProps) {
  return (
    <div
      className={cn(
        "surface-card flex flex-col items-center rounded-xl px-5 py-10 text-center sm:px-8 sm:py-12",
        className,
      )}
    >
      {Icon ? (
        <span className="flex h-11 w-11 items-center justify-center rounded-full border border-zinc-200/90 bg-zinc-50/90 text-zinc-500">
          <Icon className="h-5 w-5" aria-hidden />
        </span>
      ) : null}
      <h2 className={cn("type-section-title text-balance text-zinc-950", Icon ? "mt-4" : "")}>{title}</h2>
      {description ? (
        <p className="type-supporting mt-2 max-w-md text-pretty text-zinc-600">{description}</p>
      ) : null}
      {hint ? (
        <div className="mt-5 w-full max-w-lg rounded-lg border border-zinc-200/80 bg-zinc-50/70 px-4 py-3 text-left text-[13px] font-medium leading-relaxed text-zinc-700">
          {hint}
        </div>
      ) : null}
      {children ? <div className="mt-5 flex flex-wrap items-center justify-center gap-2">{children}</div> : null}
    </div>
  );
}
