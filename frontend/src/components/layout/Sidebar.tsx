import {
  LayoutDashboard,
  FileText,
  Users,
  Star,
  Calendar,
  Settings,
  CreditCard,
  Zap,
  HelpCircle,
} from 'lucide-react';
import { workspaceName } from '../../data/mockData';

interface NavItem {
  id: string;
  label: string;
  icon: React.ComponentType<{ size?: number; className?: string }>;
  badge?: number;
}

const navItems: NavItem[] = [
  { id: 'overzicht', label: 'Overzicht', icon: LayoutDashboard },
  { id: 'offertes', label: 'Offertes', icon: FileText, badge: 4 },
  { id: 'klussen', label: 'Klussen', icon: Users },
  { id: 'review', label: 'Review', icon: Star },
  { id: 'agenda', label: 'Agenda', icon: Calendar },
];

const bottomNavItems: NavItem[] = [
  { id: 'abonnement', label: 'Abonnement', icon: CreditCard },
  { id: 'hulp', label: 'Hulp & Support', icon: HelpCircle },
  { id: 'instellingen', label: 'Instellingen', icon: Settings },
];

interface SidebarProps {
  activeItem?: string;
  onNavigate?: (id: string) => void;
}

export function Sidebar({ activeItem = 'overzicht', onNavigate }: SidebarProps) {
  return (
    <aside className="fixed inset-y-0 left-0 z-40 w-52 flex flex-col bg-white dark:bg-[#161b22] border-r border-slate-200 dark:border-white/8">
      <div className="flex items-center gap-2.5 px-3 h-11 border-b border-slate-200 dark:border-white/8">
        <div className="flex items-center justify-center w-5 h-5 rounded bg-slate-900 dark:bg-white/10 shrink-0">
          <Zap size={11} className="text-white" />
        </div>
        <div className="min-w-0 flex-1">
          <p className="text-[12px] font-semibold text-slate-800 dark:text-slate-100 tracking-tight">Inversiq</p>
          <p className="text-[9px] text-slate-400 dark:text-slate-500 truncate">{workspaceName}</p>
        </div>
      </div>

      <div className="flex-1 overflow-y-auto px-2 py-3">
        <p className="px-2 mb-1.5 text-[9px] font-semibold tracking-widest uppercase text-slate-400 dark:text-slate-600">
          Menu
        </p>
        <nav className="space-y-px">
          {navItems.map((item) => {
            const Icon = item.icon;
            const isActive = activeItem === item.id;
            return (
              <button
                key={item.id}
                onClick={() => onNavigate?.(item.id)}
                className={`w-full flex items-center gap-2.5 px-2 py-1.5 text-[12px] font-medium transition-colors duration-100 group rounded ${
                  isActive
                    ? 'bg-slate-100 text-slate-900 dark:bg-white/10 dark:text-slate-100'
                    : 'text-slate-500 hover:text-slate-800 hover:bg-slate-50 dark:text-slate-400 dark:hover:text-slate-200 dark:hover:bg-white/6'
                }`}
              >
                <Icon
                  size={14}
                  className={isActive ? 'text-slate-700 dark:text-slate-300' : 'text-slate-400 group-hover:text-slate-600 dark:text-slate-500 dark:group-hover:text-slate-300'}
                />
                <span className="flex-1 text-left">{item.label}</span>
                {item.badge ? (
                  <span className="flex items-center justify-center min-w-[16px] h-4 rounded-sm bg-slate-200 dark:bg-white/10 text-[9px] font-semibold text-slate-600 dark:text-slate-400 px-1">
                    {item.badge}
                  </span>
                ) : null}
              </button>
            );
          })}
        </nav>
      </div>

      <div className="border-t border-slate-200 dark:border-white/8 px-2 py-2 space-y-px">
        {bottomNavItems.map((item) => {
          const Icon = item.icon;
          const isActive = activeItem === item.id;
          return (
            <button
              key={item.id}
              onClick={() => onNavigate?.(item.id)}
              className={`w-full flex items-center gap-2.5 px-2 py-1.5 text-[12px] font-medium transition-colors duration-100 group rounded ${
                isActive
                  ? 'bg-slate-100 text-slate-900 dark:bg-white/10 dark:text-slate-100'
                  : 'text-slate-500 hover:text-slate-800 hover:bg-slate-50 dark:text-slate-400 dark:hover:text-slate-200 dark:hover:bg-white/6'
              }`}
            >
              <Icon
                size={14}
                className={isActive ? 'text-slate-700 dark:text-slate-300' : 'text-slate-400 group-hover:text-slate-600 dark:text-slate-500 dark:group-hover:text-slate-300'}
              />
              <span className="flex-1 text-left">{item.label}</span>
            </button>
          );
        })}
      </div>
    </aside>
  );
}
