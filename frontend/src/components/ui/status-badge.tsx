import { Badge } from "@/components/ui/badge";
import { statusTone } from "@/lib/presentation";
import { cn } from "@/lib/utils";

type StatusBadgeProps = {
  status: string | null | undefined;
  children: React.ReactNode;
  className?: string;
};

/**
 * Status chips with shared shape + semantic colors (see `statusTone`).
 */
export function StatusBadge({ status, children, className }: StatusBadgeProps) {
  return (
    <Badge
      variant="outline"
      className={cn(
        "h-[22px] min-h-[22px] rounded-md px-2 py-0 text-[10px] font-semibold leading-none tracking-tight",
        statusTone(status),
        className,
      )}
    >
      {children}
    </Badge>
  );
}
