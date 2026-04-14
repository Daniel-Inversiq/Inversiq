import { useState, useMemo } from 'react';
import { ChevronLeft, ChevronRight, CalendarDays, Clock, User, MapPin, Plus } from 'lucide-react';
import { Card } from '../components/ui/Card';
import { Button } from '../components/ui/Button';

interface AgendaItem {
  id: string;
  title: string;
  client: string;
  location?: string;
  startTime: string;
  endTime: string;
  date: string;
  type: 'klus' | 'opname' | 'overig';
}

const agendaItems: AgendaItem[] = [
  {
    id: 'A-001',
    title: 'Buitenschilderwerk woonhuis',
    client: 'Johan',
    location: 'Hoofdstraat 12, Eindhoven',
    startTime: '08:00',
    endTime: '17:00',
    date: '2026-04-14',
    type: 'klus',
  },
  {
    id: 'A-002',
    title: 'Opname binnenschilderwerk',
    client: 'De Vries Vastgoed',
    location: 'Keizersgracht 45, Amsterdam',
    startTime: '10:00',
    endTime: '11:30',
    date: '2026-04-15',
    type: 'opname',
  },
  {
    id: 'A-003',
    title: 'Gevelschilderwerk dag 1',
    client: 'Pietersen',
    location: 'Dorpsweg 8, Utrecht',
    startTime: '07:30',
    endTime: '16:30',
    date: '2026-04-16',
    type: 'klus',
  },
  {
    id: 'A-004',
    title: 'Overleg renovatieproject',
    client: 'Bakker & Zn.',
    startTime: '14:00',
    endTime: '15:00',
    date: '2026-04-17',
    type: 'overig',
  },
];

const unplannedItems = [
  { id: 'U-001', client: 'Johan', description: 'Binnenschilderwerk kantoor', amount: '€ 890' },
  { id: 'U-002', client: 'Hendriks Woning', description: 'Compleet schilderwerk nieuwbouw', amount: '€ 2.100' },
];

const typeConfig = {
  klus: {
    label: 'Klus',
    bg: 'bg-brand-50 dark:bg-brand-400/10',
    border: 'border-brand-400 dark:border-brand-500',
    title: 'text-brand-800 dark:text-brand-300',
    meta: 'text-brand-600 dark:text-brand-400',
    dot: 'bg-brand-500',
  },
  opname: {
    label: 'Opname',
    bg: 'bg-amber-50 dark:bg-amber-400/10',
    border: 'border-amber-400 dark:border-amber-500',
    title: 'text-amber-800 dark:text-amber-300',
    meta: 'text-amber-600 dark:text-amber-400',
    dot: 'bg-amber-400',
  },
  overig: {
    label: 'Overig',
    bg: 'bg-slate-50 dark:bg-slate-700/30',
    border: 'border-slate-300 dark:border-slate-500',
    title: 'text-slate-700 dark:text-slate-300',
    meta: 'text-slate-500 dark:text-slate-400',
    dot: 'bg-slate-400',
  },
};

const NL_DAYS = ['zo', 'ma', 'di', 'wo', 'do', 'vr', 'za'];
const NL_DAYS_FULL = ['zondag', 'maandag', 'dinsdag', 'woensdag', 'donderdag', 'vrijdag', 'zaterdag'];
const NL_MONTHS = ['januari', 'februari', 'maart', 'april', 'mei', 'juni', 'juli', 'augustus', 'september', 'oktober', 'november', 'december'];

function getMonday(d: Date): Date {
  const date = new Date(d);
  const day = date.getDay();
  const diff = date.getDate() - day + (day === 0 ? -6 : 1);
  date.setDate(diff);
  date.setHours(0, 0, 0, 0);
  return date;
}

function addDays(d: Date, n: number): Date {
  const date = new Date(d);
  date.setDate(date.getDate() + n);
  return date;
}

function toDateString(d: Date): string {
  return d.toISOString().split('T')[0];
}

