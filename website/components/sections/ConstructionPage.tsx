"use client";

import { useEffect, useState, useRef } from "react";
import {
  ArrowRight, FileText, Camera, ClipboardCheck,
  GitMerge, ShieldCheck, BarChart3, ChevronRight,
  CheckCircle2, AlertTriangle, Clock, RefreshCw,
  Building2, HardHat,
} from "lucide-react";

function useReducedMotion() {
  const [r, setR] = useState(false);
  useEffect(() => {
    const mq = window.matchMedia("(prefers-reduced-motion: reduce)");
    setR(mq.matches);
    const h = (e: MediaQueryListEvent) => setR(e.matches);
    mq.addEventListener("change", h);
    return () => mq.removeEventListener("change", h);
  }, []);
  return r;
}

function useReveal(threshold = 0.15) {
  const ref = useRef<HTMLDivElement>(null);
  const [visible, setVisible] = useState(false);
  useEffect(() => {
    const el = ref.current;
    if (!el) return;
    const obs = new IntersectionObserver(
      ([entry]) => { if (entry.isIntersecting) { setVisible(true); obs.disconnect(); } },
      { threshold }
    );
    obs.observe(el);
    return () => obs.disconnect();
  }, [threshold]);
  return { ref, visible };
}

/* ── Use cases ─────────────────────────────────── */
const USE_CASES = [
  {
    icon: Camera,
    color: "#3B82F6",
    title: "Damage Assessment Automation",
    description:
      "Site photos and inspection images are analyzed automatically. Inversiq classifies damage type, severity, and affected area — producing a structured assessment without manual interpretation.",
    tags: ["Computer Vision", "Structured Output", "Auto-routing"],
  },
  {
    icon: ClipboardCheck,
    color: "#06B6D4",
    title: "Inspection Report Processing",
    description:
      "PDF and handwritten inspection reports are extracted, normalized, and entered into your systems automatically. No rekeying, no delays, no misread data.",
    tags: ["Document Intelligence", "Multi-format", "CRM Integration"],
  },
  {
    icon: FileText,
    color: "#8B5CF6",
    title: "Contractor Quote Validation",
    description:
      "Incoming contractor quotes are parsed, cross-referenced against scope and pricing benchmarks, and flagged for anomalies before a human ever reviews them.",
    tags: ["Decision Engine", "Benchmark Logic", "Escalation"],
  },
  {
    icon: Building2,
    color: "#10B981",
    title: "Project Document Extraction",
    description:
      "Contracts, drawings, handover documents, and specifications are processed to extract key terms, dates, responsibilities, and deliverables — structured and searchable.",
    tags: ["Document Intelligence", "Entity Extraction", "Audit Trail"],
  },
  {
    icon: ShieldCheck,
    color: "#F59E0B",
    title: "Compliance Documentation Routing",
    description:
      "Safety certificates, permit documents, and compliance checklists are classified and routed to the right team or system automatically, with a full audit log.",
    tags: ["Classification", "Workflow Orchestration", "Audit Trail"],
  },
];

/* ── Capabilities ──────────────────────────────── */
const CAPABILITIES = [
  { icon: FileText,      color: "#3B82F6", label: "Document Intelligence",   desc: "Extract structured data from any document type — PDFs, scans, forms, contracts." },
  { icon: Camera,        color: "#06B6D4", label: "Computer Vision",         desc: "Analyze site photos and inspection images for damage classification and condition scoring." },
  { icon: GitMerge,      color: "#8B5CF6", label: "Decision Engine",         desc: "Apply business rules to extracted data — approve, flag, escalate, or auto-route based on your logic." },
  { icon: RefreshCw,     color: "#10B981", label: "Workflow Orchestration",  desc: "Connect Inversiq to your CRM, ERP, project management tools, and email systems." },
  { icon: AlertTriangle, color: "#F59E0B", label: "Review & Escalation",     desc: "Exceptions are surfaced to the right person at the right time — nothing falls through." },
  { icon: BarChart3,     color: "#94A3B8", label: "Audit Trail",             desc: "Every decision, extraction, and action is logged — searchable and exportable for compliance." },
];

/* ── Outcomes ──────────────────────────────────── */
const OUTCOMES = [
  { icon: Clock,         label: "Faster document processing",           desc: "Inspection reports, assessments, and quotes move through your workflow in minutes, not days." },
  { icon: CheckCircle2,  label: "Fewer manual reviews",                 desc: "Routine documents are handled automatically. Your team focuses on exceptions and judgment calls." },
  { icon: ShieldCheck,   label: "More consistent decision-making",      desc: "Business rules are applied the same way every time — no variance based on who's reviewing." },
  { icon: BarChart3,     label: "Better visibility across workflows",   desc: "Every document and decision is tracked. You always know what's in progress and what's blocked." },
  { icon: RefreshCw,     label: "Repeatable operational processes",     desc: "Once a workflow is configured, it runs reliably at any volume without additional headcount." },
];

