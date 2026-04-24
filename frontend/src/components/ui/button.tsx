import { Button as ButtonPrimitive } from "@base-ui/react/button"
import { cva, type VariantProps } from "class-variance-authority"

import { cn } from "@/lib/utils"

const buttonVariants = cva(
  "group/button font-sans motion-interactive inline-flex shrink-0 items-center justify-center rounded-xl border border-transparent bg-clip-padding text-sm font-semibold whitespace-nowrap outline-none select-none focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary/28 focus-visible:ring-offset-2 disabled:pointer-events-none disabled:opacity-45 aria-invalid:border-destructive aria-invalid:ring-2 aria-invalid:ring-destructive/20 dark:aria-invalid:border-destructive/50 dark:aria-invalid:ring-destructive/40 [&_svg]:pointer-events-none [&_svg]:shrink-0 [&_svg:not([class*='size-'])]:size-4",
  {
    variants: {
      variant: {
        default:
          "bg-primary text-primary-foreground shadow-[0_4px_16px_-10px_rgba(31,122,62,0.38)] hover:-translate-y-px hover:bg-[color:var(--primary-hover)] hover:shadow-[0_6px_18px_-10px_rgba(23,99,50,0.32)] active:translate-y-0 active:bg-[color:var(--primary-hover)] active:brightness-[0.98] active:shadow-[0_2px_10px_-8px_rgba(23,99,50,0.24)]",
        outline:
          "border border-zinc-200/90 bg-white text-zinc-800 shadow-none hover:-translate-y-px hover:border-zinc-300/80 hover:bg-zinc-50/95 hover:text-zinc-950 hover:shadow-[0_1px_4px_-1px_rgba(15,23,42,0.05)] active:translate-y-0 active:bg-zinc-100/85 active:shadow-none aria-expanded:border-zinc-400/55 aria-expanded:text-zinc-950",
        secondary:
          "bg-secondary/90 text-secondary-foreground hover:-translate-y-px hover:bg-secondary hover:shadow-sm active:translate-y-0 active:bg-secondary/95 active:shadow-none aria-expanded:bg-secondary aria-expanded:text-secondary-foreground",
        ghost:
          "hover:bg-muted/55 hover:text-foreground active:translate-y-px active:bg-muted/70 aria-expanded:bg-muted/55 aria-expanded:text-foreground",
        destructive:
          "bg-destructive/10 text-destructive hover:bg-destructive/20 focus-visible:ring-2 focus-visible:ring-destructive/25 focus-visible:ring-offset-2 active:translate-y-px active:bg-destructive/[0.18] dark:bg-destructive/20 dark:hover:bg-destructive/30 dark:focus-visible:ring-destructive/35",
        link: "text-[13px] font-semibold text-primary underline-offset-4 hover:underline focus-visible:ring-2 focus-visible:ring-primary/28 focus-visible:ring-offset-2",
      },
      size: {
        default:
          "h-9 gap-1.5 px-3 has-data-[icon=inline-end]:pr-2.5 has-data-[icon=inline-start]:pl-2.5",
        xs: "h-6 gap-1 rounded-[min(var(--radius-md),10px)] px-2 text-xs font-semibold in-data-[slot=button-group]:rounded-lg has-data-[icon=inline-end]:pr-1.5 has-data-[icon=inline-start]:pl-1.5 [&_svg:not([class*='size-'])]:size-3",
        sm: "h-7 gap-1 rounded-[min(var(--radius-md),12px)] px-2.5 text-[13px] font-semibold in-data-[slot=button-group]:rounded-lg has-data-[icon=inline-end]:pr-1.5 has-data-[icon=inline-start]:pl-1.5 [&_svg:not([class*='size-'])]:size-3.5",
        lg: "h-9 gap-1.5 px-2.5 has-data-[icon=inline-end]:pr-2 has-data-[icon=inline-start]:pl-2",
        icon: "size-8",
        "icon-xs":
          "size-6 rounded-[min(var(--radius-md),10px)] in-data-[slot=button-group]:rounded-lg [&_svg:not([class*='size-'])]:size-3",
        "icon-sm":
          "size-7 rounded-[min(var(--radius-md),12px)] in-data-[slot=button-group]:rounded-lg",
        "icon-lg": "size-9",
      },
    },
    defaultVariants: {
      variant: "default",
      size: "default",
    },
  }
)

function Button({
  className,
  variant = "default",
  size = "default",
  ...props
}: ButtonPrimitive.Props & VariantProps<typeof buttonVariants>) {
  return (
    <ButtonPrimitive
      data-slot="button"
      className={cn(buttonVariants({ variant, size, className }))}
      {...props}
    />
  )
}

export { Button, buttonVariants }
