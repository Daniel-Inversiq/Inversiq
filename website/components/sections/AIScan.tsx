"use client";

import { useState } from "react";
import { ArrowRight, ArrowLeft, CheckCircle2, Zap, Clock, TrendingUp, MessageSquare, ChevronRight } from "lucide-react";
import { generateReport, type ScanData, type ScanReport } from "@/lib/scanReport";

/* ══════════════════════════════════════════════════════════
   Constants
══════════════════════════════════════════════════════════ */
const BRANCHES = [
  "Zakelijke dienstverlening",
  "Bouw & vastgoed",
  "Handel & retail",
  "Zorg & welzijn",
  "Financiële diensten",
  "IT & technologie",
  "Productie & industrie",
  "Transport & logistiek",
  "Onderwijs",
  "Anders",
];

const MEDEWERKERS = ["1–10", "11–50", "51–200", "201–500", "500+"];

const SOFTWARE_TOOLS = [
  "Outlook", "Gmail", "Excel", "Word", "Teams",
  "SharePoint", "Exact", "AFAS", "Twinfield",
  "HubSpot", "Salesforce", "Pipedrive", "Slack", "Notion", "Anders",
];

const TIJDVERLIES_OPTIES = [
  "Offerteproces", "E-mailverwerking", "Documentverwerking",
  "CRM-updates", "Facturatie", "Klantadministratie",
  "Rapportages", "Planning", "Anders",
];

const TIJD_PER_WEEK = [
  "Minder dan 5 uur",
  "5–10 uur",
  "10–20 uur",
  "20–40 uur",
  "Meer dan 40 uur",
];

const URGENTIE = ["Laag", "Gemiddeld", "Hoog", "Zeer hoog"];

const TIMING_OPTIES = [
  "Binnen 1 maand",
  "Binnen 3 maanden",
  "Later dit jaar",
  "Ik oriënteer me nog",
];

const TOTAL_STEPS = 4;

const INITIAL_DATA: ScanData = {
  bedrijfsnaam: "", branche: "", medewerkers: "", software: [],
  tijdverlies: [], beschrijving: "",
  tijdPerWeek: "", urgentie: "",
  naam: "", email: "", telefoon: "", timing: "",
};