function formatWeekRange(monday: Date): string {
  const sunday = addDays(monday, 6);
  const mDay = monday.getDate();
  const sDay = sunday.getDate();
  const mMonth = NL_MONTHS[monday.getMonth()];
  const sMonth = NL_MONTHS[sunday.getMonth()];
  if (monday.getMonth() === sunday.getMonth()) {
    return `${mDay} – ${sDay} ${mMonth} ${sunday.getFullYear()}`;
  }
  return `${mDay} ${mMonth} – ${sDay} ${sMonth} ${sunday.getFullYear()}`;
}

interface AgendaCardProps {
  item: AgendaItem;
}

function AgendaCard({ item }: AgendaCardProps) {
  const cfg = typeConfig[item.type];
  return (
    <div className={`relative rounded-lg border-l-[3px] px-2 py-2 min-w-0 overflow-hidden ${cfg.bg} ${cfg.border} group cursor-pointer hover:shadow-sm transition-shadow`}>
      <div className="flex items-start justify-between gap-1 min-w-0">
        <p className={`text-[11px] font-semibold leading-tight truncate min-w-0 ${cfg.title}`}>{item.title}</p>
        <span className={`shrink-0 inline-flex items-center text-[9px] font-semibold uppercase tracking-wide px-1 py-0.5 rounded-full ${cfg.bg} ${cfg.meta} border ${cfg.border}`}>
          {cfg.label}
        </span>
      </div>
      <div className={`mt-1 space-y-0.5 ${cfg.meta} min-w-0`}>
        <div className="flex items-center gap-1 text-[10px]">
          <Clock size={9} className="shrink-0" />
          <span className="truncate">{item.startTime}–{item.endTime}</span>
        </div>
        <div className="flex items-center gap-1 text-[10px]">
          <User size={9} className="shrink-0" />
          <span className="truncate">{item.client}</span>
        </div>
        {item.location && (
          <div className="flex items-center gap-1 text-[10px]">
            <MapPin size={9} className="shrink-0" />
            <span className="truncate">{item.location}</span>
          </div>
        )}
      </div>
    </div>
  );
}