/* ═══════════════════════════════════════════════ */
export default function ConstructionPage() {
  const reducedMotion = useReducedMotion();

  return (
    <div className="bg-white">
      <style>{`
        @keyframes fadeUp  { from { opacity:0; transform:translateY(20px); } to { opacity:1; transform:translateY(0); } }
        @keyframes glowPls { 0%,100% { opacity:.15; } 50% { opacity:.25; } }
        @keyframes dotBlink{ 0%,100% { opacity:1; } 50% { opacity:.3; } }
      `}</style>

      <HeroSection reducedMotion={reducedMotion} />
      <ProblemSection />
      <UseCasesSection reducedMotion={reducedMotion} />
      <HowItWorksSection reducedMotion={reducedMotion} />
      <CapabilitiesSection />
      <OutcomesSection />
      <CtaSection />
    </div>
  );
}

/* ── Hero ───────────────────────────────────────── */
function HeroSection({ reducedMotion }: { reducedMotion: boolean }) {
  const [ready, setReady] = useState(false);
  useEffect(() => { const t = setTimeout(() => setReady(true), 60); return () => clearTimeout(t); }, []);

  const fade = (delay: number): React.CSSProperties =>
    reducedMotion ? {} : {
      opacity:    ready ? 1 : 0,
      transform:  ready ? "translateY(0)" : "translateY(18px)",
      transition: `opacity 600ms ease ${delay}ms, transform 600ms ease ${delay}ms`,
    };

  return (
    <section className="relative overflow-hidden bg-[#080C14] pt-[108px] lg:pt-[124px]">
      <style>{`@keyframes gridFade{0%,100%{opacity:.04}50%{opacity:.08}}`}</style>

      {/* Grid */}
      <div className="absolute inset-0 pointer-events-none"
        style={{
          backgroundImage: "linear-gradient(rgba(59,130,246,0.07) 1px,transparent 1px),linear-gradient(90deg,rgba(59,130,246,0.07) 1px,transparent 1px)",
          backgroundSize: "64px 64px",
          animation: reducedMotion ? "none" : "gridFade 8s ease-in-out infinite",
        }} />

      {/* Glow */}
      <div className="absolute pointer-events-none"
        style={{
          top: "-10%", right: "-5%", width: "80%", height: "110%",
          background: "radial-gradient(ellipse at 65% 40%,rgba(37,99,235,.2) 0%,rgba(96,165,250,.07) 40%,transparent 70%)",
          animation: reducedMotion ? "none" : "glowPls 6s ease-in-out infinite",
        }} />

      <div className="relative max-w-[1280px] mx-auto px-5 sm:px-6 xl:px-8 py-16 sm:py-20 lg:py-28">
        <div className="max-w-[720px]">

          {/* Breadcrumb */}
          <div className="flex items-center gap-2 mb-6 text-[11px] font-medium" style={{ color: "#475569" }}>
            <a href="/" className="hover:text-white transition-colors duration-150">Inversiq</a>
            <ChevronRight size={12} />
            <a href="/#industries" className="hover:text-white transition-colors duration-150">Industries</a>
            <ChevronRight size={12} />
            <span style={{ color: "#94A3B8" }}>Construction</span>
          </div>

          {/* Badge */}
          <div className="inline-flex items-center gap-2 self-start px-3 py-1.5 rounded-full mb-6"
            style={{
              ...fade(0),
              backgroundColor: "rgba(16,185,129,0.10)",
              color: "#059669",
              border: "1px solid rgba(16,185,129,0.20)",
              fontSize: "10px",
              fontWeight: 700,
              letterSpacing: "0.07em",
              textTransform: "uppercase",
            }}>
            <span className="w-1.5 h-1.5 rounded-full bg-emerald-500 flex-shrink-0"
              style={{ animation: reducedMotion ? "none" : "dotBlink 2s ease-in-out infinite" }} />
            Live · First Vertical
          </div>

          {/* Headline */}
          <h1 style={{ ...fade(100), lineHeight: 1.05, fontSize: "clamp(2rem, 5.5vw, 3.75rem)", fontWeight: 700, letterSpacing: "-0.025em", color: "#fff", marginBottom: "1.25rem" }}>
            AI Decision Infrastructure<br className="hidden sm:block" /> for Construction Operations
          </h1>

          {/* Sub */}
          <p style={{ ...fade(200), color: "#94A3B8", fontSize: "clamp(1rem, 2.2vw, 1.125rem)", lineHeight: 1.65, maxWidth: "580px", marginBottom: "2rem" }}>
            Automate inspection reports, damage assessments, contractor quotes and
            project documentation with one AI-native platform — without replacing your existing systems.
          </p>

          {/* CTAs */}
          <div className="flex flex-col sm:flex-row gap-3" style={fade(300)}>
            <a href="/contact"
              className="flex items-center justify-center gap-2 rounded-full font-semibold text-white transition-all duration-150 hover:opacity-90"
              style={{ padding: "14px 28px", fontSize: "0.9375rem", backgroundColor: "#2563EB", boxShadow: "0 0 0 1px rgba(59,130,246,0.3),0 4px 16px rgba(37,99,235,.35)" }}>
              Request Construction Demo
              <ArrowRight size={15} strokeWidth={2.2} />
            </a>
            <a href="#how-it-works"
              className="flex items-center justify-center gap-2 rounded-full font-semibold transition-all duration-150"
              style={{ padding: "14px 28px", fontSize: "0.9375rem", color: "#94A3B8", border: "1px solid rgba(255,255,255,0.12)", backgroundColor: "rgba(255,255,255,0.04)" }}>
              See how it works
            </a>
          </div>

          {/* Platform note */}
          <p style={{ ...fade(400), marginTop: "1.75rem", fontSize: "12px", color: "#334155" }}>
            Part of the Inversiq platform &mdash; Document Intelligence · Computer Vision · Decision Engine · Workflow Orchestration
          </p>
        </div>
      </div>

      {/* Bottom fade */}
      <div className="absolute bottom-0 left-0 right-0 h-16 pointer-events-none"
        style={{ background: "linear-gradient(transparent, white)" }} />
    </section>
  );
}

