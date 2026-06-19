import { clsx } from "clsx";
import { twMerge } from "tailwind-merge";

type ButtonVariant = "primary" | "accent" | "secondary" | "ghost" | "outline-accent";
type ButtonSize = "sm" | "md" | "lg";

interface ButtonProps extends React.ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: ButtonVariant;
  size?: ButtonSize;
  href?: string;
}

const variants: Record<ButtonVariant, string> = {
  primary:
    "bg-foreground text-background hover:bg-neutral-800 active:bg-neutral-900",
  accent:
    "bg-[#2563EB] text-white hover:bg-[#1D4ED8] active:bg-[#1e40af] shadow-sm",
  secondary:
    "bg-transparent text-foreground border border-foreground hover:bg-foreground hover:text-background",
  "outline-accent":
    "bg-transparent text-[#2563EB] border border-blue-200 hover:bg-blue-50",
  ghost:
    "bg-transparent text-neutral-500 hover:text-foreground",
};

const sizes: Record<ButtonSize, string> = {
  sm: "px-4 py-2 text-sm",
  md: "px-5 py-2.5 text-sm",
  lg: "px-7 py-3.5 text-base",
};

export function Button({
  variant = "primary",
  size = "md",
  className,
  children,
  href,
  ...props
}: ButtonProps) {
  const classes = twMerge(
    clsx(
      "inline-flex items-center justify-center gap-2 font-medium tracking-tight transition-all duration-150 cursor-pointer rounded-full whitespace-nowrap",
      variants[variant],
      sizes[size],
      className
    )
  );

  if (href) {
    return (
      <a href={href} className={classes}>
        {children}
      </a>
    );
  }

  return (
    <button className={classes} {...props}>
      {children}
    </button>
  );
}
