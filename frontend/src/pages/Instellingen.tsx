import { useState } from 'react';
import { Upload, Link, CheckCircle2, Lock, Save, User, Tag, Plug, GitBranch } from 'lucide-react';
import { Card, CardHeader, Divider } from '../components/ui/Card';
import { Button } from '../components/ui/Button';
import { Badge } from '../components/ui/Badge';
import { workspaceName } from '../data/mockData';

function SectionHeading({ icon: Icon, title, subtitle }: { icon: React.ComponentType<{ size?: number; className?: string }>; title: string; subtitle?: string }) {
  return (
    <div className="flex items-center gap-2.5 mb-4">
      <div className="flex items-center justify-center w-7 h-7 rounded-lg bg-slate-100 dark:bg-slate-700/60 shrink-0">
        <Icon size={14} className="text-slate-500 dark:text-slate-400" />
      </div>
      <div>
        <h2 className="text-sm font-semibold text-slate-900 dark:text-slate-100">{title}</h2>
        {subtitle && <p className="text-[11px] text-slate-400 dark:text-slate-500 mt-0.5">{subtitle}</p>}
      </div>
    </div>
  );
}

function FieldLabel({ children, required }: { children: React.ReactNode; required?: boolean }) {
  return (
    <label className="block text-[10px] font-semibold text-slate-400 dark:text-slate-500 uppercase tracking-widest mb-1.5">
      {children}
      {required && <span className="text-red-400 ml-0.5">*</span>}
    </label>
  );
}

function Input({ placeholder, defaultValue, type = 'text', prefix }: { placeholder?: string; defaultValue?: string; type?: string; prefix?: string }) {
  return (
    <div className="relative flex items-center">
      {prefix && (
        <span className="absolute left-3 text-[13px] text-slate-400 dark:text-slate-500 select-none">{prefix}</span>
      )}
      <input
        type={type}
        placeholder={placeholder}
        defaultValue={defaultValue}
        className={`w-full h-9 rounded-lg border border-slate-200 dark:border-slate-700/80 bg-white dark:bg-slate-800/80 text-[13px] text-slate-900 dark:text-slate-100 placeholder:text-slate-400 dark:placeholder:text-slate-600 focus:outline-none focus:ring-2 focus:ring-brand-500/40 focus:border-brand-500 dark:focus:border-brand-400 transition-all ${prefix ? 'pl-7 pr-3' : 'px-3'}`}
      />
    </div>
  );
}

export function Instellingen({ onNavigate }: { onNavigate?: (id: string) => void }) {
  const [logoPreview] = useState<string | null>(null);

  return (
    <div className="max-w-2xl space-y-6">

      <div>
        <h1 className="text-lg font-bold text-slate-900 dark:text-slate-100 tracking-tight">Instellingen</h1>
        <p className="text-[13px] text-slate-500 dark:text-slate-400 mt-0.5">Beheer je account, prijzen en integraties</p>
      </div>

      <Card>
        <SectionHeading icon={User} title="Account" />
        <div className="space-y-4">
          <div>
            <FieldLabel>Bedrijfsnaam</FieldLabel>
            <Input defaultValue={workspaceName} />
          </div>

          <div>
            <FieldLabel>Logo</FieldLabel>
            <div className="flex items-center gap-3">
              <div className="flex items-center justify-center w-12 h-12 rounded-xl border border-slate-200 dark:border-slate-700/60 bg-slate-50 dark:bg-slate-800/60 overflow-hidden shrink-0">
                {logoPreview ? (
                  <img src={logoPreview} alt="Logo" className="w-full h-full object-contain" />
                ) : (
                  <div className="flex items-center justify-center w-7 h-7 rounded-lg bg-brand-600">
                    <span className="text-white text-[11px] font-bold">S</span>
                  </div>
                )}
              </div>
              <div className="flex items-center gap-2">
                <Button variant="secondary" size="sm" className="gap-1.5">
                  <Upload size={12} />
                  Upload logo
                </Button>
                <span className="text-[11px] text-slate-400 dark:text-slate-500">PNG of JPEG</span>
              </div>
            </div>
          </div>

          <div>
            <FieldLabel>E-mail</FieldLabel>
            <Input type="email" defaultValue="dvanlieshout00@gmail.com" />
          </div>

          <Divider />

          <div className="flex justify-end gap-2 pt-1">
            <Button variant="secondary" size="sm" className="gap-1.5">
              <Lock size={12} />
              Wachtwoord wijzigen
            </Button>
            <Button variant="primary" size="sm" className="gap-1.5">
              <Save size={12} />
              Opslaan
            </Button>
          </div>
        </div>
      </Card>

      <Card>
        <SectionHeading
          icon={Tag}
          title="Prijzen"
          subtitle="Gebruikt voor het automatisch berekenen van offertes."
        />
        <div className="space-y-4">
          <div>
            <FieldLabel>Prijs per m²</FieldLabel>
            <Input defaultValue="25.0" prefix="€" />
          </div>

          <div>
            <FieldLabel>Minimum prijs</FieldLabel>
            <Input placeholder="Bijv. 250" prefix="€" />
          </div>

          <div>
            <FieldLabel>Voorrijkosten</FieldLabel>
            <Input placeholder="Bijv. 50" prefix="€" />
          </div>

          <Divider />

          <div className="flex justify-end pt-1">
            <Button variant="primary" size="sm" className="gap-1.5">
              <Save size={12} />
              Opslaan
            </Button>
          </div>
        </div>
      </Card>

      <Card>
        <SectionHeading icon={Plug} title="Integraties" />
        <div className="rounded-lg border border-slate-200 dark:border-slate-700/60 divide-y divide-slate-100 dark:divide-slate-700/60">
          <div className="flex items-center justify-between gap-4 px-4 py-3">
            <div className="flex items-center gap-3">
              <div className="flex items-center justify-center w-8 h-8 rounded-lg bg-slate-100 dark:bg-slate-700/60 shrink-0">
                <Link size={14} className="text-slate-500 dark:text-slate-400" />
              </div>
              <div>
                <p className="text-[13px] font-medium text-slate-900 dark:text-slate-100">Google Calendar</p>
                <p className="text-[11px] text-slate-400 dark:text-slate-500">Niet verbonden</p>
              </div>
            </div>
            <Button variant="primary" size="sm">Verbinden</Button>
          </div>
        </div>
      </Card>

      <Card>
        <SectionHeading icon={GitBranch} title="Actieve workflows" />
        <div className="space-y-3">
          <div className="flex items-center gap-2 flex-wrap">
            <div className="flex items-center gap-1.5 h-7 px-2.5 rounded-lg border border-slate-200 dark:border-slate-700/60 bg-slate-50 dark:bg-slate-800/60">
              <CheckCircle2 size={12} className="text-emerald-500 dark:text-emerald-400 shrink-0" />
              <span className="text-[12px] font-medium text-slate-700 dark:text-slate-300">Painting</span>
            </div>
          </div>
          <p className="text-[12px] text-slate-400 dark:text-slate-500 leading-relaxed">
            Neem contact op met Inversiq om workflows toe te voegen of te wijzigen.
          </p>
        </div>

        <Divider className="my-4" />

        <div className="flex items-center justify-between">
          <p className="text-[12px] text-slate-500 dark:text-slate-400">
            Beheer je plan en gebruik via{' '}
            <button
              onClick={() => onNavigate?.('abonnement')}
              className="text-brand-500 dark:text-brand-400 hover:underline font-medium"
            >
              Abonnement
            </button>
            .
          </p>
          <Badge variant="info" className="text-[10px]">1 actief</Badge>
        </div>
      </Card>

    </div>
  );
}