/* ── Problem ────────────────────────────────────── */
function ProblemSection() {
  const { ref, visible } = useReveal();

  const problems = [
    { icon: FileText,      label: "Inspection PDFs",       desc: "Processed manually, one by one. Hours lost per report." },
    { icon: Camera,        label: "Site photos",           desc: "No system can read them. Teams interpret damage by eye." },
    { icon: ClipboardCheck,label: "Contractor quotes",     desc: "Compared manually against scope. Inconsistent decisions." },
    { icon: Building2,     label: "Project documents",     desc: "Contracts and handovers buried in inboxes and shared drives." },
    { icon: HardHat,       label: "Compliance forms",      desc: "Routed by hand. Easy to miss. Hard to audit." },
  ];

  return (
    <section className="py-16 sm:py-20 lg:py-28 bg-white">
      <div className="max-w-[1280px] mx-auto px-5 sm:px-6 xl:px-8">
        <div ref={ref} className="max-w-[640px] mb-12 lg:mb-16"
          style={{
            opacity: visible ? 1 : 0,
            transform: visible ? "translateY(0)" : "translateY(20px)",
            transition: "opacity 600ms ease, transform 600ms ease",
          }}>
          <p className="text-[10px] font-bold uppercase tracking-widest mb-3" style={{ color: "#2563EB" }}>The Problem</p>
          <h2 className="font-bold tracking-tight text-neutral-900 mb-4"
            style={{ fontSize: "clamp(1.625rem, 3.5vw, 2.5rem)", lineHeight: 1.1 }}>
            Construction runs on documents no software knows how to read.
          </h2>
          <p className="text-neutral-500 leading-relaxed" style={{ fontSize: "clamp(0.9375rem, 1.8vw, 1.0625rem)" }}>
            Every inspection, assessment, quote, and compliance form arrives as a PDF, photo, or scanned file.
            Your team converts them into decisions manually — one by one — every single day.
            That&apos;s the gap Inversiq closes.
          </p>
        </div>

        <div className="grid sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-5 gap-4">
          {problems.map((p, i) => (
            <div key={p.label}
              style={{
                opacity: visible ? 1 : 0,
                transform: visible ? "translateY(0)" : "translateY(16px)",
                transition: `opacity 500ms ease ${120 + i * 80}ms, transform 500ms ease ${120 + i * 80}ms`,
              }}>
              <div className="rounded-2xl p-5 h-full"
                style={{ backgroundColor: "#F8FAFC", border: "1px solid #E2E8F0" }}>
                <div className="w-9 h-9 rounded-xl flex items-center justify-center mb-4"
                  style={{ backgroundColor: "rgba(37,99,235,0.07)", border: "1px solid rgba(37,99,235,0.12)" }}>
                  <p.icon size={16} style={{ color: "#2563EB" }} />
                </div>
                <p className="font-semibold text-neutral-800 mb-1.5 text-sm">{p.label}</p>
                <p className="text-xs text-neutral-500 leading-relaxed">{p.desc}</p>
              </div>
            </div>
          ))}
        </div>
      </div>
    </section>
  );
}

