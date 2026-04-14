import { Sun, Moon, Bell } from 'lucide-react';
import { useTheme } from '../../contexts/ThemeContext';

interface HeaderProps {
  title: string;
  breadcrumb?: string;
}

export function Header({ title, breadcrumb }: HeaderProps) {
  const { theme, toggleTheme } = useTheme();

  return (
    <header className="sticky top-0 z-30 flex items-center justify-between h-12 px-6 bg-white dark:bg-[#0d1117] border-b border-neutral-200/90 dark:border-white/[0.07]">
      <div className="flex items-center gap-1.5 text-[12px]">
        {breadcrumb && (
          <>
            <span className="text-neutral-400 dark:text-white/25">{breadcrumb}</span>
            <span className="text-neutral-300 dark:text-white/15">/</span>
          </>
        )}
        <span className="font-semibold text-neutral-900 tracking-tight dark:text-white/70">{title}</span>
      </div>

      <div className="flex items-center gap-0.5">
        <button
          onClick={() => {}}
          className="relative flex items-center justify-center w-7 h-7 rounded text-slate-400 hover:text-slate-600 hover:bg-slate-100 dark:text-white/30 dark:hover:text-white/60 dark:hover:bg-white/[0.05] transition-colors"
        >
          <Bell size={14} />
          <span className="absolute top-1.5 right-1.5 w-1 h-1 rounded-full bg-slate-500 dark:bg-white/40" />
        </button>

        <button
          onClick={toggleTheme}
          className="flex items-center justify-center w-7 h-7 rounded text-slate-400 hover:text-slate-600 hover:bg-slate-100 dark:text-white/30 dark:hover:text-white/60 dark:hover:bg-white/[0.05] transition-colors"
          aria-label="Thema wisselen"
        >
          {theme === 'dark' ? <Sun size={14} /> : <Moon size={14} />}
        </button>


      </div>
    </header>
  );
}
