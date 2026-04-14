import { forwardRef } from 'react';

interface ButtonProps extends React.ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: 'primary' | 'secondary' | 'ghost' | 'danger';
  size?: 'sm' | 'md';
  children: React.ReactNode;
}

const variants = {
  primary: 'bg-slate-900 text-white hover:bg-slate-700 border border-slate-900 dark:bg-slate-100 dark:text-slate-900 dark:border-slate-100 dark:hover:bg-white',
  secondary: 'bg-white text-slate-700 border border-slate-300 hover:bg-slate-50 hover:border-slate-400 dark:bg-slate-800 dark:text-slate-200 dark:border-slate-600 dark:hover:bg-slate-700 dark:hover:border-slate-500',
  ghost: 'text-slate-600 hover:bg-slate-100 hover:text-slate-800 border border-transparent dark:text-slate-400 dark:hover:bg-slate-700/50 dark:hover:text-slate-200',
  danger: 'bg-white text-red-600 border border-red-300 hover:bg-red-50 dark:bg-transparent dark:text-red-400 dark:border-red-400/30 dark:hover:bg-red-400/10',
};

const sizes = {
  sm: 'px-2.5 py-1.5 text-xs gap-1.5',
  md: 'px-3 py-1.5 text-[13px] gap-2',
};

export const Button = forwardRef<HTMLButtonElement, ButtonProps>(
  ({ variant = 'secondary', size = 'md', className = '', children, ...props }, ref) => {
    return (
      <button
        ref={ref}
        className={`inline-flex items-center font-medium rounded transition-colors duration-100 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brand-500 focus-visible:ring-offset-1 disabled:opacity-40 disabled:cursor-not-allowed ${variants[variant]} ${sizes[size]} ${className}`}
        {...props}
      >
        {children}
      </button>
    );
  }
);

Button.displayName = 'Button';