/* ── Use cases ──────────────────────────────────── */
function UseCasesSection({ reducedMotion }: { reducedMotion: boolean }) {
  const { ref, visible } = useReveal();
  const [active, setActive] = useState(0);
  const current = USE_CASES[active];

  return (
    <section className="py-16 sm:py-20 lg:py-28" style={{ backgroundColor: "#F8FAFC", borderTop: "1px solid #E2E8F0" }}>
      <div className="max-w-[1280px] mx-auto px-5 sm:px-6 xl:px-8">

        <div ref={ref} className="max-w-[640px] mb-12"
          style={{ opacity: visible ? 1 : 0, transform: visible ? "none" : "translateY(20px)", transition: "opacity 600ms ease, transform 600ms ease" }}>
          <p className="text-[10px] font-bold uppercase tracking-widest mb-3" style={{ color: "#2563EB" }}>Use Cases</p>
          <h2 className="font-bold tracking-tight text-neutral-900 mb-4"
            style={{ fontSize: "clamp(1.625rem, 3.5vw, 2.5rem)", lineHeight: 1.1 }}>
            What Inversiq automates in construction.
          </h2>
          <p className="text-neutral-500 leading-relaxed" style={{ fontSize: "clamp(0.9375rem, 1.8vw, 1.0625rem)" }}>
            Each use case runs on the same Inversiq platform — deployed and configured for your specific document types and business rules.
          </p>
        </div>

        {/* Desktop: two-column tabs */}
        <div className="hidden lg:grid lg:grid-cols-[280px_1fr] gap-6">
          {/* Tabs */}
          <div className="flex flex-col gap-2">
            {USE_CASES.map((uc, i) => (
              <button key={uc.title} onClick={() => setActive(i)}
                className="flex items-center gap-3 px-4 py-3.5 rounded-xl text-left transition-all duration-150"
                style={{
                  backgroundColor: active === i ? "#fff" : "transparent",
                  border: active === i ? "1px solid #E2E8F0" : "1px solid transparent",
                  boxShadow: active === i ? "0 2px 8px rgba(0,0,0,0.06)" : "none",
                  color: active === i ? "#0F172A" : "#64748B",
                }}>
                <div className="w-8 h-8 rounded-lg flex items-center justify-center flex-shrink-0"
                  style={{ backgroundColor: active === i ? `${uc.color}12` : "transparent" }}>
                  <uc.icon size={15} style={{ color: active === i ? uc.color : "#94A3B8" }} />
                </div>
                <span className="text-sm font-medium leading-tight">{uc.title}</span>
              </button>
            ))}
          </div>

          {/* Detail */}
          <div className="rounded-2xl p-8 bg-white" style={{ border: "1px solid #E2E8F0", boxShadow: "0 2px 12px rgba(0,0,0,0.05)" }}>
            <div className="w-12 h-12 rounded-2xl flex items-center justify-center mb-5"
              style={{ backgroundColor: `${current.color}12`, border: `1px solid ${current.color}25` }}>
              <current.icon size={22} style={{ color: current.color }} />
            </div>
            <h3 className="text-xl font-bold text-neutral-900 mb-3">{current.title}</h3>
            <p className="text-neutral-500 leading-relaxed mb-6" style={{ fontSize: "1rem" }}>{current.description}</p>
            <div className="flex flex-wrap gap-2">
              {current.tags.map((t) => (
                <span key={t} className="px-3 py-1 rounded-full text-xs font-semibold"
                  style={{ backgroundColor: `${current.color}10`, color: current.color, border: `1px solid ${current.color}25` }}>
                  {t}
                </span>
              ))}
            </div>
          </div>
        </div>

        {/* Mobile: stacked cards */}
        <div className="flex flex-col gap-4 lg:hidden">
          {USE_CASES.map((uc) => (
            <div key={uc.title} className="rounded-2xl p-5 bg-white" style={{ border: "1px solid #E2E8F0" }}>
              <div className="flex items-start gap-3 mb-3">
                <div className="w-9 h-9 rounded-xl flex items-center justify-center flex-shrink-0"
                  style={{ backgroundColor: `${uc.color}12`, border: `1px solid ${uc.color}25` }}>
                  <uc.icon size={16} style={{ color: uc.color }} />
                </div>
                <h3 className="font-semibold text-neutral-900 text-sm leading-tight pt-1.5">{uc.title}</h3>
              </div>
              <p className="text-xs text-neutral-500 leading-relaxed mb-3">{uc.description}</p>
              <div className="flex flex-wrap gap-1.5">
                {uc.tags.map((t) => (
                  <span key={t} className="px-2 py-0.5 rounded-full text-[10px] font-semibold"
                    style={{ backgroundColor: `${uc.color}10`, color: uc.color, border: `1px solid ${uc.color}25` }}>
                    {t}
                  </span>
                ))}
              </div>
            </div>
          ))}
        </div>
      </div>
    </section>
  );
}

