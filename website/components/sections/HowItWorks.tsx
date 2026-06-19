"use client";

import { useEffect, useRef, useState, useCallback } from "react";
import { Search, Layers, Zap, Link2, TrendingUp, type LucideIcon } from "lucide-react";

const steps: { number: string; title: string; description: string; detail: string; Icon: LucideIcon }[] = [
  {
    number: "01",
    title: "Assess",
    description:
      "We map your current workflows and identify where Inversiq delivers the highest return. Concrete analysis of document types, volumes, systems, and decision logic — not a generic discovery workshop.",
    detail: "Impact-first scoping",
    Icon: Search,
  },
  {
    number: "02",
    title: "Configure",
    description:
      "We build the Inversiq configuration for your environment: extraction schemas, business rules, exception thresholds, and integration targets. Every decision logic is documented and version-controlled.",
    detail: "Purpose-built, not generic",
    Icon: Layers,
  },
  {
    number: "03",
    title: "Integrate",
    description:
      "Inversiq connects to your existing systems — CRM, ERP, inbox, field tools. Your team changes nothing. We test against real data before anything goes live.",
    detail: "No migration. No downtime.",
    Icon: Zap,
  },
  {
    number: "04",
    title: "Deploy",
    description:
      "Inversiq goes live. Processes that took hours run in seconds. Your team sees results immediately — and the observability dashboard shows exactly what the platform is doing.",
    detail: "Results, not promises",
    Icon: Link2,
  },
  {
    number: "05",
    title: "Scale",
    description:
      "We measure what Inversiq delivers, optimize the configuration, and expand to additional process areas. Volume grows — your team capacity stays constant.",
    detail: "Continuous improvement",
    Icon: TrendingUp,
  },
];

function useReducedMotion() {
  const [reduced, setReduced] = useState(false);
  useEffect(() => {
    const mq = window.matchMedia("(prefers-reduced-motion: reduce)");
    setReduced(mq.matches);
    const handler = (e: MediaQueryListEvent) => setReduced(e.matches);
    mq.addEventListener("change", handler);
    return () => mq.removeEventListener("change", handler);
  }, []);
  return reduced;
}

export default function HowItWorks() {
  const reducedMotion = useReducedMotion();
  const [visibleSet, setVisibleSet] = useState<Set<number>>(new Set());

  const markVisible = useCallback((index: number) => {
    setVisibleSet((prev) => {
      if (prev.has(index)) return prev;
      const next = new Set(prev); next.add(index); return next;
    });
  }, []);

  const maxVisible = visibleSet.size > 0 ? Math.max(...visibleSet) : -1;
  const progressPct = visibleSet.size > 0 ? ((maxVisible + 1) / steps.length) * 100 : 0;

  const headerRef = useRef<HTMLDivElement>(null);
  const [headerVisible, setHeaderVisible] = useState(false);

  useEffect(() => {
    if (reducedMotion) { setHeaderVisible(true); return; }
    const el = headerRef.current;
    if (!el) return;
    const io = new IntersectionObserver(
      ([e]) => { if (e.isIntersecting) { setHeaderVisible(true); io.disconnect(); } },
      { threshold: 0.2 }
    );
    io.observe(el);
    return () => io.disconnect();
  }, [reducedMotion]);

  return (
    <section id="deployment" className="py-14 lg:py-24 bg-neutral-50">
      <style>{`
        @keyframes bubblePulse { 0% { box-shadow: 0 0 0 0 rgba(37,99,235,0.35); } 60% { box-shadow: 0 0 0 7px rgba(37,99,235,0); } 100% { box-shadow: 0 0 0 0 rgba(37,99,235,0); } }
      `}</style>

      <div className="max-w-6xl mx-auto px-6">
        <div ref={headerRef} className="max-w-xl mb-10 lg:mb-20"
          style={{ opacity: headerVisible ? 1 : 0, transform: headerVisible ? "translateY(0px)" : "translateY(20px)",
            transition: reducedMotion ? "none" : "opacity 600ms ease, transform 600ms ease" }}>
          <p className="text-xs font-semibold uppercase tracking-widest text-neutral-400 mb-4">Deployment</p>
          <h2 className="text-4xl lg:text-5xl font-semibold tracking-tight text-neutral-900 leading-tight text-balance mb-6">
            From first conversation
            <br />
            to production system.
          </h2>
          <p className="text-lg text-neutral-500 leading-relaxed">
            Not months of consulting. Not a generic implementation. We configure, integrate, and deploy —
            and you measure results from week one.
          </p>
        </div>

        <div className="relative">
          <div className="absolute left-8 top-5 bottom-5 w-px hidden md:block"
            style={{ backgroundColor: "rgba(37,99,235,0.1)" }} />
          <div className="absolute left-8 top-5 w-px hidden md:block pointer-events-none"
            style={{ height: "calc(100% - 2.5rem)", overflow: "hidden" }}>
            <div style={{ width: "1px", height: `${progressPct}%`, backgroundColor: "#2563EB", opacity: 0.5,
              transition: reducedMotion ? "none" : "height 700ms cubic-bezier(0.4,0,0.2,1)" }} />
          </div>

          <div className="flex flex-col gap-0">
            {steps.map((step, i) => (
              <StepRow key={step.number} step={step} index={i} reducedMotion={reducedMotion} onVisible={markVisible} />
            ))}
          </div>
        </div>
      </div>
    </section>
  );
}