/* ══════════════════════════════════════════════════════════
   Main component
══════════════════════════════════════════════════════════ */
export default function AIScan() {
  const [step, setStep]       = useState(0);   // 0=intro, 1-4=form, 5=result
  const [data, setData]       = useState<ScanData>(INITIAL_DATA);
  const [errors, setErrors]   = useState<Partial<Record<keyof ScanData, string>>>({});
  const [report, setReport]   = useState<ScanReport | null>(null);

  function update<K extends keyof ScanData>(key: K, value: ScanData[K]) {
    setData((prev) => ({ ...prev, [key]: value }));
    if (errors[key]) setErrors((prev) => ({ ...prev, [key]: undefined }));
  }

  function toggleArray(key: "software" | "tijdverlies", value: string) {
    setData((prev) => {
      const arr = prev[key] as string[];
      return {
        ...prev,
        [key]: arr.includes(value) ? arr.filter((v) => v !== value) : [...arr, value],
      };
    });
  }

  /* ── Validatie per stap ─────────────────────────────── */
  function validate(s: number): boolean {
    const e: typeof errors = {};
    if (s === 1) {
      if (!data.bedrijfsnaam.trim()) e.bedrijfsnaam = "Vul je bedrijfsnaam in.";
      if (!data.branche)             e.branche      = "Kies een branche.";
      if (!data.medewerkers)         e.medewerkers  = "Kies een teamgrootte.";
    }
    if (s === 2) {
      if (data.tijdverlies.length === 0) e.tijdverlies = "Selecteer minimaal één optie.";
    }
    if (s === 3) {
      if (!data.tijdPerWeek) e.tijdPerWeek = "Kies een optie.";
      if (!data.urgentie)    e.urgentie    = "Kies een optie.";
    }
    if (s === 4) {
      if (!data.naam.trim())  e.naam  = "Vul je naam in.";
      if (!data.email.trim()) e.email = "Vul je e-mailadres in.";
      else if (!/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(data.email))
                              e.email = "Voer een geldig e-mailadres in.";
    }
    setErrors(e);
    return Object.keys(e).length === 0;
  }

  function next() {
    if (!validate(step)) return;
    if (step === TOTAL_STEPS) {
      // Generate report — swap this call for an API fetch later
      const r = generateReport(data);
      setReport(r);
      setStep(5);

      // ── Lead tracking: sla de scan op in de database ──────────────
      // Fire-and-forget: de gebruiker merkt hier niets van.
      // Fouten worden gelogd maar storen de wizard-flow niet.
      fetch("/api/scan", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          company_name:               data.bedrijfsnaam,
          industry:                   data.branche,
          employees:                  data.medewerkers,
          tools:                      data.software,
          pain_points:                data.tijdverlies,
          custom_problem_description: data.beschrijving || undefined,
          hours_lost:                 data.tijdPerWeek,
          urgency:                    data.urgentie,
          timeline:                   data.timing || undefined,
          name:                       data.naam,
          email:                      data.email,
          phone:                      data.telefoon || undefined,
          score:                      r.score,
          generated_report:           r,
        }),
      }).catch((err) => {
        // TODO: Stuur naar een error-monitoring service (bijv. Sentry)
        console.error("[scan tracking]", err);
      });
      // ─────────────────────────────────────────────────────────────
    } else {
      setStep((s) => s + 1);
    }
  }

  function back() {
    setStep((s) => Math.max(0, s - 1));
    setErrors({});
  }

  /* ── Render ─────────────────────────────────────────── */
  return (
    <div className="bg-white">
      <div className="max-w-2xl mx-auto px-6 pt-32 pb-8 lg:pb-12">

        {/* Intro */}
        {step === 0 && (
          <IntroScreen onStart={() => setStep(1)} />
        )}

        {/* Steps 1–4 */}
        {step >= 1 && step <= TOTAL_STEPS && (
          <>
            <ProgressBar current={step} total={TOTAL_STEPS} />
            <div className="mt-8">
              {step === 1 && (
                <Step1
                  data={data} errors={errors}
                  onUpdate={update} onToggle={toggleArray}
                />
              )}
              {step === 2 && (
                <Step2
                  data={data} errors={errors}
                  onUpdate={update} onToggle={toggleArray}
                />
              )}
              {step === 3 && (
                <Step3 data={data} errors={errors} onUpdate={update} />
              )}
              {step === 4 && (
                <Step4 data={data} errors={errors} onUpdate={update} />
              )}
            </div>
            <div className="flex items-center justify-between mt-8 pt-6 border-t border-neutral-100">
              <button
                onClick={back}
                className="inline-flex items-center gap-2 text-sm font-medium text-neutral-500 hover:text-neutral-800 transition-colors duration-150"
              >
                <ArrowLeft size={15} />
                Terug
              </button>
              <button
                onClick={next}
                className="inline-flex items-center gap-2 px-6 py-3 rounded-full text-sm font-semibold text-white transition-all duration-150"
                style={{ backgroundColor: "#2563EB" }}
                onMouseEnter={(e) => { (e.currentTarget as HTMLButtonElement).style.backgroundColor = "#1d4ed8"; }}
                onMouseLeave={(e) => { (e.currentTarget as HTMLButtonElement).style.backgroundColor = "#2563EB"; }}
              >
                {step === TOTAL_STEPS ? "Genereer mijn rapport" : "Volgende"}
                <ArrowRight size={15} />
              </button>
            </div>
          </>
        )}

        {/* Result */}
        {step === 5 && report && (
          <ResultScreen report={report} naam={data.naam} bedrijfsnaam={data.bedrijfsnaam} />
        )}

      </div>
    </div>
  );
}

