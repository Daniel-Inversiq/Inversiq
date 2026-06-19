"use client";

import { useEffect, useRef, useState, useCallback } from "react";
import { FileText, Mail, Database, Keyboard, BarChart2, GitBranch, type LucideIcon } from "lucide-react";

const problems: { icon: LucideIcon; title: string; description: string }[] = [
  {
    icon: FileText,
    title: "Documents no system can read",
    description:
      "Inspection reports, damage assessments, contractor forms — arriving as PDFs, photos, and scanned files. Your teams process them manually, one by one.",
  },
  {
    icon: Mail,
    title: "Inboxes that bottleneck operations",
    description:
      "Requests, approvals, and exceptions land in email and wait for human triage. As volume scales, so does the delay. Inversiq classifies and routes every message automatically.",
  },
  {
    icon: Database,
    title: "Systems that are always out of date",
    description:
      "CRMs, ERPs, and project platforms reflect what someone entered last — not what is actually happening. Inversiq keeps every system current in real time.",
  },
  {
    icon: Keyboard,
    title: "Data re-entered across every tool",
    description:
      "The same information typed into three different systems. Every handoff is a chance for error, delay, and inconsistency. Inversiq eliminates the step entirely.",
  },
  {
    icon: BarChart2,
    title: "Reports that take hours to produce",
    description:
      "Weekly numbers pulled from five places, formatted by hand, and delivered late. Inversiq generates operational reporting automatically from live data.",
  },
  {
    icon: GitBranch,
    title: "Workflows that stall on human approval",
    description:
      "Decisions that could be automated sit in queues waiting for sign-off. Inversiq applies your business logic and escalates only the exceptions that genuinely need attention.",
  },
];

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

function useInView(threshold = 0.12) {
  const ref = useRef<HTMLDivElement>(null);
  const [visible, setVisible] = useState(false);
  useEffect(() => {
    const el = ref.current;
    if (!el) return;
    const io = new IntersectionObserver(
      ([entry]) => { if (entry.isIntersecting) { setVisible(true); io.disconnect(); } },
      { threshold }
    );
    io.observe(el);
    return () => io.disconnect();
  }, [threshold]);
  return { ref, visible };
}

export default function ProblemSection() {
  const reducedMotion = useReducedMotion();
  const [visibleCount, setVisibleCount] = useState(0);
  const markCardVisible = useCallback(() => setVisibleCount((n) => n + 1), []);
  const allVisible = visibleCount >= problems.length;
  const { ref: headerRef, visible: headerVisible } = useInView(0.2);

  const reveal = (visible: boolean, delay = 0) =>
    reducedMotion ? {} : {
      opacity: visible ? 1 : 0,
      transform: visible ? "translateY(0px)" : "translateY(20px)",
      transition: `opacity 500ms ease ${delay}ms, transform 500ms ease ${delay}ms`,
    };

  return (
    <section className="py-14 lg:py-24 bg-neutral-50">
      <div className="max-w-6xl mx-auto px-6">

        <div ref={headerRef} className="max-w-xl mb-10 lg:mb-16" style={reveal(headerVisible)}>
          <p className="text-xs font-semibold uppercase tracking-widest text-neutral-400 mb-4">The Problem</p>
          <h2 className="text-4xl lg:text-5xl font-semibold tracking-tight text-neutral-900 leading-tight text-balance mb-6">
            Operational industries run on information
            <span style={{ color: "#2563EB" }}> no system knows how to read.</span>
          </h2>
          <p className="text-lg text-neutral-500 leading-relaxed">
            Documents, photos, forms, and emails arrive continuously — unstructured and unactionable.
            Your teams spend hours converting that information into decisions. Inversiq eliminates that step.
          </p>
        </div>

        <div className="grid sm:grid-cols-2 lg:grid-cols-3 gap-4">
          {problems.map((item, i) => (
            <ProblemCard
              key={item.title}
              item={item}
              index={i}
              reducedMotion={reducedMotion}
              onVisible={markCardVisible}
            />
          ))}
        </div>

        <div className="mt-12 flex items-center gap-3"
          style={reducedMotion ? {} : { opacity: allVisible ? 1 : 0, transition: "opacity 600ms ease" }}>
          <div className="h-px flex-1 bg-neutral-200" />
          <p className="text-sm text-neutral-400 px-4 text-center text-balance">
            Every one of these problems is solvable with existing infrastructure. The scan identifies which delivers the highest ROI.
          </p>
          <div className="h-px flex-1 bg-neutral-200" />
        </div>
      </div>
    </section>
  );
}

function ProblemCard({
  item, index, reducedMotion, onVisible,
}: { item: typeof problems[number]; index: number; reducedMotion: boolean; onVisible: () => void }) {
  const ref = useRef<HTMLDivElement>(null);
  const [inView, setInView] = useState(false);
  const [revealed, setRevealed] = useState(false);
  const [hovered, setHovered] = useState(false);

  const col = index % 3;
  const row = Math.floor(index / 3);
  const delay = reducedMotion ? 0 : row * 120 + col * 75;

  useEffect(() => {
    if (reducedMotion) { setInView(true); setRevealed(true); onVisible(); return; }
    const el = ref.current;
    if (!el) return;
    const io = new IntersectionObserver(
      ([entry]) => {
        if (entry.isIntersecting) {
          setInView(true); onVisible();
          setTimeout(() => setRevealed(true), delay + 520);
          io.disconnect();
        }
      },
      { threshold: 0.1 }
    );
    io.observe(el);
    return () => io.disconnect();
  }, [reducedMotion, delay, onVisible]);

  const Icon = item.icon;

  return (
    <div ref={ref}
      style={{ opacity: inView ? 1 : 0, transform: inView ? "translateY(0px)" : "translateY(20px)",
        transition: reducedMotion ? "none" : `opacity 500ms ease ${delay}ms, transform 500ms ease ${delay}ms` }}
      onMouseEnter={() => setHovered(true)} onMouseLeave={() => setHovered(false)}>
      <div className="h-full bg-white rounded-2xl p-7"
        style={{
          border: hovered ? "1px solid rgba(37,99,235,0.28)" : "1px solid rgba(0,0,0,0.07)",
          boxShadow: hovered ? "0 4px 20px -4px rgba(37,99,235,0.12), 0 1px 4px rgba(0,0,0,0.04)" : "0 1px 3px rgba(0,0,0,0.03)",
          transform: revealed && hovered ? "translateY(-4px)" : "translateY(0)",
          transition: "border-color 250ms ease, box-shadow 250ms ease, transform 250ms ease",
        }}>
        <div className="w-10 h-10 rounded-xl flex items-center justify-center mb-5"
          style={{
            backgroundColor: hovered ? "rgba(37,99,235,0.08)" : "rgba(37,99,235,0.05)",
            border: hovered ? "1px solid rgba(37,99,235,0.2)" : "1px solid rgba(37,99,235,0.1)",
            transition: "background-color 250ms ease, border-color 250ms ease",
          }}>
          <Icon size={17} strokeWidth={1.75} style={{ color: "#2563EB", transform: hovered ? "scale(1.08)" : "scale(1)", transition: "transform 250ms ease" }} />
        </div>
        <h3 className="font-semibold text-neutral-900 mb-2 tracking-tight">{item.title}</h3>
        <p className="text-sm text-neutral-500 leading-relaxed">{item.description}</p>
      </div>
    </div>
  );
}
