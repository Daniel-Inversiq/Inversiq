"use client";

import { useEffect, useRef, useState } from "react";

const LAYERS = [
  {
    label: "Data Inputs",
    color: "#64748B",
    items: ["PDF / Documents", "Images / Video", "Forms & Surveys", "Email & Inbox", "REST APIs", "Field Data"],
  },
  {
    label: "Inversiq Core",
    color: "#2563EB",
    items: ["Document Intelligence", "Computer Vision", "Decision Engine", "Workflow Orchestration", "AI Agents", "Observability"],
    isCore: true,
  },
  {
    label: "Outputs & Integrations",
    color: "#10B981",
    items: ["CRM / ERP", "Field Systems", "Notifications", "Reports & Audit", "Downstream APIs", "Human Tasks"],
  },
];

const differentiators = [
  {
    title: "Multi-tenant by design",
    description:
      "One platform serves multiple clients, multiple verticals, and multiple deployment environments — without code changes per customer.",
  },
  {
    title: "Industry-specific modules",
    description:
      "Vertical modules extend the core for domain requirements: construction, insurance, logistics, field services — each with fine-tuned models.",
  },
  {
    title: "API-first architecture",
    description:
      "Every Inversiq capability is accessible via API — enabling custom integrations, partner products, and embedded deployments at any scale.",
  },
];

function useInView(threshold = 0.15) {
  const ref = useRef<HTMLDivElement>(null);
  const [visible, setVisible] = useState(false);
  useEffect(() => {
    const el = ref.current;
    if (!el) return;
    const io = new IntersectionObserver(
      ([e]) => { if (e.isIntersecting) { setVisible(true); io.disconnect(); } },
      { threshold }
    );
    io.observe(el);
    return () => io.disconnect();
  }, [threshold]);
  return { ref, visible };
}

export default function PlatformArchitecture() {
  const { ref, visible } = useInView(0.1);

  return (
    <section className="py-14 lg:py-24 bg-[#080C14]">
      <div className="max-w-6xl mx-auto px-6">

        {/* Header */}
        <div className="text-center max-w-2xl mx-auto mb-14 lg:mb-20">
          <p className="text-xs font-semibold uppercase tracking-widest mb-4" style={{ color: "#3B82F6" }}>
            Architecture
          </p>
          <h2 className="text-4xl lg:text-5xl font-semibold tracking-tight text-white leading-tight text-balance mb-6">
            Designed for depth.
            <br />
            <span style={{ color: "#3B82F6" }}>Built for scale.</span>
          </h2>
          <p className="text-lg leading-relaxed" style={{ color: "#94A3B8" }}>
            Inversiq is not a collection of point solutions. It&apos;s a purpose-built AI infrastructure layer
            with a shared data model, multi-tenant architecture, and industry-specific vertical modules.
          </p>
        </div>

        {/* Architecture diagram */}
        <div ref={ref} className="mb-16">
          <div className="max-w-4xl mx-auto flex flex-col gap-3">
            {LAYERS.map((layer, li) => (
              <div key={layer.label}>
                {/* Layer label */}
                <p className="text-[11px] font-semibold uppercase tracking-widest mb-2 px-1"
                  style={{ color: layer.isCore ? "#3B82F6" : "#475569" }}>
                  {layer.label}
                </p>

                {/* Layer box */}
                <div className="rounded-2xl p-4"
                  style={layer.isCore
                    ? { background: "linear-gradient(135deg, rgba(37,99,235,0.15) 0%, rgba(59,130,246,0.08) 100%)", border: "1px solid rgba(59,130,246,0.30)", boxShadow: "0 0 32px rgba(37,99,235,0.12)" }
                    : { background: "rgba(255,255,255,0.03)", border: "1px solid rgba(255,255,255,0.06)" }}>
                  <div className="grid grid-cols-3 sm:grid-cols-6 gap-2">
                    {layer.items.map((item, ii) => (
                      <div key={item}
                        className="rounded-xl px-3 py-2.5 text-center"
                        style={{
                          opacity: visible ? 1 : 0,
                          transform: visible ? "translateY(0px)" : "translateY(12px)",
                          transition: `opacity 400ms ease ${(li * 6 + ii) * 40}ms, transform 400ms ease ${(li * 6 + ii) * 40}ms`,
                          ...(layer.isCore
                            ? { background: "rgba(37,99,235,0.15)", border: "1px solid rgba(59,130,246,0.25)" }
                            : { background: "rgba(255,255,255,0.04)", border: "1px solid rgba(255,255,255,0.06)" }),
                        }}>
                        <p className="text-[11px] font-medium leading-tight"
                          style={{ color: layer.isCore ? "#93C5FD" : "#64748B" }}>
                          {item}
                        </p>
                      </div>
                    ))}
                  </div>
                </div>

                {/* Arrow between layers */}
                {li < LAYERS.length - 1 && (
                  <div className="flex justify-center my-2">
                    <svg width="16" height="24" viewBox="0 0 16 24" fill="none">
                      <path d="M8 0v18M2 12l6 8 6-8" stroke="#2563EB" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" strokeOpacity="0.5" />
                    </svg>
                  </div>
                )}
              </div>
            ))}
          </div>
        </div>

        {/* Differentiators */}
        <div className="grid sm:grid-cols-3 gap-5">
          {differentiators.map((d) => (
            <div key={d.title} className="rounded-2xl p-6"
              style={{ background: "rgba(255,255,255,0.03)", border: "1px solid rgba(255,255,255,0.07)" }}>
              <div className="w-8 h-8 rounded-lg flex items-center justify-center mb-4"
                style={{ backgroundColor: "rgba(37,99,235,0.15)", border: "1px solid rgba(59,130,246,0.25)" }}>
                <svg width="14" height="14" viewBox="0 0 14 14" fill="none">
                  <path d="M2 7l3.5 3.5L12 3" stroke="#3B82F6" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" />
                </svg>
              </div>
              <h3 className="font-semibold text-white mb-2 tracking-tight">{d.title}</h3>
              <p className="text-sm leading-relaxed" style={{ color: "#94A3B8" }}>{d.description}</p>
            </div>
          ))}
        </div>

      </div>
    </section>
  );
}