/* ── How it works ───────────────────────────────── */
function HowItWorksSection({ reducedMotion }: { reducedMotion: boolean }) {
  const { ref, visible } = useReveal();

  const inputs = [
    { label: "PDF Inspection Report", icon: FileText },
    { label: "Site Photo",            icon: Camera },
    { label: "Contractor Quote",      icon: ClipboardCheck },
    { label: "Compliance Form",       icon: ShieldCheck },
    { label: "Email Request",         icon: GitMerge },
  ];

  const capabilities = [
    { label: "Document Intelligence", color: "#3B82F6" },
    { label: "Computer Vision",       color: "#06B6D4" },
    { label: "Decision Engine",       color: "#8B5CF6" },
    { label: "Workflow Orchestration",color: "#10B981" },
  ];

  const outputs = [
    { label: "Structured Decision",  icon: CheckCircle2, color: "#10B981" },
    { label: "Workflow Triggered",   icon: GitMerge,     color: "#3B82F6" },
    { label: "System Updated",       icon: RefreshCw,    color: "#06B6D4" },
    { label: "Report Generated",     icon: BarChart3,    color: "#8B5CF6" },
    { label: "Escalation Flagged",   icon: AlertTriangle,color: "#F59E0B" },
  ];

  return (
    <section id="how-it-works" className="py-16 sm:py-20 lg:py-28 bg-[#080C14] relative overflow-hidden">
      <style>{`
        @keyframes flowPulse {
          0%   { transform: translateX(-100%); opacity: 0; }
          20%  { opacity: 1; }
          80%  { opacity: 1; }
          100% { transform: translateX(200%); opacity: 0; }
        }
        @keyframes flowPulseGreen {
          0%   { transform: translateX(-100%); opacity: 0; }
          20%  { opacity: 1; }
          80%  { opacity: 1; }
          100% { transform: translateX(200%); opacity: 0; }
        }
      `}</style>

      {/* Grid background */}
      <div className="absolute inset-0 pointer-events-none"
        style={{
          backgroundImage: "linear-gradient(rgba(59,130,246,0.05) 1px,transparent 1px),linear-gradient(90deg,rgba(59,130,246,0.05) 1px,transparent 1px)",
          backgroundSize: "64px 64px",
        }} />
      {/* Central glow */}
      <div className="absolute pointer-events-none"
        style={{ top: "50%", left: "50%", transform: "translate(-50%,-50%)", width: "70%", height: "80%",
          background: "radial-gradient(ellipse,rgba(37,99,235,0.13) 0%,transparent 65%)" }} />

      <div className="relative max-w-[1280px] mx-auto px-5 sm:px-6 xl:px-8">

        {/* Header */}
        <div ref={ref} className="text-center mb-12 lg:mb-16"
          style={{ opacity: visible ? 1 : 0, transform: visible ? "none" : "translateY(20px)", transition: "opacity 600ms ease, transform 600ms ease" }}>
          <p className="text-[10px] font-bold uppercase tracking-widest mb-3" style={{ color: "#3B82F6" }}>How It Works</p>
          <h2 className="font-bold tracking-tight text-white mb-4"
            style={{ fontSize: "clamp(1.625rem, 3.5vw, 2.5rem)", lineHeight: 1.1 }}>
            From document to decision. Automatically.
          </h2>
          <p className="mx-auto" style={{ color: "#64748B", maxWidth: "540px", fontSize: "clamp(0.9375rem, 1.8vw, 1.0625rem)", lineHeight: 1.65 }}>
            Inversiq sits between your incoming documents and your operating systems —
            reading, deciding, and acting without manual intervention.
          </p>
        </div>

        {/* ── Desktop: horizontal three-column diagram ── */}
        <div className="hidden lg:flex items-center gap-0"
          style={{ opacity: visible ? 1 : 0, transform: visible ? "none" : "translateY(20px)", transition: "opacity 700ms ease 150ms, transform 700ms ease 150ms" }}>

          {/* Column 1: Inputs */}
          <div className="flex-1 rounded-2xl p-6"
            style={{ background: "rgba(255,255,255,0.03)", border: "1px solid rgba(255,255,255,0.07)" }}>
            <p className="text-[10px] font-bold uppercase tracking-widest mb-4" style={{ color: "#475569" }}>Inputs</p>
            <div className="flex flex-col gap-2">
              {inputs.map(({ label, icon: Icon }) => (
                <div key={label} className="flex items-center gap-2.5 px-3 py-2.5 rounded-xl"
                  style={{ backgroundColor: "rgba(255,255,255,0.04)", border: "1px solid rgba(255,255,255,0.06)" }}>
                  <Icon size={11} style={{ color: "#3B82F6", flexShrink: 0 }} />
                  <span className="text-xs font-medium" style={{ color: "#94A3B8" }}>{label}</span>
                </div>
              ))}
            </div>
          </div>

          {/* Connector: Inputs → Core */}
          <HorizontalConnector color="#3B82F6" reducedMotion={reducedMotion} delay={0} />

          {/* Column 2: Inversiq Core */}
          <div className="flex-shrink-0 w-[230px] rounded-2xl p-6 flex flex-col items-center text-center"
            style={{
              background: "linear-gradient(160deg,rgba(37,99,235,0.18) 0%,rgba(96,165,250,0.06) 100%)",
              border: "1px solid rgba(59,130,246,0.30)",
              boxShadow: "0 0 40px rgba(37,99,235,0.12), inset 0 1px 0 rgba(255,255,255,0.06)",
            }}>
            {/* Icon */}
            <div className="w-12 h-12 rounded-2xl flex items-center justify-center mb-4"
              style={{ backgroundColor: "rgba(37,99,235,0.25)", border: "1px solid rgba(59,130,246,0.35)" }}>
              <GitMerge size={22} style={{ color: "#60A5FA" }} />
            </div>
            {/* Label */}
            <p className="text-[10px] font-bold uppercase tracking-widest mb-0.5" style={{ color: "#60A5FA" }}>Inversiq Core</p>
            <p className="text-sm font-bold text-white mb-5">Decision Infrastructure</p>
            {/* Capabilities */}
            <div className="flex flex-col gap-2 w-full">
              {capabilities.map((cap) => (
                <div key={cap.label} className="flex items-center gap-2 px-2.5 py-2 rounded-lg"
                  style={{ backgroundColor: "rgba(255,255,255,0.05)", border: "1px solid rgba(255,255,255,0.08)" }}>
                  <span className="w-1.5 h-1.5 rounded-full flex-shrink-0" style={{ backgroundColor: cap.color }} />
                  <span className="text-[10px] font-medium text-left" style={{ color: "#94A3B8" }}>{cap.label}</span>
                </div>
              ))}
            </div>
          </div>

          {/* Connector: Core → Outputs */}
          <HorizontalConnector color="#10B981" reducedMotion={reducedMotion} delay={400} />

          {/* Column 3: Outputs */}
          <div className="flex-1 rounded-2xl p-6"
            style={{ background: "rgba(16,185,129,0.05)", border: "1px solid rgba(16,185,129,0.15)" }}>
            <p className="text-[10px] font-bold uppercase tracking-widest mb-4" style={{ color: "#059669" }}>Outputs</p>
            <div className="flex flex-col gap-2">
              {outputs.map(({ label, icon: Icon, color }) => (
                <div key={label} className="flex items-center gap-2.5 px-3 py-2.5 rounded-xl"
                  style={{ backgroundColor: "rgba(16,185,129,0.06)", border: "1px solid rgba(16,185,129,0.12)" }}>
                  <Icon size={11} style={{ color, flexShrink: 0 }} />
                  <span className="text-xs font-medium" style={{ color: "#6EE7B7" }}>{label}</span>
                </div>
              ))}
            </div>
          </div>
        </div>

        {/* ── Mobile: vertical stacked with downward arrows ── */}
        <div className="flex flex-col gap-0 lg:hidden"
          style={{ opacity: visible ? 1 : 0, transform: visible ? "none" : "translateY(20px)", transition: "opacity 700ms ease 150ms, transform 700ms ease 150ms" }}>

          {/* Inputs */}
          <div className="rounded-2xl p-5"
            style={{ background: "rgba(255,255,255,0.03)", border: "1px solid rgba(255,255,255,0.07)" }}>
            <p className="text-[10px] font-bold uppercase tracking-widest mb-3" style={{ color: "#475569" }}>Inputs</p>
            <div className="flex flex-col gap-1.5">
              {inputs.map(({ label, icon: Icon }) => (
                <div key={label} className="flex items-center gap-2 px-3 py-2 rounded-xl"
                  style={{ backgroundColor: "rgba(255,255,255,0.04)", border: "1px solid rgba(255,255,255,0.06)" }}>
                  <Icon size={11} style={{ color: "#3B82F6", flexShrink: 0 }} />
                  <span className="text-xs font-medium" style={{ color: "#94A3B8" }}>{label}</span>
                </div>
              ))}
            </div>
          </div>

          <VerticalConnector color="#3B82F6" reducedMotion={reducedMotion} />

          {/* Core */}
          <div className="rounded-2xl p-5"
            style={{
              background: "linear-gradient(160deg,rgba(37,99,235,0.18) 0%,rgba(96,165,250,0.06) 100%)",
              border: "1px solid rgba(59,130,246,0.30)",
            }}>
            <div className="flex items-center gap-3 mb-4">
              <div className="w-9 h-9 rounded-xl flex items-center justify-center flex-shrink-0"
                style={{ backgroundColor: "rgba(37,99,235,0.25)", border: "1px solid rgba(59,130,246,0.35)" }}>
                <GitMerge size={17} style={{ color: "#60A5FA" }} />
              </div>
              <div>
                <p className="text-[10px] font-bold uppercase tracking-widest" style={{ color: "#60A5FA" }}>Inversiq Core</p>
                <p className="text-sm font-bold text-white">Decision Infrastructure</p>
              </div>
            </div>
            <div className="grid grid-cols-2 gap-1.5">
              {capabilities.map((cap) => (
                <div key={cap.label} className="flex items-center gap-1.5 px-2.5 py-2 rounded-lg"
                  style={{ backgroundColor: "rgba(255,255,255,0.05)", border: "1px solid rgba(255,255,255,0.08)" }}>
                  <span className="w-1.5 h-1.5 rounded-full flex-shrink-0" style={{ backgroundColor: cap.color }} />
                  <span className="text-[10px] font-medium" style={{ color: "#94A3B8" }}>{cap.label}</span>
                </div>
              ))}
            </div>
          </div>

          <VerticalConnector color="#10B981" reducedMotion={reducedMotion} />

          {/* Outputs */}
          <div className="rounded-2xl p-5"
            style={{ background: "rgba(16,185,129,0.05)", border: "1px solid rgba(16,185,129,0.15)" }}>
            <p className="text-[10px] font-bold uppercase tracking-widest mb-3" style={{ color: "#059669" }}>Outputs</p>
            <div className="flex flex-col gap-1.5">
              {outputs.map(({ label, icon: Icon, color }) => (
                <div key={label} className="flex items-center gap-2 px-3 py-2 rounded-xl"
                  style={{ backgroundColor: "rgba(16,185,129,0.06)", border: "1px solid rgba(16,185,129,0.12)" }}>
                  <Icon size={11} style={{ color, flexShrink: 0 }} />
                  <span className="text-xs font-medium" style={{ color: "#6EE7B7" }}>{label}</span>
                </div>
              ))}
            </div>
          </div>
        </div>
      </div>
    </section>
  );
}

