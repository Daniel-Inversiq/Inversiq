import type { QuoteStatus } from '../../types';

const statusConfig: Record<QuoteStatus, { label: string; className: string }> = {
  wordt_voorbereid: {
    label: 'Wordt voorbereid',
    className: 'bg-amber-50 text-amber-800 border-amber-200 dark:bg-amber-400/10 dark:text-amber-400 dark:border-amber-400/20',
  },
  open: {
    label: 'Open',
    className: 'bg-blue-50 text-blue-800 border-blue-200 dark:bg-blue-400/10 dark:text-blue-400 dark:border-blue-400/20',
  },
  akkoord: {
    label: 'Akkoord',
    className: 'bg-emerald-50 text-emerald-800 border-emerald-200 dark:bg-emerald-400/10 dark:text-emerald-400 dark:border-emerald-400/20',
  },
  verloren: {
    label: 'Verloren',
    className: 'bg-red-50 text-red-800 border-red-200 dark:bg-red-400/10 dark:text-red-400 dark:border-red-400/20',
  },
};

interface StatusBadgeProps {
  status: QuoteStatus;
}

export function StatusBadge({ status }: StatusBadgeProps) {
  const config = statusConfig[status];
  return (
    <span className={`inline-flex items-center gap-1.5 rounded-sm px-1.5 py-0.5 text-[11px] font-medium border ${config.className}`}>
      <span className="w-1 h-1 rounded-full bg-current opacity-80 shrink-0" />
      {config.label}
    </span>
  );
}

interface BadgeProps {
  children: React.ReactNode;
  variant?: 'default' | 'warning' | 'success' | 'danger' | 'info';
  className?: string;
}

const variantStyles = {
  default: 'bg-slate-100 text-slate-700 border-slate-200 dark:bg-slate-700/40 dark:text-slate-300 dark:border-slate-600',
  warning: 'bg-amber-50 text-amber-800 border-amber-200 dark:bg-amber-400/10 dark:text-amber-400 dark:border-amber-400/20',
  success: 'bg-emerald-50 text-emerald-800 border-emerald-200 dark:bg-emerald-400/10 dark:text-emerald-400 dark:border-emerald-400/20',
  danger: 'bg-red-50 text-red-800 border-red-200 dark:bg-red-400/10 dark:text-red-400 dark:border-red-400/20',
  info: 'bg-blue-50 text-blue-800 border-blue-200 dark:bg-blue-400/10 dark:text-blue-400 dark:border-blue-400/20',
};

export function Badge({ children, variant = 'default', className = '' }: BadgeProps) {
  return (
    <span className={`inline-flex items-center rounded-sm px-1.5 py-0.5 text-[11px] font-medium border ${variantStyles[variant]} ${className}`}>
      {children}
    </span>
  );
}
