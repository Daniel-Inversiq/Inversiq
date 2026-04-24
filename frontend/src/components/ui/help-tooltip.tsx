"use client";

import { Tooltip } from "@base-ui/react/tooltip";
import { CircleHelp } from "lucide-react";
import { t } from "@/lib/i18n";
import { cn } from "@/lib/utils";

type HelpTooltipProps = {
  content: string;
  className?: string;
};

/** Inline “?” help: hover/focus on desktop, tap on touch devices (Base UI tooltip). */
export function HelpTooltip({ content, className }: HelpTooltipProps) {
  return (
    <Tooltip.Root>
      <Tooltip.Trigger
        type="button"
        delay={280}
        closeDelay={80}
        className={cn(
          "inline-flex h-6 w-6 shrink-0 items-center justify-center rounded-md border border-transparent text-zinc-400 outline-none transition-colors",
          "hover:border-zinc-200/90 hover:bg-zinc-50 hover:text-zinc-600",
          "focus-visible:ring-2 focus-visible:ring-primary/25 focus-visible:ring-offset-2",
          className,
        )}
        aria-label={t("context_help.icon_aria")}
      >
        <CircleHelp className="h-3.5 w-3.5" strokeWidth={2} aria-hidden />
      </Tooltip.Trigger>
      <Tooltip.Portal>
        <Tooltip.Positioner side="top" sideOffset={8} className="z-[200] outline-none">
          <Tooltip.Popup
            className={cn(
              "max-w-[min(100vw-2rem,17rem)] rounded-lg border border-zinc-200/90 bg-white px-3 py-2.5 text-[12px] font-medium leading-snug text-zinc-700 shadow-[0_8px_28px_-6px_rgba(15,23,42,0.12),0_4px_12px_-8px_rgba(15,23,42,0.08)]",
            )}
          >
            {content}
          </Tooltip.Popup>
        </Tooltip.Positioner>
      </Tooltip.Portal>
    </Tooltip.Root>
  );
}