/* ══════════════════════════════════════════════════════════
   IntroScreen
══════════════════════════════════════════════════════════ */
function IntroScreen({ onStart }: { onStart: () => void }) {
  return (
    <div className="flex flex-col items-center text-center">
      {/* Badge */}
      <div
        className="inline-flex items-center gap-2 px-3 py-1.5 rounded-full mb-8 text-[11px] font-semibold tracking-widest uppercase"
        style={{
          backgroundColor: "rgba(37,99,235,0.07)",
          color: "#2563EB",
          border: "1px solid rgba(37,99,235,0.15)",
        }}
      >
        <Zap size={11} strokeWidth={2} />
        Gratis · Geen verplichtingen
      </div>

      <h1
        className="font-bold tracking-tight text-neutral-900 mb-5 text-balance"
        style={{ fontSize: "clamp(2rem, 4vw, 3rem)", lineHeight: 1.1 }}
      >
        Gratis AI-automatisering scan
      </h1>

      <p className="text-lg text-neutral-500 leading-relaxed max-w-md mb-10">
        Ontdek welke processen binnen jouw organisatie geautomatiseerd kunnen
        worden en hoeveel tijd dat oplevert — in 3 minuten.
      </p>

      {/* Trust bullets */}
      <div className="flex flex-col sm:flex-row gap-4 mb-10 text-sm text-neutral-500">
        {[
          "Duurt ~3 minuten",
          "Volledig gratis",
          "Direct resultaat",
        ].map((item) => (
          <div key={item} className="flex items-center gap-2">
            <CheckCircle2 size={14} style={{ color: "#2563EB", flexShrink: 0 }} />
            {item}
          </div>
        ))}
      </div>

      <button
        onClick={onStart}
        className="inline-flex items-center gap-2 px-8 py-4 rounded-full font-semibold text-white text-base transition-all duration-150"
        style={{ backgroundColor: "#2563EB", boxShadow: "0 2px 12px rgba(37,99,235,0.3)" }}
        onMouseEnter={(e) => {
          const el = e.currentTarget as HTMLButtonElement;
          el.style.backgroundColor = "#1d4ed8";
          el.style.transform = "translateY(-1px)";
        }}
        onMouseLeave={(e) => {
          const el = e.currentTarget as HTMLButtonElement;
          el.style.backgroundColor = "#2563EB";
          el.style.transform = "translateY(0)";
        }}
      >
        Start de scan
        <ArrowRight size={16} />
      </button>
    </div>
  );
}

/* ══════════════════════════════════════════════════════════
   ProgressBar
══════════════════════════════════════════════════════════ */
function ProgressBar({ current, total }: { current: number; total: number }) {
  return (
    <div>
      <div className="flex items-center justify-between mb-2">
        <span className="text-xs font-semibold text-neutral-400 uppercase tracking-widest">
          Stap {current} van {total}
        </span>
        <span className="text-xs text-neutral-400">
          {Math.round((current / total) * 100)}%
        </span>
      </div>
      <div className="h-1.5 w-full rounded-full" style={{ backgroundColor: "rgba(0,0,0,0.06)" }}>
        <div
          className="h-full rounded-full"
          style={{
            width: `${(current / total) * 100}%`,
            backgroundColor: "#2563EB",
            transition: "width 400ms cubic-bezier(0.4,0,0.2,1)",
          }}
        />
      </div>
    </div>
  );
}

/* ══════════════════════════════════════════════════════════
   Step 1 — Bedrijfsinformatie
══════════════════════════════════════════════════════════ */
function Step1({
  data, errors, onUpdate, onToggle,
}: {
  data: ScanData;
  errors: Partial<Record<keyof ScanData, string>>;
  onUpdate: <K extends keyof ScanData>(k: K, v: ScanData[K]) => void;
  onToggle: (k: "software" | "tijdverlies", v: string) => void;
}) {
  return (
    <div className="flex flex-col gap-6">
      <StepHeader
        number="01"
        title="Bedrijfsinformatie"
        sub="Vertel ons iets over je organisatie."
      />

      <Field label="Bedrijfsnaam" error={errors.bedrijfsnaam} required>
        <input
          type="text" placeholder="Bedrijf BV"
          value={data.bedrijfsnaam}
          onChange={(e) => onUpdate("bedrijfsnaam", e.target.value)}
          className={inp(!!errors.bedrijfsnaam)}
        />
      </Field>

      <Field label="Branche" error={errors.branche} required>
        <select
          value={data.branche}
          onChange={(e) => onUpdate("branche", e.target.value)}
          className={inp(!!errors.branche)}
        >
          <option value="">Kies een branche…</option>
          {BRANCHES.map((b) => (
            <option key={b} value={b}>{b}</option>
          ))}
        </select>
      </Field>

      <Field label="Aantal medewerkers" error={errors.medewerkers} required>
        <div className="flex flex-wrap gap-2">
          {MEDEWERKERS.map((m) => (
            <RadioPill
              key={m}
              label={m}
              selected={data.medewerkers === m}
              onSelect={() => onUpdate("medewerkers", m)}
            />
          ))}
        </div>
      </Field>

      <Field label="Welke software of tools gebruiken jullie?" hint="Selecteer alles wat van toepassing is">
        <div className="flex flex-wrap gap-2">
          {SOFTWARE_TOOLS.map((t) => (
            <CheckPill
              key={t}
              label={t}
              checked={data.software.includes(t)}
              onToggle={() => onToggle("software", t)}
            />
          ))}
        </div>
      </Field>
    </div>
  );
}

