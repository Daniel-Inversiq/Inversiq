import { Check, Zap, TrendingUp, Building2, Globe, ExternalLink, AlertTriangle, PhoneCall, FileText, Inbox, ChevronRight } from 'lucide-react';
import { Badge } from '../components/ui/Badge';
import { Button } from '../components/ui/Button';
import { Card, Divider } from '../components/ui/Card';
import { subscriptionInfo } from '../data/mockData';

const USAGE_USED = 1;
const USAGE_MAX = 30;
const USAGE_PERCENT = Math.round((USAGE_USED / USAGE_MAX) * 100);

const plans = [
  {
    id: 'core',
    name: 'Core',
    tagline: 'Voor kleinere teams die snel willen starten',
    volume: '30 aanvragen / maand',
    price: 399,
    priceLabel: '€399',
    badge: 'HUIDIG' as const,
    badgeVariant: 'info' as const,
    features: ['30 aanvragen / maand', '1 workflow', 'Standaard rules', 'Standaard output'],
    action: 'current' as const,
    highlighted: false,
  },
  {
    id: 'growth',
    name: 'Growth',
    tagline: 'Voor groeiende teams met meer volume en automatisering',
    volume: '150 aanvragen / maand',
    price: 899,
    priceLabel: '€899',
    badge: 'Meest gekozen' as const,
    badgeVariant: 'success' as const,
    features: ['150 aanvragen / maand', '1-2 workflows', 'Advanced rules', 'Automation'],
    action: 'growth' as const,
    highlighted: true,
  },
  {
    id: 'pro',
    name: 'Pro',
    tagline: 'Voor bedrijven met meerdere workflows en complexere processen',
    volume: '750 aanvragen / maand',
    price: 2499,
    priceLabel: '€2.499',
    badge: null,
    badgeVariant: null,
    features: ['750 aanvragen / maand', 'Meerdere workflows', 'Complexe logic', 'Integraties'],
    action: 'pro' as const,
    highlighted: false,
  },
  {
    id: 'scale',
    name: 'Scale',
    tagline: 'Voor enterprise teams met maatwerk, API en SLA',
    volume: 'Onbeperkt volume',
    price: null,
    priceLabel: 'Op aanvraag',
    badge: null,
    badgeVariant: null,
    features: ['Onbeperkt volume', 'Custom rules', 'API / Infra', 'SLA + support'],
    action: 'contact' as const,
    highlighted: false,
  },
];

function PlanIcon({ id }: { id: string }) {
  const cls = 'shrink-0';
  if (id === 'core') return <Zap size={15} className={cls} />;
  if (id === 'growth') return <TrendingUp size={15} className={cls} />;
  if (id === 'pro') return <Building2 size={15} className={cls} />;
  return <Globe size={15} className={cls} />;
}

function PlanActionButton({ action }: { action: typeof plans[0]['action'] }) {
  if (action === 'current') {
    return (
      <Button variant="secondary" size="sm" disabled className="shrink-0 min-w-[110px] justify-center text-slate-400 dark:text-slate-500 cursor-default">
        Huidig plan
      </Button>
    );
  }
  if (action === 'growth') {
    return (
      <Button variant="primary" size="sm" className="shrink-0 min-w-[130px] justify-center bg-emerald-600 hover:bg-emerald-700 dark:bg-emerald-600 dark:hover:bg-emerald-500">
        Start met Growth
      </Button>
    );
  }
  if (action === 'pro') {
    return (
      <Button variant="secondary" size="sm" className="shrink-0 min-w-[130px] justify-center">
        Upgrade naar Pro
      </Button>
    );
  }
  return (
    <Button variant="secondary" size="sm" className="shrink-0 min-w-[130px] justify-center">
      Contact opnemen
    </Button>
  );
}