/* ── Horizontal connector with animated pulse dot ── */
function HorizontalConnector({ color, reducedMotion, delay }: { color: string; reducedMotion: boolean; delay: number }) {
  return (
    <div className="flex-shrink-0 flex items-center justify-center" style={{ width: "56px", position: "relative" }}>
      {/* Track line */}
      <div className="absolute left-0 right-0 h-px"
        style={{ background: `linear-gradient(90deg, transparent, ${color}60, ${color}60, transparent)` }} />
      {/* Arrowhead */}
      <div className="relative z-10 flex items-center justify-center"
        style={{ width: "22px", height: "22px", borderRadius: "50%", backgroundColor: `${color}18`, border: `1px solid ${color}40` }}>
        <ArrowRight size={11} style={{ color }} />
      </div>
      {/* Animated travel dot */}
      {!reducedMotion && (
        <div className="absolute left-0 right-0 flex items-center overflow-hidden" style={{ height: "8px" }}>
          <div style={{
            width: "6px", height: "6px", borderRadius: "50%",
            backgroundColor: color,
            boxShadow: `0 0 6px ${color}`,
            animation: `flowPulse 2.4s ease-in-out ${delay}ms infinite`,
            position: "absolute",
          }} />
        </div>
      )}
    </div>
  );
}

