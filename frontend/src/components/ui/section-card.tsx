import { type ReactNode } from "react";

import { cn } from "@/lib/utils";

type SectionCardProps = {
  children: ReactNode;
  className?: string;
  /** Slightly tighter padding for dense tables */
  padding?: "default" | "none";
};

/**
 * Primary content surface: white panel, standard radius, calm shadow.
 */
export function SectionCard({ children, className, padding = "default" }: SectionCardProps) {
  return (
    <div
      className={cn(
        "surface-card overflow-hidden",
        padding === "default" ? "p-4 sm:p-5" : "",
        className,
      )}
    >
      {children}
    </div>
  );
}