export function Abonnement() {
  const daysLeft = subscriptionInfo.daysRemaining;
  const trialEndDate = '27-04-2026';
  const usedPct = USAGE_PERCENT;
  const remaining = USAGE_MAX - USAGE_USED;

  return (
    <div className="flex gap-6 items-start">
      <div className="flex-1 min-w-0 space-y-5">

        <div>
          <h1 className="text-lg font-bold text-slate-900 dark:text-slate-100 tracking-tight">Billing</h1>
          <p className="text-[13px] text-slate-500 dark:text-slate-400 mt-0.5">
            {subscriptionInfo.plan} · Proefperiode · nog {daysLeft} dagen gratis
          </p>
        </div>

        <Card>
          <div className="flex items-center gap-2 mb-4">
            <div className="flex items-center justify-center w-7 h-7 rounded-lg bg-brand-600/10 dark:bg-brand-400/10 shrink-0">
              <Zap size={13} className="text-brand-600 dark:text-brand-400" />
            </div>
            <h2 className="text-sm font-semibold text-slate-900 dark:text-slate-100">Huidig abonnement</h2>
          </div>

          <div className="grid grid-cols-2 sm:grid-cols-4 gap-5">
            <div>
              <p className="text-[10px] font-semibold text-slate-400 dark:text-slate-500 uppercase tracking-widest mb-1">Plan</p>
              <p className="text-sm font-semibold text-slate-900 dark:text-slate-100">{subscriptionInfo.plan}</p>
            </div>
            <div>
              <p className="text-[10px] font-semibold text-slate-400 dark:text-slate-500 uppercase tracking-widest mb-1">Status</p>
              <Badge variant="warning">{subscriptionInfo.status}</Badge>
            </div>
            <div>
              <p className="text-[10px] font-semibold text-slate-400 dark:text-slate-500 uppercase tracking-widest mb-1">Prijs</p>
              <p className="text-sm font-semibold text-slate-900 dark:text-slate-100">
                €399 <span className="text-xs font-normal text-slate-400 dark:text-slate-500">/ maand</span>
              </p>
            </div>
            <div>
              <p className="text-[10px] font-semibold text-slate-400 dark:text-slate-500 uppercase tracking-widest mb-1">Proefperiode</p>
              <p className="text-sm font-semibold text-slate-900 dark:text-slate-100">{daysLeft} dagen</p>
              <p className="text-[11px] text-slate-400 dark:text-slate-500 mt-0.5">tot {trialEndDate}</p>
            </div>
          </div>
        </Card>

        <Card>
          <div className="flex items-center justify-between mb-4">
            <h2 className="text-sm font-semibold text-slate-900 dark:text-slate-100">Gebruik deze maand</h2>
          </div>

          <div className="flex items-center justify-between text-[12px] mb-2">
            <span className="text-slate-500 dark:text-slate-400">
              <span className="font-semibold text-slate-900 dark:text-slate-100">{USAGE_USED}</span> gebruikt
            </span>
            <span className="text-slate-400 dark:text-slate-500">{USAGE_MAX} max · <span className="text-slate-600 dark:text-slate-300 font-medium">{remaining} resterend</span></span>
          </div>

          <div className="relative h-2 rounded-full bg-slate-100 dark:bg-slate-700/70 overflow-hidden">
            <div
              className="absolute inset-y-0 left-0 rounded-full bg-brand-500 transition-all"
              style={{ width: `${Math.max(usedPct, 2)}%` }}
            />
          </div>

          <p className="mt-2 text-[11px] text-slate-400 dark:text-slate-500">{usedPct}% gebruikt deze maand</p>
        </Card>

        <Card noPadding>
          <div className="flex items-center justify-between px-5 py-4">
            <h2 className="text-sm font-semibold text-slate-900 dark:text-slate-100">Beschikbare plannen</h2>
            <span className="text-[11px] text-slate-400 dark:text-slate-500">Excl. btw</span>
          </div>
          <Divider />

          <div className="divide-y divide-slate-100 dark:divide-slate-700/60">
            {plans.map((plan) => (
              <div
                key={plan.id}
                className={`px-5 py-4 transition-colors ${plan.highlighted ? 'bg-emerald-50/50 dark:bg-emerald-400/[0.04]' : 'hover:bg-slate-50/70 dark:hover:bg-slate-700/20'}`}
              >
                <div className="flex items-start gap-4">
                  <div className={`mt-0.5 flex items-center justify-center w-7 h-7 rounded-lg shrink-0 ${
                    plan.id === 'core' ? 'bg-brand-50 dark:bg-brand-400/10 text-brand-600 dark:text-brand-400' :
                    plan.id === 'growth' ? 'bg-sky-50 dark:bg-sky-400/10 text-sky-600 dark:text-sky-400' :
                    plan.id === 'pro' ? 'bg-emerald-50 dark:bg-emerald-400/10 text-emerald-600 dark:text-emerald-400' :
                    'bg-slate-100 dark:bg-slate-700/60 text-slate-500 dark:text-slate-400'
                  }`}>
                    <PlanIcon id={plan.id} />
                  </div>

                  <div className="flex-1 min-w-0">
                    <div className="flex items-center gap-2 mb-0.5">
                      <span className="text-sm font-semibold text-slate-900 dark:text-slate-100">{plan.name}</span>
                      {plan.badge && (
                        <Badge variant={plan.badgeVariant ?? 'default'} className="text-[10px] px-1.5 py-0.5">
                          {plan.badge}
                        </Badge>
                      )}
                    </div>
                    <p className="text-[12px] text-slate-500 dark:text-slate-400">{plan.tagline}</p>
                    <p className="text-[11px] font-medium text-brand-600 dark:text-brand-400 mt-1">{plan.volume}</p>

                    <div className="flex flex-wrap gap-x-4 gap-y-1 mt-2.5">
                      {plan.features.map((f) => (
                        <span key={f} className="flex items-center gap-1 text-[11px] text-slate-500 dark:text-slate-400">
                          <Check size={11} className="text-emerald-500 dark:text-emerald-400 shrink-0" />
                          {f}
                        </span>
                      ))}
                    </div>
                  </div>

                  <div className="shrink-0 flex flex-col items-end gap-2 ml-4">
                    <div className="text-right">
                      <span className={`text-base font-bold ${plan.price === null ? 'text-slate-700 dark:text-slate-200' : 'text-slate-900 dark:text-slate-100'}`}>
                        {plan.priceLabel}
                      </span>
                      {plan.price !== null && (
                        <p className="text-[10px] text-slate-400 dark:text-slate-500">per maand</p>
                      )}
                    </div>
                    <PlanActionButton action={plan.action} />
                  </div>
                </div>
              </div>
            ))}
          </div>

          <Divider />
          <div className="px-5 py-3">
            <p className="text-[11px] text-slate-400 dark:text-slate-500">
              Prijzen zijn exclusief btw.{' '}
              <span className="text-brand-500 dark:text-brand-400 cursor-pointer hover:underline">Facturen</span>
              {' '}en betaalmethode via{' '}
              <span className="text-brand-500 dark:text-brand-400 cursor-pointer hover:underline">beheer abonnement</span>.
            </p>
          </div>
        </Card>

        <Card>
          <div className="flex items-center justify-between mb-3">
            <h2 className="text-sm font-semibold text-slate-900 dark:text-slate-100">Extra aanvragen</h2>
            <Badge variant="info" className="text-[10px]">ADD-ON</Badge>
          </div>
          <div className="flex items-center justify-between gap-4">
            <p className="text-[13px] text-slate-500 dark:text-slate-400 leading-relaxed">
              Koop 10 extra{' '}
              <span className="text-brand-500 dark:text-brand-400 cursor-pointer hover:underline">aanvragen</span>
              {' '}voor €30. Handig als{' '}
              <span className="text-brand-500 dark:text-brand-400 cursor-pointer hover:underline">tijdelijke</span>
              {' '}uitbreiding zonder direct te upgraden.
            </p>
            <Button
              type="button"
              variant="secondary"
              size="sm"
              className="shrink-0 whitespace-nowrap"
              onClick={() => {
                window.location.assign("/app/billing?action=topup");
              }}
            >
              Koop extra aanvragen
            </Button>
          </div>
        </Card>

      </div>

      <div className="w-64 shrink-0 space-y-4">

        <Card>
          <div className="flex items-center gap-2 mb-4">
            <div className="flex items-center justify-center w-6 h-6 rounded-md bg-brand-600/10 dark:bg-brand-400/10">
              <Zap size={12} className="text-brand-600 dark:text-brand-400" />
            </div>
            <h3 className="text-[13px] font-semibold text-slate-900 dark:text-slate-100">Abonnement</h3>
          </div>

          <div className="space-y-3">
            <div>
              <p className="text-[10px] font-semibold text-slate-400 dark:text-slate-500 uppercase tracking-widest mb-0.5">Plan</p>
              <p className="text-sm font-semibold text-slate-900 dark:text-slate-100">{subscriptionInfo.plan}</p>
            </div>

            <Divider />

            <div>
              <p className="text-[10px] font-semibold text-slate-400 dark:text-slate-500 uppercase tracking-widest mb-1">Status</p>
              <Badge variant="warning">{subscriptionInfo.status}</Badge>
            </div>

            <Divider />

            <div>
              <p className="text-[10px] font-semibold text-slate-400 dark:text-slate-500 uppercase tracking-widest mb-0.5">Proefperiode</p>
              <p className="text-sm font-semibold text-slate-900 dark:text-slate-100">Nog {daysLeft} dagen</p>
              <p className="text-[11px] text-slate-400 dark:text-slate-500 mt-0.5">Eindigt op {trialEndDate}</p>
            </div>

            <div className={`flex items-start gap-2 rounded-lg p-2.5 border ${
              daysLeft <= 7
                ? 'bg-red-50 dark:bg-red-400/10 border-red-100 dark:border-red-400/20'
                : 'bg-amber-50 dark:bg-amber-400/10 border-amber-100 dark:border-amber-400/20'
            }`}>
              <AlertTriangle size={12} className={`mt-0.5 shrink-0 ${daysLeft <= 7 ? 'text-red-500 dark:text-red-400' : 'text-amber-500 dark:text-amber-400'}`} />
              <p className={`text-[11px] leading-relaxed ${daysLeft <= 7 ? 'text-red-700 dark:text-red-300' : 'text-amber-800 dark:text-amber-300'}`}>
                Nog <span className="font-bold">{daysLeft} dagen</span> gratis proberen.
              </p>
            </div>

            <Button variant="primary" size="sm" className="w-full justify-center">
              Beheer abonnement
            </Button>
          </div>
        </Card>

        <Card>
          <h3 className="text-[13px] font-semibold text-slate-900 dark:text-slate-100 mb-3">Gebruik</h3>

          <div className="flex items-end justify-between mb-1">
            <div>
              <span className="text-xl font-bold text-slate-900 dark:text-slate-100">{USAGE_USED}</span>
              <span className="text-[12px] text-slate-400 dark:text-slate-500 ml-1">/ {USAGE_MAX}</span>
            </div>
            <span className="text-[11px] text-slate-400 dark:text-slate-500 mb-0.5">{remaining} resterend</span>
          </div>

          <div className="relative h-1.5 rounded-full bg-slate-100 dark:bg-slate-700/70 overflow-hidden">
            <div
              className="absolute inset-y-0 left-0 rounded-full bg-brand-500 transition-all"
              style={{ width: `${Math.max(usedPct, 4)}%` }}
            />
          </div>
          <p className="mt-1.5 text-[11px] text-slate-400 dark:text-slate-500">{usedPct}% gebruikt deze maand</p>
        </Card>

        <Card>
          <h3 className="text-[13px] font-semibold text-slate-900 dark:text-slate-100 mb-3">Vandaag te doen</h3>
          <ul className="space-y-1">
            {[
              { icon: <PhoneCall size={12} />, label: 'Bel klant (opvolging nodig)' },
              { icon: <FileText size={12} />, label: 'Offerte bekijken' },
              { icon: <Inbox size={12} />, label: 'Nieuwe aanvraag checken' },
            ].map(({ icon, label }) => (
              <li key={label}>
                <button className="w-full flex items-center gap-2.5 rounded-md px-2 py-1.5 text-left hover:bg-slate-50 dark:hover:bg-slate-700/40 transition-colors group">
                  <span className="text-brand-500 dark:text-brand-400 shrink-0">{icon}</span>
                  <span className="flex-1 text-[12px] text-slate-700 dark:text-slate-300 group-hover:text-slate-900 dark:group-hover:text-slate-100 truncate">{label}</span>
                  <ChevronRight size={11} className="text-slate-300 dark:text-slate-600 group-hover:text-slate-400 dark:group-hover:text-slate-400 shrink-0" />
                </button>
              </li>
            ))}
          </ul>
        </Card>

        <Card>
          <h3 className="text-[13px] font-semibold text-slate-900 dark:text-slate-100 mb-2">Hulp</h3>
          <p className="text-[12px] text-slate-500 dark:text-slate-400 leading-relaxed mb-3">
            Vragen over je{' '}
            <span className="text-brand-500 dark:text-brand-400 cursor-pointer hover:underline">factuur</span>
            {' '}of{' '}
            <span className="text-brand-500 dark:text-brand-400 cursor-pointer hover:underline">abonnement</span>
            ? Wijzigingen gaan direct in via abonnementsbeheer.
          </p>
          <Button variant="secondary" size="sm" className="w-full justify-center gap-1.5">
            Open facturatie
            <ExternalLink size={11} />
          </Button>
        </Card>

      </div>
    </div>
  );
}