/* ── Vertical connector for mobile ── */
function VerticalConnector({ color, reducedMotion }: { color: string; reducedMotion: boolean }) {
  return (
    <div className="flex items-center justify-center py-1" style={{ position: "relative", height: "40px" }}>
      {/* Track */}
      <div className="absolute top-0 bottom-0 w-px left-1/2 -translate-x-1/2"
        style={{ background: `linear-gradient(transparent, ${color}60, ${color}60, transparent)` }} />
      {/* Arrowhead */}
      <div className="relative z-10 flex items-center justify-center"
        style={{ width: "22px", height: "22px", borderRadius: "50%", backgroundColor: `${color}18`, border: `1px solid ${color}40` }}>
        <ArrowRight size={11} style={{ color, transform: "rotate(90deg)" }} />
      </div>
    </div>
  );
}

/* ── Capabilities ───────────────────────────────── */
function CapabilitiesSection() {
  const { ref, visible } = useReveal();
  return (
    <section className="py-16 sm:py-20 lg:py-28 bg-white">
      <div className="max-w-[1280px] mx-auto px-5 sm:px-6 xl:px-8">
        <div ref={ref} className="max-w-[640px] mb-12"
          style={{ opacity: visible ? 1 : 0, transform: visible ? "none" : "translateY(20px)", transition: "opacity 600ms ease, transform 600ms ease" }}>
          <p className="text-[10px] font-bold uppercase tracking-widest mb-3" style={{ color: "#2563EB" }}>Platform</p>
          <h2 className="font-bold tracking-tight text-neutral-900 mb-4"
            style={{ fontSize: "clamp(1.625rem, 3.5vw, 2.5rem)", lineHeight: 1.1 }}>
            Capabilities used in construction.
          </h2>
          <p className="text-neutral-500 leading-relaxed" style={{ fontSize: "clamp(0.9375rem, 1.8vw, 1.0625rem)" }}>
            Every construction workflow runs on the same Inversiq platform — configured for your document types, business rules, and integrations.
          </p>
        </div>

        <div className="grid sm:grid-cols-2 lg:grid-cols-3 gap-5">
          {CAPABILITIES.map((cap, i) => (
            <div key={cap.label}
              style={{
                opacity: visible ? 1 : 0,
                transform: visible ? "none" : "translateY(16px)",
                transition: `opacity 500ms ease ${i * 70}ms, transform 500ms ease ${i * 70}ms`,
              }}>
              <div className="rounded-2xl p-5 h-full" style={{ backgroundColor: "#F8FAFC", border: "1px solid #E2E8F0" }}>
                <div className="w-10 h-10 rounded-xl flex items-center justify-center mb-4"
                  style={{ backgroundColor: `${cap.color}10`, border: `1px solid ${cap.color}20` }}>
                  <cap.icon size={18} style={{ color: cap.color }} />
                </div>
                <p className="font-semibold text-neutral-900 mb-2 text-sm">{cap.label}</p>
                <p className="text-xs text-neutral-500 leading-relaxed">{cap.desc}</p>
              </div>
            </div>
          ))}
        </div>
      </div>
    </section>
  );
}

