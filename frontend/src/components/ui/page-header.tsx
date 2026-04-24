import { type ReactNode } from "react";

import { cn } from "@/lib/utils";

type PageHeaderProps = {
  kicker?: ReactNode;
  title: ReactNode;
  description?: ReactNode;
  /** Override width/typography on the supporting line (default keeps a readable measure). */
  descriptionClassName?: string;
  /** Right column: date, actions, or metadata */
  aside?: ReactNode;
  className?: string;
};

/**
 * Consistent page title block: kicker → title → supporting line.
 * Use across app shell pages for scan-friendly hierarchy.
 */
export function PageHeader({
  kicker,
  title,
  description,
  descriptionClassName,
  aside,
  className,
}: PageHeaderProps) {
  return (
    <header
      className={cn(
        "flex flex-col gap-1.5 sm:flex-row sm:items-end sm:justify-between sm:gap-6",
        className,
      )}
    >
      <div className="min-w-0 space-y-0.5">
        {kicker ? <p className="type-kicker">{kicker}</p> : null}
        <h1 className="type-page-title">{title}</h1>
        {description ? (
          <p
            className={cn(
              "type-supporting max-w-2xl text-pretty text-zinc-600",
              descriptionClassName,
            )}
          >
            {description}
          </p>
        ) : null}
      </div>
      {aside ? <div className="shrink-0">{aside}</div> : null}
    </header>
  );
}
