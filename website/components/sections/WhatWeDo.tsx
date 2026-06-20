"use client";

import { useEffect, useRef, useState } from "react";
import { ArrowRight, ScanLine, Brain, Zap } from "lucide-react";

const PILLARS = [
  {
    icon: ScanLine,
    verb: "Reads",
    headline: "Every input, structured and ready to act on",
    body: "Documents, images, emails, forms, and field data — Inversiq extracts structured information from any source, at any volume, without manual processing.",
    color: "#3B82F6",
  },
  {
    icon: Brain,
    verb: "Decides",
    headline: "Your rules, applied consistently at scale",
    body: "Business logic defined once, executed reliably across thousands of cases. Full audit trails, automatic escalation for exceptions, and zero decisions falling through the cracks.",
    color: "#8B5CF6",
  },
  {
    icon: Zap,
    verb: "Acts",
    headline: "End-to-end execution across people and systems",
    body: "Inversiq coordinates AI agents, human tasks, and downstream systems across multi-step workflows — from intake to outcome, without manual handoffs.",
    color: "#10B981",
  },
];

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

export default function WhatWeDo() {
  const header = useInView(0.15);
  const pillars = useInView(0.08);

  return (
    <section id="platform" className="py-16 lg:py-28 bg-white">
      <div className="max-w-6xl mx-auto px-6">

        {/* Header */}
        <div
          ref={header.ref}
          className="max-w-2xl mb-14 lg:mb-20"
          style={{
            opacity: header.visible ? 1 : 0,
            transform: header.visible ? "none" : "translateY(20px)",
            transition: "opacity 600ms ease, transform 600ms ease",
          }}
        >
          <p className="text-[10px] font-bold uppercase tracking-widest mb-4" style={{ color: "#2563EB" }}>
            The Platform
          </p>
          <h2
            className="font-bold tracking-tight text-neutral-900 mb-5"
            style={{ fontSize: "clamp(1.75rem, 3.8vw, 3rem)", lineHeight: 1.1 }}
          >
            The AI operating system
            <br />
            <span style={{ color: "#2563EB" }}>for operational industries.</span>
          </h2>
          <p className="text-neutral-500 leading-relaxed" style={{ fontSize: "clamp(0.9375rem, 1.8vw, 1.0625rem)" }}>
            Inversiq is the intelligence layer between field operations and the decisions that need
            to happen at scale. One unified system — not a patchwork of integrations.
          </p>
        </div>

        {/* Three pillars */}
        <div
          ref={pillars.ref}
          className="grid lg:grid-cols-3 gap-5 mb-14"
        >
          {PILLARS.map((p, i) => {
            const Icon = p.icon;
            return (
              <div
                key={p.verb}
                className="rounded-2xl p-7 flex flex-col"
                style={{
                  border: "1px solid #E2E8F0",
                  boxShadow: "0 1px 6px rgba(0,0,0,0.04)",
                  opacity: pillars.visible ? 1 : 0,
                  transform: pillars.visible ? "none" : "translateY(20px)",
                  transition: `opacity 550ms ease ${i * 100}ms, transform 550ms ease ${i * 100}ms`,
                }}
              >
                {/* Icon + verb */}
                <div className="flex items-center gap-3 mb-5">
                  <div
                    className="w-10 h-10 rounded-xl flex items-center justify-center flex-shrink-0"
                    style={{ backgroundColor: `${p.color}10`, border: `1px solid ${p.color}25` }}
                  >
                    <Icon size={18} style={{ color: p.color }} />
                  </div>
                  <span
                    className="font-bold tracking-tight"
                    style={{ fontSize: "1.375rem", color: p.color }}
                  >
                    {p.verb}
                  </span>
                </div>

                <h3 className="font-semibold text-neutral-900 mb-3 leading-snug tracking-tight">
                  {p.headline}
                </h3>
                <p className="text-sm text-neutral-500 leading-relaxed flex-1">{p.body}</p>
              </div>
            );
          })}
        </div>

        {/* Platform teaser row */}
        <div
          className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-5 p-6 rounded-2xl"
          style={{
            backgroundColor: "rgba(37,99,235,0.03)",
            border: "1px solid rgba(37,99,235,0.10)",
            opacity: pillars.visible ? 1 : 0,
            transition: "opacity 600ms ease 350ms",
          }}
        >
          <div>
            <p className="text-sm font-semibold text-neutral-800 mb-1">
              Built on six core capabilities
            </p>
            <p className="text-xs text-neutral-400 leading-relaxed">
              Document Intelligence · Computer Vision · Decision Engine · Workflow Orchestration · AI Agents · Observability
            </p>
          </div>
          <a
            href="/platform"
            className="flex-shrink-0 inline-flex items-center gap-2 px-5 py-2.5 rounded-full text-sm font-semibold text-white transition-all duration-150 hover:opacity-90 active:scale-[0.98]"
            style={{ backgroundColor: "#2563EB", boxShadow: "0 1px 4px rgba(37,99,235,0.25)" }}
          >
            Explore the platform
            <ArrowRight size={13} strokeWidth={2.2} />
          </a>
        </div>

      </div>
    </section>
  );
}