/* ── Outcomes ───────────────────────────────────── */
function OutcomesSection() {
  const { ref, visible } = useReveal();
  return (
    <section className="py-16 sm:py-20 lg:py-28" style={{ backgroundColor: "#F8FAFC", borderTop: "1px solid #E2E8F0" }}>
      <div className="max-w-[1280px] mx-auto px-5 sm:px-6 xl:px-8">
        <div ref={ref} className="max-w-[640px] mb-12"
          style={{ opacity: visible ? 1 : 0, transform: visible ? "none" : "translateY(20px)", transition: "opacity 600ms ease, transform 600ms ease" }}>
          <p className="text-[10px] font-bold uppercase tracking-widest mb-3" style={{ color: "#2563EB" }}>Outcomes</p>
          <h2 className="font-bold tracking-tight text-neutral-900 mb-4"
            style={{ fontSize: "clamp(1.625rem, 3.5vw, 2.5rem)", lineHeight: 1.1 }}>
            What changes when Inversiq runs your workflows.
          </h2>
          <p className="text-neutral-500 leading-relaxed" style={{ fontSize: "clamp(0.9375rem, 1.8vw, 1.0625rem)" }}>
            These outcomes are consistent across construction teams that deploy Inversiq — regardless of scale.
          </p>
        </div>

        <div className="grid sm:grid-cols-2 lg:grid-cols-3 gap-5">
          {OUTCOMES.map((o, i) => (
            <div key={o.label}
              style={{
                opacity: visible ? 1 : 0,
                transform: visible ? "none" : "translateY(16px)",
                transition: `opacity 500ms ease ${i * 80}ms, transform 500ms ease ${i * 80}ms`,
              }}>
              <div className="rounded-2xl p-5 h-full bg-white" style={{ border: "1px solid #E2E8F0", boxShadow: "0 1px 4px rgba(0,0,0,0.04)" }}>
                <div className="w-10 h-10 rounded-xl flex items-center justify-center mb-4"
                  style={{ backgroundColor: "rgba(37,99,235,0.07)", border: "1px solid rgba(37,99,235,0.12)" }}>
                  <o.icon size={18} style={{ color: "#2563EB" }} />
                </div>
                <p className="font-semibold text-neutral-900 mb-2 text-sm">{o.label}</p>
                <p className="text-xs text-neutral-500 leading-relaxed">{o.desc}</p>
              </div>
            </div>
          ))}
        </div>
      </div>
    </section>
  );
}

/* ── CTA ────────────────────────────────────────── */
function CtaSection() {
  const { ref, visible } = useReveal();
  return (
    <section className="py-20 sm:py-24 lg:py-32 bg-[#080C14] relative overflow-hidden">
      <div className="absolute inset-0 pointer-events-none"
        style={{
          backgroundImage: "linear-gradient(rgba(59,130,246,0.05) 1px,transparent 1px),linear-gradient(90deg,rgba(59,130,246,0.05) 1px,transparent 1px)",
          backgroundSize: "64px 64px",
        }} />
      <div className="absolute pointer-events-none"
        style={{ top: "50%", left: "50%", transform: "translate(-50%,-50%)", width: "80%", height: "90%",
          background: "radial-gradient(ellipse,rgba(37,99,235,0.15) 0%,transparent 65%)" }} />

      <div ref={ref} className="relative max-w-[760px] mx-auto px-5 sm:px-6 text-center"
        style={{ opacity: visible ? 1 : 0, transform: visible ? "none" : "translateY(20px)", transition: "opacity 600ms ease, transform 600ms ease" }}>
        <p className="text-[10px] font-bold uppercase tracking-widest mb-4" style={{ color: "#3B82F6" }}>Ready to automate</p>
        <h2 className="font-bold tracking-tight text-white mb-5"
          style={{ fontSize: "clamp(1.75rem, 4vw, 3rem)", lineHeight: 1.1 }}>
          Bring AI-native decision infrastructure to your construction workflows.
        </h2>
        <p className="mb-8 mx-auto" style={{ color: "#64748B", maxWidth: "500px", fontSize: "clamp(0.9375rem, 1.8vw, 1.0625rem)", lineHeight: 1.65 }}>
          We&apos;ll show you Inversiq running on your document types — inspection reports, quotes, photos, and forms — in a custom demo.
        </p>
        <div className="flex flex-col sm:flex-row gap-3 justify-center">
          <a href="/contact"
            className="flex items-center justify-center gap-2 rounded-full font-semibold text-white transition-all duration-150 hover:opacity-90"
            style={{ padding: "15px 32px", fontSize: "0.9375rem", backgroundColor: "#2563EB", boxShadow: "0 0 0 1px rgba(59,130,246,0.3),0 4px 16px rgba(37,99,235,.4)" }}>
            Request a Demo
            <ArrowRight size={15} strokeWidth={2.2} />
          </a>
          <a href="/#platform"
            className="flex items-center justify-center gap-2 rounded-full font-semibold transition-all duration-150"
            style={{ padding: "15px 32px", fontSize: "0.9375rem", color: "#94A3B8", border: "1px solid rgba(255,255,255,0.12)", backgroundColor: "rgba(255,255,255,0.04)" }}>
            Explore the Platform
          </a>
        </div>
      </div>
    </section>
  );
}