/* ══════════════════════════════════════════════════════════
   Step 2 — Tijdverlies
══════════════════════════════════════════════════════════ */
function Step2({
  data, errors, onUpdate, onToggle,
}: {
  data: ScanData;
  errors: Partial<Record<keyof ScanData, string>>;
  onUpdate: <K extends keyof ScanData>(k: K, v: ScanData[K]) => void;
  onToggle: (k: "software" | "tijdverlies", v: string) => void;
}) {
  return (
    <div className="flex flex-col gap-6">
      <StepHeader
        number="02"
        title="Waar gaat tijd verloren?"
        sub="Selecteer de processen die nu veel handmatig werk kosten."
      />

      <Field label="Processen" error={errors.tijdverlies as string} required>
        <div className="grid grid-cols-2 sm:grid-cols-3 gap-2">
          {TIJDVERLIES_OPTIES.map((t) => (
            <CheckPill
              key={t}
              label={t}
              checked={data.tijdverlies.includes(t)}
              onToggle={() => onToggle("tijdverlies", t)}
            />
          ))}
        </div>
      </Field>

      <Field
        label="Beschrijf kort welk proces nu veel handmatig werk kost"
        hint="Optioneel — maar hoe concreter, hoe beter ons rapport"
        icon={<MessageSquare size={14} className="text-neutral-400" />}
      >
        <textarea
          rows={4}
          placeholder="Bijv. elke week typen we klantgegevens handmatig over van e-mail naar ons CRM…"
          value={data.beschrijving}
          onChange={(e) => onUpdate("beschrijving", e.target.value)}
          className={`${inp(false)} resize-none`}
        />
      </Field>
    </div>
  );
}

/* ══════════════════════════════════════════════════════════
   Step 3 — Impact
══════════════════════════════════════════════════════════ */
function Step3({
  data, errors, onUpdate,
}: {
  data: ScanData;
  errors: Partial<Record<keyof ScanData, string>>;
  onUpdate: <K extends keyof ScanData>(k: K, v: ScanData[K]) => void;
}) {
  return (
    <div className="flex flex-col gap-8">
      <StepHeader
        number="03"
        title="Impact"
        sub="Hoeveel tijd en prioriteit is er mee gemoeid?"
      />

      <Field
        label="Hoeveel tijd kost dit ongeveer per week?"
        error={errors.tijdPerWeek}
        required
        icon={<Clock size={14} className="text-neutral-400" />}
      >
        <div className="flex flex-col gap-2">
          {TIJD_PER_WEEK.map((t) => (
            <RadioRow
              key={t}
              label={t}
              selected={data.tijdPerWeek === t}
              onSelect={() => onUpdate("tijdPerWeek", t)}
            />
          ))}
        </div>
      </Field>

      <Field
        label="Hoe urgent is dit probleem?"
        error={errors.urgentie}
        required
        icon={<TrendingUp size={14} className="text-neutral-400" />}
      >
        <div className="flex flex-wrap gap-2">
          {URGENTIE.map((u) => (
            <RadioPill
              key={u}
              label={u}
              selected={data.urgentie === u}
              onSelect={() => onUpdate("urgentie", u)}
            />
          ))}
        </div>
      </Field>
    </div>
  );
}

