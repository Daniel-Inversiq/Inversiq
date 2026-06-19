"use client";

import { useEffect, useState } from "react";
import { ArrowRight, Shield, Zap, Globe } from "lucide-react";

function useReducedMotion() {
  const [reduced, setReduced] = useState(false);
  useEffect(() => {
    const mq = window.matchMedia("(prefers-reduced-motion: reduce)");
    setReduced(mq.matches);
    const h = (e: MediaQueryListEvent) => setReduced(e.matches);
    mq.addEventListener("change", h);
    return () => mq.removeEventListener("change", h);
  }, []);
  return reduced;
}

const PIPELINE_STEPS = [
  { input: "Inspection PDF",  stage: "Document Intelligence",  output: "Structured Data",   color: "#3B82F6" },
  { input: "Site Photo",      stage: "Computer Vision",        output: "Damage Assessment", color: "#06B6D4" },
  { input: "Contractor Form", stage: "Decision Engine",        output: "Approval / Route",  color: "#8B5CF6" },
  { input: "Email Request",   stage: "Workflow Orchestration", output: "System Action",     color: "#10B981" },
] as const;

export default function Hero() {
  const reducedMotion = useReducedMotion();
  const [activeStep, setActiveStep] = useState(0);

  useEffect(() => {
    if (reducedMotion) return;
    const interval = setInterval(() => setActiveStep((s) => (s + 1) % PIPELINE_STEPS.length), 2400);
    return () => clearInterval(interval);
  }, [reducedMotion]);

  const anim = (v: string) => (reducedMotion ? "none" : v);

  return (
    <section className="relative w-full overflow-hidden bg-[#080C14]">

      <style>{`
        @keyframes heroFloat { 0%,100% { transform: translateY(0px); } 50% { transform: translateY(-6px); } }
        @keyframes gridPulse { 0%,100% { opacity: 0.03; } 50% { opacity: 0.07; } }
        @keyframes glowPulse { 0%,100% { opacity: 0.18; } 50% { opacity: 0.28; } }
        @keyframes dotBlink  { 0%,100% { opacity:1; } 50% { opacity:0.3; } }
        @keyframes liveRing  { 0% { transform: scale(1); opacity:0.55; } 100% { transform: scale(2.8); opacity:0; } }
      `}</style>

      {/* Background grid */}
      <div className="absolute inset-0 pointer-events-none"
        style={{
          backgroundImage: "linear-gradient(rgba(59,130,246,0.06) 1px, transparent 1px), linear-gradient(90deg, rgba(59,130,246,0.06) 1px, transparent 1px)",
          backgroundSize: "64px 64px",
          animation: anim("gridPulse 8s ease-in-out infinite"),
        }}
      />

      {/* Glow — toned down on mobile */}
      <div className="absolute pointer-events-none"
        style={{
          top: "-10%", right: "-5%", width: "85%", height: "120%",
          background: "radial-gradient(ellipse at 65% 40%, rgba(37,99,235,0.18) 0%, rgba(96,165,250,0.07) 40%, transparent 70%)",
          animation: anim("glowPulse 6s ease-in-out infinite"),
        }}
      />

      {/* Bottom cyan accent */}
      <div className="absolute pointer-events-none"
        style={{
          bottom: "-20%", left: "-10%", width: "55%", height: "80%",
          background: "radial-gradient(ellipse at 30% 70%, rgba(6,182,212,0.07) 0%, transparent 60%)",
        }}
      />

      {/* ── Content ── */}
      {/*
        Mobile:  pt-[108px] (navbar 64px + ann bar 36px + 8px breathing room)
        Desktop: pt-[124px] + min-h-svh centering
      */}
      <div className="relative pt-[108px] lg:pt-[124px] lg:min-h-svh lg:flex lg:items-center">
        <div className="w-full max-w-[1280px] mx-auto px-5 sm:px-6 xl:px-8 py-8 sm:py-10 lg:py-20">

          {/* Two-column on desktop, single column on mobile */}
          <div className="flex flex-col lg:grid lg:grid-cols-2 lg:gap-16 xl:gap-20 lg:items-center gap-0">

            {/* ── Copy block ── */}
            <div className="flex flex-col">

              {/* Eyebrow badge */}
              <div className="inline-flex items-center gap-2 self-start px-3 py-1.5 rounded-full mb-5 sm:mb-6"
                style={{
                  backgroundColor: "rgba(59,130,246,0.10)",
                  color: "#93C5FD",
                  border: "1px solid rgba(59,130,246,0.20)",
                  fontSize: "10px",
                  fontWeight: 700,
                  letterSpacing: "0.07em",
                  textTransform: "uppercase",
                }}>
                <span className="w-1.5 h-1.5 rounded-full bg-blue-400 flex-shrink-0"
                  style={{ animation: anim("dotBlink 2s ease-in-out infinite") }} />
                {/* Shorter label on small screens */}
                <span className="sm:hidden">AI Platform · Operational Industries</span>
                <span className="hidden sm:inline">AI Operating System for Operational Industries</span>
              </div>

              {/* ── Headline ──
                Mobile:  ~30–34px, no forced line-breaks, natural wrapping
                Desktop: ~52–66px, line-breaks restored via hidden spans
              */}
              <h1 className="font-bold tracking-[-0.025em] text-white mb-4 sm:mb-5"
                style={{ lineHeight: 1.06, fontSize: "clamp(1.875rem, 7.5vw, 4.1rem)" }}>
                {/* Mobile: single flowing headline, no breaks */}
                <span className="lg:hidden">
                  The Intelligence Layer Between Work and Decisions.
                </span>
                {/* Desktop: structured line breaks */}
                <span className="hidden lg:inline">
                  The Intelligence Layer
                  <br />
                  <span style={{ color: "#3B82F6" }}>Between Work</span>
                  <br />
                  and Decisions.
                </span>
              </h1>

              {/* Subheadline */}
              <p className="leading-relaxed mb-6 sm:mb-7"
                style={{
                  color: "#94A3B8",
                  fontSize: "clamp(0.9375rem, 2.5vw, 1.0625rem)",
                  lineHeight: 1.65,
                  maxWidth: "480px",
                }}>
                Inversiq reads documents, interprets field data, applies business logic,
                and executes workflows — built for the operational industries that have
                been underserved by software.
              </p>

              {/* ── CTAs ──
                Mobile:  stacked, full-width
                Desktop: inline row
              */}
              <div className="flex flex-col sm:flex-row gap-3 mb-6 sm:mb-7">
                <a href="/contact"
                  className="flex items-center justify-center gap-2 rounded-full font-semibold text-white transition-all duration-150 hover:opacity-90 active:scale-[0.98]"
                  style={{
                    padding: "14px 28px",
                    fontSize: "0.9375rem",
                    backgroundColor: "#2563EB",
                    boxShadow: "0 0 0 1px rgba(59,130,246,0.3), 0 4px 16px rgba(37,99,235,0.35)",
                  }}>
                  Request a Demo
                  <ArrowRight size={15} strokeWidth={2.2} />
                </a>
                <a href="/#platform"
                  className="flex items-center justify-center gap-2 rounded-full font-semibold transition-all duration-150"
                  style={{
                    padding: "14px 28px",
                    fontSize: "0.9375rem",
                    color: "#94A3B8",
                    border: "1px solid rgba(255,255,255,0.12)",
                    backgroundColor: "rgba(255,255,255,0.04)",
                  }}>
                  Explore the Platform
                </a>
              </div>

              {/* Trust strip */}
              <div className="flex flex-wrap items-center gap-x-5 gap-y-2">
                {[
                  { icon: Shield, label: "SOC 2 Type II" },
                  { icon: Globe,  label: "GDPR Compliant" },
                  { icon: Zap,    label: "99.9% Uptime SLA" },
                ].map(({ icon: Icon, label }) => (
                  <div key={label} className="flex items-center gap-1.5">
                    <Icon size={11} style={{ color: "#334155" }} />
                    <span style={{ color: "#475569", fontSize: "12px", fontWeight: 500 }}>{label}</span>
                  </div>
                ))}
              </div>
            </div>

            {/* ── Platform diagram ──
              Mobile:  full width, visible below copy, less animation
              Desktop: right column, floating animation
            */}
            <div className="mt-10 sm:mt-12 lg:mt-0 flex justify-center lg:justify-end"
              style={{ animation: anim("heroFloat 7s ease-in-out infinite") }}>
              <PlatformDiagram activeStep={activeStep} reducedMotion={reducedMotion} />
            </div>

          </div>
        </div>
      </div>
    </section>
  );
}

