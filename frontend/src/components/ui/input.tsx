import * as React from "react"
import { Input as InputPrimitive } from "@base-ui/react/input"

import { cn } from "@/lib/utils"

function Input({ className, type, ...props }: React.ComponentProps<"input">) {
  return (
    <InputPrimitive
      type={type}
      data-slot="input"
      className={cn(
        "h-9 w-full min-w-0 rounded-[min(var(--radius-lg),12px)] border border-zinc-200/90 bg-white px-3 py-2 font-sans text-sm text-foreground shadow-[inset_0_1px_0_rgba(255,255,255,0.85)] outline-none transition-[color,box-shadow,border-color] duration-[130ms] file:inline-flex file:h-6 file:border-0 file:bg-transparent file:text-sm file:font-medium file:text-foreground placeholder:text-zinc-400 focus-visible:border-primary/45 focus-visible:ring-[3px] focus-visible:ring-primary/18 disabled:pointer-events-none disabled:cursor-not-allowed disabled:bg-zinc-50/90 disabled:opacity-55 aria-invalid:border-destructive aria-invalid:ring-[3px] aria-invalid:ring-destructive/18 dark:bg-input/45 dark:disabled:bg-input/80 dark:aria-invalid:border-destructive/50 dark:aria-invalid:ring-destructive/35",
        className
      )}
      {...props}
    />
  )
}

export { Input }