/* ══════════════════════════════════════════════════════════
   Step 4 — Contactgegevens
══════════════════════════════════════════════════════════ */
function Step4({
  data, errors, onUpdate,
}: {
  data: ScanData;
  errors: Partial<Record<keyof ScanData, string>>;
  onUpdate: <K extends keyof ScanData>(k: K, v: ScanData[K]) => void;
}) {
  return (
    <div className="flex flex-col gap-6">
      <StepHeader
        number="04"
        title="Waar sturen we het rapport naartoe?"
        sub="Je rapport wordt direct gegenereerd na invulling."
      />

      <Field label="Naam" error={errors.naam} required>
        <input
          type="text" placeholder="Jan de Vries"
          value={data.naam}
          onChange={(e) => onUpdate("naam", e.target.value)}
          className={inp(!!errors.naam)}
          autoComplete="name"
        />
      </Field>

      <Field label="E-mailadres" error={errors.email} required>
        <input
          type="email" placeholder="jan@bedrijf.nl"
          value={data.email}
          onChange={(e) => onUpdate("email", e.target.value)}
          className={inp(!!errors.email)}
          autoComplete="email"
        />
      </Field>

      <Field label="Telefoonnummer" hint="Optioneel">
        <input
          type="tel" placeholder="+31 6 12345678"
          value={data.telefoon}
          onChange={(e) => onUpdate("telefoon", e.target.value)}
          className={inp(false)}
          autoComplete="tel"
        />
      </Field>

      <Field label="Wanneer wil je hier iets mee doen?" hint="Optioneel">
        <div className="flex flex-wrap gap-2">
          {TIMING_OPTIES.map((t) => (
            <RadioPill
              key={t}
              label={t}
              selected={data.timing === t}
              onSelect={() => onUpdate("timing", t)}
            />
          ))}
        </div>
      </Field>

      <p className="text-xs text-neutral-400 leading-relaxed">
        We gebruiken je gegevens alleen om je scanresultaat te tonen en
        eventueel op te volgen. Geen spam, geen verplichtingen.
      </p>
    </div>
  );
}