/* ─────────────────────────────────────────────────────────
   Platform Diagram
   Mobile: compact, essentials only
   Desktop: full with modules grid
───────────────────────────────────────────────────────── */
function PlatformDiagram({
  activeStep,
  reducedMotion,
}: {
  activeStep: number;
  reducedMotion: boolean;
}) {
  const anim = (v: string) => (reducedMotion ? "none" : v);
  const step = PIPELINE_STEPS[activeStep];

  return (
    /*
      w-full on mobile so it fills the column without overflow.
      max-w caps at 400px on large screens.
    */
    <div className="relative w-full max-w-full sm:max-w-[420px] lg:max-w-[400px] select-none">

      {/* Glow halo — desktop only to avoid mobile bleed */}
      <div className="absolute -inset-6 pointer-events-none rounded-3xl hidden sm:block"
        style={{ background: "radial-gradient(ellipse at 50% 50%, rgba(37,99,235,0.13) 0%, transparent 70%)" }} />

      {/* Card */}
      <div className="relative rounded-2xl overflow-hidden w-full"
        style={{
          background: "linear-gradient(135deg, #0F172A 0%, #0D1526 100%)",
          border: "1px solid rgba(255,255,255,0.07)",
          boxShadow: "0 16px 48px -8px rgba(0,0,0,0.55), 0 0 0 1px rgba(59,130,246,0.07)",
        }}>

        {/* Chrome bar */}
        <div className="flex items-center gap-1.5 px-3 sm:px-4 py-2.5 border-b"
          style={{ backgroundColor: "rgba(255,255,255,0.03)", borderColor: "rgba(255,255,255,0.05)" }}>
          <span className="w-1.5 h-1.5 sm:w-2 sm:h-2 rounded-full flex-shrink-0" style={{ backgroundColor: "rgba(255,255,255,0.12)" }} />
          <span className="w-1.5 h-1.5 sm:w-2 sm:h-2 rounded-full flex-shrink-0" style={{ backgroundColor: "rgba(255,255,255,0.12)" }} />
          <span className="w-1.5 h-1.5 sm:w-2 sm:h-2 rounded-full flex-shrink-0" style={{ backgroundColor: "rgba(255,255,255,0.12)" }} />
          <span className="ml-2 sm:ml-3 text-[10px] sm:text-[11px] font-medium truncate" style={{ color: "rgba(255,255,255,0.28)" }}>
            Inversiq · Runtime
          </span>
          <span className="ml-auto flex items-center gap-1.5 flex-shrink-0">
            <span className="relative flex h-1.5 w-1.5 sm:h-2 sm:w-2">
              <span className="absolute inline-flex h-full w-full rounded-full bg-emerald-400"
                style={{ animation: anim("liveRing 2s ease-out infinite") }} />
              <span className="relative inline-flex rounded-full h-full w-full bg-emerald-500" />
            </span>
            <span className="text-[10px] font-semibold text-emerald-500">Live</span>
          </span>
        </div>

        {/* Body */}
        <div className="p-4 sm:p-5 flex flex-col gap-3 sm:gap-4">

          {/* Active pipeline — the key visual, always shown */}
          <div className="rounded-xl p-3 sm:p-4"
            style={{ background: "rgba(255,255,255,0.03)", border: "1px solid rgba(255,255,255,0.06)" }}>
            <p className="text-[9px] sm:text-[10px] font-semibold uppercase tracking-widest mb-2.5"
              style={{ color: "#475569" }}>
              Active Pipeline
            </p>
            <div className="flex items-center gap-1.5 sm:gap-2">
              {/* Input */}
              <div className="flex-1 min-w-0 rounded-lg px-2 sm:px-3 py-2 text-center"
                style={{ background: "rgba(255,255,255,0.04)", border: "1px solid rgba(255,255,255,0.07)" }}>
                <p className="text-[9px] font-medium mb-0.5" style={{ color: "#64748B" }}>Input</p>
                <p className="text-[10px] sm:text-xs font-semibold text-white truncate">{step.input}</p>
              </div>
              {/* Arrow */}
              <svg width="14" height="8" viewBox="0 0 14 8" fill="none" className="flex-shrink-0">
                <path d="M0 4h10M7 1l3 3-3 3" stroke={step.color} strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round"
                  style={{ transition: "stroke 400ms ease" }} />
              </svg>
              {/* Stage */}
              <div className="flex-1 min-w-0 rounded-lg px-2 sm:px-3 py-2 text-center"
                style={{
                  background: `${step.color}15`,
                  border: `1px solid ${step.color}30`,
                  transition: "background 400ms ease, border-color 400ms ease",
                }}>
                <p className="text-[9px] font-medium mb-0.5" style={{ color: step.color, transition: "color 400ms ease" }}>Stage</p>
                <p className="text-[10px] sm:text-xs font-semibold leading-tight" style={{ color: step.color, transition: "color 400ms ease" }}>
                  {/* Shorten long stage names on mobile */}
                  <span className="sm:hidden">{step.stage.split(" ")[0]}</span>
                  <span className="hidden sm:inline">{step.stage}</span>
                </p>
              </div>
              {/* Arrow */}
              <svg width="14" height="8" viewBox="0 0 14 8" fill="none" className="flex-shrink-0">
                <path d="M0 4h10M7 1l3 3-3 3" stroke={step.color} strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" />
              </svg>
              {/* Output */}
              <div className="flex-1 min-w-0 rounded-lg px-2 sm:px-3 py-2 text-center"
                style={{ background: "rgba(16,185,129,0.08)", border: "1px solid rgba(16,185,129,0.18)" }}>
                <p className="text-[9px] font-medium mb-0.5" style={{ color: "#10B981" }}>Output</p>
                <p className="text-[10px] sm:text-xs font-semibold text-emerald-400 leading-tight">
                  <span className="sm:hidden">{step.output.split(" ")[0]}</span>
                  <span className="hidden sm:inline">{step.output}</span>
                </p>
              </div>
            </div>
          </div>

          {/* Modules grid — hidden on smallest screens, shown sm+ */}
          <div className="hidden sm:block">
            <p className="text-[10px] font-semibold uppercase tracking-widest mb-2.5" style={{ color: "#475569" }}>
              Platform Modules
            </p>
            <div className="grid grid-cols-3 gap-1.5 sm:gap-2">
              {[
                { label: "Doc Intelligence", color: "#3B82F6" },
                { label: "Computer Vision",  color: "#06B6D4" },
                { label: "Decision Engine",  color: "#8B5CF6" },
                { label: "Orchestration",    color: "#10B981" },
                { label: "AI Agents",        color: "#F59E0B" },
                { label: "Observability",    color: "#6B7280" },
              ].map((mod) => (
                <div key={mod.label} className="rounded-lg px-2 py-2 text-center"
                  style={{ background: "rgba(255,255,255,0.03)", border: "1px solid rgba(255,255,255,0.06)" }}>
                  <div className="w-1.5 h-1.5 rounded-full mx-auto mb-1.5" style={{ backgroundColor: mod.color }} />
                  <p className="text-[9px] font-medium leading-tight" style={{ color: "#94A3B8" }}>{mod.label}</p>
                </div>
              ))}
            </div>
          </div>

          {/* On mobile: condensed module pills row instead of grid */}
          <div className="flex sm:hidden gap-1.5 flex-wrap">
            {[
              { label: "Doc Intelligence", color: "#3B82F6" },
              { label: "Computer Vision",  color: "#06B6D4" },
              { label: "Decision Engine",  color: "#8B5CF6" },
              { label: "Orchestration",    color: "#10B981" },
              { label: "AI Agents",        color: "#F59E0B" },
              { label: "Observability",    color: "#6B7280" },
            ].map((mod) => (
              <span key={mod.label}
                className="inline-flex items-center gap-1 px-2 py-1 rounded-full text-[9px] font-medium"
                style={{ backgroundColor: `${mod.color}12`, color: mod.color, border: `1px solid ${mod.color}25` }}>
                <span className="w-1 h-1 rounded-full flex-shrink-0" style={{ backgroundColor: mod.color }} />
                {mod.label}
              </span>
            ))}
          </div>

          {/* Stats row */}
          <div className="grid grid-cols-3 gap-2 sm:gap-3 pt-0.5">
            {[
              { value: "< 30s", label: "Time to decision" },
              { value: "94%",   label: "Automation rate" },
              { value: "24/7",  label: "Runtime" },
            ].map((stat) => (
              <div key={stat.label} className="text-center">
                <p className="text-sm sm:text-base font-bold text-white">{stat.value}</p>
                <p className="text-[9px] sm:text-[10px] mt-0.5 leading-tight" style={{ color: "#475569" }}>{stat.label}</p>
              </div>
            ))}
          </div>
        </div>

        {/* Footer */}
        <div className="px-4 sm:px-5 py-2.5 sm:py-3 flex items-center justify-between border-t"
          style={{ borderColor: "rgba(255,255,255,0.05)", backgroundColor: "rgba(255,255,255,0.02)" }}>
          <div className="flex items-center gap-1.5 min-w-0">
            <span className="w-1.5 h-1.5 rounded-full bg-emerald-500 flex-shrink-0" />
            <span className="text-[10px] truncate" style={{ color: "#475569" }}>
              <span className="font-semibold text-white">2,847</span> documents processed today
            </span>
          </div>
          <span className="text-[9px] sm:text-[10px] font-medium flex-shrink-0 ml-2" style={{ color: "#334155" }}>EU · GDPR</span>
        </div>
      </div>
    </div>
  );
}