export function Agenda() {
  const today = useMemo(() => {
    const d = new Date();
    d.setHours(0, 0, 0, 0);
    return d;
  }, []);

  const [weekStart, setWeekStart] = useState(() => getMonday(today));

  const weekDays = useMemo(
    () => Array.from({ length: 7 }, (_, i) => addDays(weekStart, i)),
    [weekStart]
  );

  const isCurrentWeek = toDateString(weekStart) === toDateString(getMonday(today));

  const itemsByDate = useMemo(() => {
    const map: Record<string, AgendaItem[]> = {};
    for (const item of agendaItems) {
      if (!map[item.date]) map[item.date] = [];
      map[item.date].push(item);
    }
    return map;
  }, []);

  const totalThisWeek = weekDays.reduce(
    (acc, d) => acc + (itemsByDate[toDateString(d)]?.length ?? 0),
    0
  );

  return (
    <div className="space-y-5">
      <div className="flex items-start justify-between gap-4">
        <div>
          <h1 className="text-lg font-bold text-slate-900 dark:text-slate-100 tracking-tight">Agenda</h1>
          <p className="text-[13px] text-slate-500 dark:text-slate-400 mt-0.5">
            Weekplanning · {totalThisWeek} {totalThisWeek === 1 ? 'item' : 'items'} deze week
          </p>
        </div>
        <Button variant="primary" size="sm">
          <Plus size={13} />
          Nieuw item
        </Button>
      </div>

      <div className="grid grid-cols-1 xl:grid-cols-[1fr_260px] gap-5 items-start">
        <Card noPadding>
          <div className="flex items-center justify-between px-5 py-4 border-b border-slate-100 dark:border-slate-700/60">
            <div className="flex items-center gap-2">
              <CalendarDays size={15} className="text-slate-500 dark:text-slate-400" />
              <span className="text-[13px] font-semibold text-slate-800 dark:text-slate-100">
                {formatWeekRange(weekStart)}
              </span>
            </div>
            <div className="flex items-center gap-1">
              <button
                onClick={() => setWeekStart(w => addDays(w, -7))}
                className="flex items-center justify-center w-7 h-7 rounded-lg text-slate-500 dark:text-slate-400 hover:text-slate-700 dark:hover:text-slate-200 hover:bg-slate-100 dark:hover:bg-slate-700/50 transition-all"
                aria-label="Vorige week"
              >
                <ChevronLeft size={15} />
              </button>
              <button
                onClick={() => setWeekStart(getMonday(today))}
                disabled={isCurrentWeek}
                className="px-2.5 py-1 text-[11px] font-semibold rounded-md transition-all disabled:opacity-40 disabled:cursor-not-allowed text-slate-600 dark:text-slate-300 hover:bg-slate-100 dark:hover:bg-slate-700/50 disabled:hover:bg-transparent"
              >
                Deze week
              </button>
              <button
                onClick={() => setWeekStart(w => addDays(w, 7))}
                className="flex items-center justify-center w-7 h-7 rounded-lg text-slate-500 dark:text-slate-400 hover:text-slate-700 dark:hover:text-slate-200 hover:bg-slate-100 dark:hover:bg-slate-700/50 transition-all"
                aria-label="Volgende week"
              >
                <ChevronRight size={15} />
              </button>
            </div>
          </div>

          <div className="grid divide-x divide-slate-100 dark:divide-slate-700/60 overflow-hidden" style={{ gridTemplateColumns: 'repeat(7, minmax(0, 1fr))' }}>
            {weekDays.map((day, i) => {
              const dateStr = toDateString(day);
              const isToday = dateStr === toDateString(today);
              const isWeekend = i >= 5;
              const items = itemsByDate[dateStr] ?? [];

              return (
                <div key={dateStr} className={`min-h-[280px] flex flex-col min-w-0 overflow-hidden ${isWeekend ? 'bg-slate-50/60 dark:bg-slate-800/20' : ''}`}>
                  <div className="flex flex-col items-center gap-1 py-3 border-b border-slate-100 dark:border-slate-700/60">
                    <span className={`text-[10px] font-semibold uppercase tracking-widest ${isToday ? 'text-brand-500' : 'text-slate-400 dark:text-slate-500'}`}>
                      {NL_DAYS[day.getDay()]}
                    </span>
                    <div className={`flex items-center justify-center w-7 h-7 rounded-full text-sm font-bold transition-colors ${
                      isToday
                        ? 'bg-brand-600 text-white shadow-sm'
                        : 'text-slate-700 dark:text-slate-200'
                    }`}>
                      {day.getDate()}
                    </div>
                    {items.length > 0 && (
                      <div className="flex gap-0.5">
                        {items.slice(0, 3).map((item, idx) => (
                          <span key={idx} className={`w-1 h-1 rounded-full ${typeConfig[item.type].dot}`} />
                        ))}
                      </div>
                    )}
                  </div>

                  <div className="flex-1 p-1.5 space-y-1.5 min-w-0">
                    {items.map(item => (
                      <AgendaCard key={item.id} item={item} />
                    ))}
                    {items.length === 0 && (
                      <div className="flex items-center justify-center h-full pb-6">
                        <span className="text-[10px] text-slate-300 dark:text-slate-600">—</span>
                      </div>
                    )}
                  </div>
                </div>
              );
            })}
          </div>

          <div className="px-5 py-3 border-t border-slate-100 dark:border-slate-700/60 flex items-center gap-4">
            {(Object.entries(typeConfig) as [keyof typeof typeConfig, typeof typeConfig[keyof typeof typeConfig]][]).map(([key, cfg]) => (
              <div key={key} className="flex items-center gap-1.5">
                <span className={`w-2 h-2 rounded-full ${cfg.dot}`} />
                <span className="text-[11px] text-slate-500 dark:text-slate-400">{cfg.label}</span>
              </div>
            ))}
          </div>
        </Card>

        <div className="space-y-4">
          <Card noPadding>
            <div className="px-4 py-3.5 border-b border-slate-100 dark:border-slate-700/60">
              <h3 className="text-[13px] font-semibold text-slate-800 dark:text-slate-100">Niet ingepland</h3>
              <p className="text-[11px] text-slate-500 dark:text-slate-400 mt-0.5">
                {unplannedItems.length} {unplannedItems.length === 1 ? 'klus wacht' : 'klussen wachten'} op planning
              </p>
            </div>

            <div className="divide-y divide-slate-100 dark:divide-slate-700/60">
              {unplannedItems.map(item => {
                const initials = item.client.split(' ').map(w => w[0]).slice(0, 2).join('').toUpperCase();
                return (
                  <div key={item.id} className="flex items-start gap-3 px-4 py-3.5 hover:bg-slate-50/80 dark:hover:bg-slate-700/20 transition-colors group">
                    <div className="flex items-center justify-center w-7 h-7 rounded-full bg-brand-100 dark:bg-brand-400/15 text-brand-700 dark:text-brand-400 text-[10px] font-bold shrink-0 mt-0.5">
                      {initials}
                    </div>
                    <div className="flex-1 min-w-0">
                      <p className="text-[12px] font-semibold text-slate-800 dark:text-slate-100">{item.client}</p>
                      <p className="text-[11px] text-slate-500 dark:text-slate-400 mt-0.5 truncate">{item.description}</p>
                      <p className="text-[11px] font-semibold text-slate-600 dark:text-slate-300 mt-1">{item.amount}</p>
                    </div>
                    <button className="shrink-0 flex items-center justify-center w-6 h-6 rounded-md text-slate-400 dark:text-slate-500 hover:text-brand-600 dark:hover:text-brand-400 hover:bg-brand-50 dark:hover:bg-brand-400/10 opacity-0 group-hover:opacity-100 transition-all">
                      <Plus size={13} />
                    </button>
                  </div>
                );
              })}
            </div>

            {unplannedItems.length === 0 && (
              <div className="px-4 py-10 text-center">
                <p className="text-[12px] font-medium text-slate-400 dark:text-slate-500">Alles ingepland</p>
                <p className="text-[11px] text-slate-400 dark:text-slate-600 mt-0.5">Geen openstaande klussen</p>
              </div>
            )}
          </Card>

          <Card noPadding>
            <div className="px-4 py-3.5 border-b border-slate-100 dark:border-slate-700/60">
              <h3 className="text-[13px] font-semibold text-slate-800 dark:text-slate-100">Week overzicht</h3>
            </div>
            <div className="px-4 py-3.5 space-y-3">
              {(['klus', 'opname', 'overig'] as const).map(type => {
                const cfg = typeConfig[type];
                const count = agendaItems.filter(i => {
                  const d = new Date(i.date);
                  d.setHours(0, 0, 0, 0);
                  return i.type === type && weekDays.some(wd => toDateString(wd) === toDateString(d));
                }).length;
                return (
                  <div key={type} className="flex items-center justify-between">
                    <div className="flex items-center gap-2">
                      <span className={`w-2 h-2 rounded-full ${cfg.dot}`} />
                      <span className="text-[12px] text-slate-600 dark:text-slate-400">{cfg.label}s</span>
                    </div>
                    <span className="text-[12px] font-semibold text-slate-800 dark:text-slate-200">{count}</span>
                  </div>
                );
              })}
              <div className="pt-2 border-t border-slate-100 dark:border-slate-700/60 flex items-center justify-between">
                <span className="text-[12px] font-semibold text-slate-700 dark:text-slate-300">Totaal</span>
                <span className="text-[12px] font-bold text-slate-900 dark:text-slate-100">{totalThisWeek}</span>
              </div>
            </div>
          </Card>
        </div>
      </div>
    </div>
  );
}