/* ══════════════════════════════════════════════════════════
   ResultScreen
══════════════════════════════════════════════════════════ */
function ResultScreen({
  report, naam, bedrijfsnaam,
}: {
  report: ScanReport;
  naam: string;
  bedrijfsnaam: string;
}) {
  const scoreColor =
    report.score >= 65 ? "#2563EB"
    : report.score >= 40 ? "#0284c7"
    : "#64748b";

  return (
    <div className="flex flex-col gap-8">

      {/* Header */}
      <div className="text-center">
        <div
          className="inline-flex items-center gap-2 px-3 py-1.5 rounded-full mb-6 text-[11px] font-semibold tracking-widest uppercase"
          style={{
            backgroundColor: "rgba(37,99,235,0.07)",
            color: "#2563EB",
            border: "1px solid rgba(37,99,235,0.15)",
          }}
        >
          <CheckCircle2 size={11} strokeWidth={2} />
          Rapport gegenereerd
        </div>

        <h2
          className="font-bold tracking-tight text-neutral-900 mb-3 text-balance"
          style={{ fontSize: "clamp(1.75rem, 3.5vw, 2.5rem)", lineHeight: 1.1 }}
        >
          {naam ? `${naam.split(" ")[0]}, hier zijn jouw resultaten` : "Hier zijn jouw resultaten"}
        </h2>
        <p className="text-neutral-500">
          {bedrijfsnaam || "Jouw organisatie"} — AI-automatisering scan
        </p>
      </div>

      {/* Score card */}
      <div
        className="rounded-2xl p-7 text-center"
        style={{
          background: `linear-gradient(135deg, rgba(37,99,235,0.05) 0%, rgba(37,99,235,0.02) 100%)`,
          border: "1px solid rgba(37,99,235,0.15)",
        }}
      >
        <p className="text-xs font-semibold uppercase tracking-widest text-neutral-400 mb-3">
          Automatiseringspotentieel
        </p>
        <div
          className="text-7xl font-bold mb-2 tabular-nums"
          style={{ color: scoreColor, letterSpacing: "-0.04em" }}
        >
          {report.score}
          <span className="text-3xl text-neutral-300 font-normal">/100</span>
        </div>
        <span
          className="inline-block px-3 py-1 rounded-full text-sm font-semibold"
          style={{
            backgroundColor: `${scoreColor}15`,
            color: scoreColor,
            border: `1px solid ${scoreColor}30`,
          }}
        >
          {report.scorelabel}
        </span>
        <p className="text-sm text-neutral-500 leading-relaxed mt-4 max-w-md mx-auto">
          {report.samenvatting}
        </p>
      </div>

      {/* Top 3 kansen */}
      <div>
        <h3 className="text-base font-semibold text-neutral-900 mb-4">
          Top 3 automatiseringskansen
        </h3>
        <div className="flex flex-col gap-3">
          {report.kansen.map((kans, i) => (
            <div
              key={kans.titel}
              className="rounded-xl p-5"
              style={{
                backgroundColor: "white",
                border: "1px solid rgba(0,0,0,0.07)",
                boxShadow: "0 1px 3px rgba(0,0,0,0.04)",
              }}
            >
              <div className="flex items-start gap-4">
                <div
                  className="w-7 h-7 rounded-lg flex items-center justify-center flex-shrink-0 mt-0.5"
                  style={{ backgroundColor: "rgba(37,99,235,0.08)" }}
                >
                  <span className="text-xs font-bold" style={{ color: "#2563EB" }}>
                    {i + 1}
                  </span>
                </div>
                <div className="flex-1 min-w-0">
                  <div className="flex items-start justify-between gap-3 flex-wrap">
                    <p className="text-sm font-semibold text-neutral-900">{kans.titel}</p>
                    <span
                      className="text-[10px] font-semibold uppercase tracking-wider px-2 py-0.5 rounded-full flex-shrink-0"
                      style={{
                        backgroundColor: "rgba(37,99,235,0.06)",
                        color: "#2563EB",
                        border: "1px solid rgba(37,99,235,0.12)",
                      }}
                    >
                      Indicatie: {kans.tijdsbesparing}
                    </span>
                  </div>
                  <p className="text-sm text-neutral-500 leading-relaxed mt-1">
                    {kans.beschrijving}
                  </p>
                </div>
              </div>
            </div>
          ))}
        </div>
      </div>

      {/* Metrics row */}
      <div className="grid grid-cols-2 gap-3">
        <div
          className="rounded-xl p-4"
          style={{ backgroundColor: "#f8fafc", border: "1px solid rgba(0,0,0,0.07)" }}
        >
          <p className="text-[10px] font-semibold uppercase tracking-widest text-neutral-400 mb-1.5">
            Geschatte tijdsbesparing
          </p>
          <p className="text-lg font-bold text-neutral-900 leading-tight">
            Indicatie: {report.tijdsbesparing}
          </p>
        </div>
        <div
          className="rounded-xl p-4"
          style={{ backgroundColor: "#f8fafc", border: "1px solid rgba(0,0,0,0.07)" }}
        >
          <p className="text-[10px] font-semibold uppercase tracking-widest text-neutral-400 mb-1.5">
            Potentieel
          </p>
          <p className="text-lg font-bold leading-tight" style={{ color: scoreColor }}>
            {report.scorelabel}
          </p>
        </div>
      </div>

      {/* Eerste stap */}
      <div
        className="rounded-xl p-5"
        style={{
          backgroundColor: "rgba(37,99,235,0.04)",
          border: "1px solid rgba(37,99,235,0.15)",
        }}
      >
        <p className="text-xs font-semibold uppercase tracking-widest mb-2" style={{ color: "#2563EB" }}>
          Aanbevolen eerste stap
        </p>
        <p className="text-sm text-neutral-700 leading-relaxed">{report.eersteStap}</p>
      </div>

      {/* Disclaimer */}
      <p className="text-xs text-neutral-400 leading-relaxed">
        Deze scan is een indicatie op basis van je antwoorden. In een kort gesprek kunnen we bepalen
        welke automatiseringen technisch en financieel het meeste opleveren voor jouw organisatie.
      </p>

      {/* CTA */}
      <div className="flex flex-col sm:flex-row gap-3">
        <a
          href="/contact"
          className="flex-1 inline-flex items-center justify-center gap-2 py-4 rounded-full text-sm font-semibold text-white transition-all duration-150"
          style={{ backgroundColor: "#2563EB" }}
          onMouseEnter={(e) => { (e.currentTarget as HTMLAnchorElement).style.backgroundColor = "#1d4ed8"; }}
          onMouseLeave={(e) => { (e.currentTarget as HTMLAnchorElement).style.backgroundColor = "#2563EB"; }}
        >
          Bespreek mijn scan
          <ChevronRight size={15} />
        </a>
        <a
          href="/"
          className="inline-flex items-center justify-center gap-2 px-6 py-4 rounded-full text-sm font-medium text-neutral-500 hover:text-neutral-800 transition-colors duration-150"
          style={{ border: "1px solid rgba(0,0,0,0.09)" }}
        >
          Terug naar home
        </a>
      </div>
    </div>
  );
}

/* ══════════════════════════════════════════════════════════
   Shared UI components
══════════════════════════════════════════════════════════ */