function StepRow({ step, index, reducedMotion, onVisible }: {
  step: typeof steps[number]; index: number; reducedMotion: boolean; onVisible: (i: number) => void;
}) {
  const rowRef = useRef<HTMLDivElement>(null);
  const [inView, setInView] = useState(false);
  const [revealed, setRevealed] = useState(false);
  const [hovered, setHovered] = useState(false);
  const [pulsing, setPulsing] = useState(false);
  const delay = index * 100;

  useEffect(() => {
    if (reducedMotion) { setInView(true); setRevealed(true); onVisible(index); return; }
    const el = rowRef.current;
    if (!el) return;
    const io = new IntersectionObserver(
      ([entry]) => {
        if (entry.isIntersecting) {
          setInView(true); onVisible(index);
          setTimeout(() => { setPulsing(true); setTimeout(() => setPulsing(false), 750); }, delay + 620);
          setTimeout(() => setRevealed(true), delay + 650);
          io.disconnect();
        }
      },
      { threshold: 0.1 }
    );
    io.observe(el);
    return () => io.disconnect();
  }, [reducedMotion, index, delay, onVisible]);

  const { Icon } = step;

  return (
    <div ref={rowRef} className="relative md:pl-24"
      style={{ opacity: inView ? 1 : 0, transform: inView ? "translateY(0px)" : "translateY(20px)",
        transition: reducedMotion ? "none" : `opacity 600ms ease ${delay}ms, transform 600ms ease ${delay}ms` }}
      onMouseEnter={() => setHovered(true)} onMouseLeave={() => setHovered(false)}>
      <div className="hidden md:flex absolute left-0 top-0 w-16 h-16 rounded-full items-center justify-center z-10"
        style={{
          backgroundColor: inView ? "#2563EB" : "white",
          border: inView ? "1px solid #2563EB" : "1px solid rgba(37,99,235,0.2)",
          animation: pulsing && !reducedMotion ? "bubblePulse 750ms ease forwards" : "none",
          transition: "background-color 350ms ease, border-color 350ms ease",
        }}>
        <span className="text-xs font-bold tracking-wider"
          style={{ color: inView ? "white" : "#2563EB", transition: "color 350ms ease" }}>
          {step.number}
        </span>
      </div>

      <div className="rounded-2xl p-7 mb-4"
        style={{
          backgroundColor: inView ? "rgba(37,99,235,0.04)" : "white",
          border: hovered ? "1px solid rgba(37,99,235,0.32)" : inView ? "1px solid rgba(37,99,235,0.18)" : "1px solid rgba(0,0,0,0.07)",
          boxShadow: hovered ? "0 4px 20px rgba(0,0,0,0.07), 0 1px 4px rgba(0,0,0,0.04)" : "none",
          transform: revealed && hovered ? "translateY(-4px)" : "translateY(0)",
          transition: ["background-color 300ms ease", "border-color 250ms ease", "box-shadow 250ms ease", "transform 250ms ease"].join(", "),
        }}>
        <span className="md:hidden text-xs font-bold tracking-wider mb-3 block"
          style={{ color: inView ? "#2563EB" : "rgba(37,99,235,0.35)" }}>{step.number}</span>
        <div className="flex items-center gap-2 mb-2.5">
          <Icon size={15} strokeWidth={1.75}
            style={{ color: inView ? "#2563EB" : "#c4c4c4", flexShrink: 0, transition: "color 350ms ease" }} />
          <h3 className="font-semibold text-lg tracking-tight leading-snug"
            style={{ color: inView ? "#1d4ed8" : "#0a0a0a", transition: "color 350ms ease" }}>
            {step.title}
          </h3>
        </div>
        <p className="text-sm leading-relaxed text-neutral-500 mb-4">{step.description}</p>
        <div className="flex sm:justify-end">
          <div className="inline-flex px-3 py-1 rounded-full font-medium whitespace-nowrap"
            style={{
              fontSize: "0.6875rem",
              ...(inView
                ? { backgroundColor: hovered ? "rgba(37,99,235,0.1)" : "rgba(37,99,235,0.07)", color: "#2563EB",
                    border: hovered ? "1px solid rgba(37,99,235,0.28)" : "1px solid rgba(37,99,235,0.14)", transition: "background-color 250ms, border-color 250ms" }
                : { backgroundColor: "#f5f5f5", color: "#a3a3a3", border: "1px solid rgba(0,0,0,0.06)" }),
            }}>
            {step.detail}
          </div>
        </div>
      </div>
    </div>
  );
}
