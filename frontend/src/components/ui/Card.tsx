interface CardProps {
  children: React.ReactNode;
  className?: string;
  noPadding?: boolean;
}

export function Card({ children, className = '', noPadding = false }: CardProps) {
  return (
    <div
      className={`bg-white dark:bg-white/[0.03] border border-neutral-200/90 dark:border-white/[0.07] shadow-none rounded-xl ${noPadding ? '' : 'p-5'} ${className}`}
    >
      {children}
    </div>
  );
}

interface CardHeaderProps {
  title: string;
  subtitle?: string;
  action?: React.ReactNode;
  className?: string;
}

export function CardHeader({ title, subtitle, action, className = '' }: CardHeaderProps) {
  return (
    <div className={`flex items-start justify-between gap-4 ${className}`}>
      <div>
        <h3 className="text-[12px] font-semibold text-slate-800 dark:text-white/80">{title}</h3>
        {subtitle && (
          <p className="mt-0.5 text-[11px] text-slate-500 dark:text-white/30">{subtitle}</p>
        )}
      </div>
      {action && <div className="shrink-0">{action}</div>}
    </div>
  );
}

interface DividerProps {
  className?: string;
}

export function Divider({ className = '' }: DividerProps) {
  return <div className={`border-t border-slate-100 dark:border-white/[0.06] ${className}`} />;
}