function StepHeader({ number, title, sub }: { number: string; title: string; sub: string }) {
  return (
    <div className="mb-2">
      <span className="text-xs font-semibold uppercase tracking-widest" style={{ color: "#2563EB" }}>
        Stap {number}
      </span>
      <h2 className="text-2xl font-bold tracking-tight text-neutral-900 mt-1 mb-1.5">
        {title}
      </h2>
      <p className="text-neutral-500 text-sm">{sub}</p>
    </div>
  );
}

function Field({
  label, hint, error, required, icon, children,
}: {
  label: string;
  hint?: string;
  error?: string;
  required?: boolean;
  icon?: React.ReactNode;
  children: React.ReactNode;
}) {
  return (
    <div className="flex flex-col gap-1.5">
      <div className="flex items-center justify-between gap-2 flex-wrap">
        <label className="text-sm font-medium text-neutral-700 flex items-center gap-1.5">
          {icon}{label}{required && <span className="text-red-400">*</span>}
        </label>
        {hint && <span className="text-xs text-neutral-400">{hint}</span>}
      </div>
      {children}
      {error && <p className="text-xs font-medium text-red-500">{error}</p>}
    </div>
  );
}

function CheckPill({
  label, checked, onToggle,
}: {
  label: string; checked: boolean; onToggle: () => void;
}) {
  return (
    <button
      type="button"
      onClick={onToggle}
      className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-full text-xs font-medium transition-all duration-150"
      style={
        checked
          ? {
              backgroundColor: "rgba(37,99,235,0.1)",
              color: "#2563EB",
              border: "1px solid rgba(37,99,235,0.3)",
            }
          : {
              backgroundColor: "#f5f5f5",
              color: "#525252",
              border: "1px solid rgba(0,0,0,0.07)",
            }
      }
    >
      {checked && (
        <svg width="10" height="10" viewBox="0 0 10 10" fill="none">
          <path d="M2 5l2.5 2.5L8 2.5" stroke="#2563EB" strokeWidth="1.6" strokeLinecap="round" strokeLinejoin="round" />
        </svg>
      )}
      {label}
    </button>
  );
}

function RadioPill({
  label, selected, onSelect,
}: {
  label: string; selected: boolean; onSelect: () => void;
}) {
  return (
    <button
      type="button"
      onClick={onSelect}
      className="inline-flex items-center px-4 py-1.5 rounded-full text-xs font-semibold transition-all duration-150"
      style={
        selected
          ? { backgroundColor: "#2563EB", color: "white", border: "1px solid #2563EB" }
          : { backgroundColor: "#f5f5f5", color: "#525252", border: "1px solid rgba(0,0,0,0.07)" }
      }
    >
      {label}
    </button>
  );
}

function RadioRow({
  label, selected, onSelect,
}: {
  label: string; selected: boolean; onSelect: () => void;
}) {
  return (
    <button
      type="button"
      onClick={onSelect}
      className="flex items-center gap-3 px-4 py-3 rounded-xl text-sm text-left w-full transition-all duration-150"
      style={
        selected
          ? {
              backgroundColor: "rgba(37,99,235,0.06)",
              border: "1px solid rgba(37,99,235,0.25)",
              color: "#1d4ed8",
              fontWeight: 500,
            }
          : {
              backgroundColor: "#fafafa",
              border: "1px solid rgba(0,0,0,0.07)",
              color: "#404040",
            }
      }
    >
      <div
        className="w-4 h-4 rounded-full flex-shrink-0 flex items-center justify-center"
        style={
          selected
            ? { backgroundColor: "#2563EB", border: "1px solid #2563EB" }
            : { border: "1.5px solid #d4d4d4", backgroundColor: "white" }
        }
      >
        {selected && <div className="w-1.5 h-1.5 rounded-full bg-white" />}
      </div>
      {label}
    </button>
  );
}

function inp(hasError: boolean): string {
  return [
    "w-full px-4 py-2.5 rounded-xl text-sm text-neutral-800 bg-neutral-50 outline-none",
    "transition-all duration-200 placeholder:text-neutral-300 focus:bg-white",
    hasError
      ? "border border-red-300 focus:border-red-400 focus:ring-2 focus:ring-red-100"
      : "border border-neutral-200 focus:border-blue-500 focus:ring-2 focus:ring-blue-100",
  ].join(" ");
}
