"use client";

import { useEffect, useRef, useState } from "react";

const items = [
  {
    value: 30,
    prefix: "< ",
    suffix: " sec",
    staticValue: "",
    title: "Time to decision",
    label: "From document ingestion to system action",
  },
  {
    value: 94,
    prefix: "",
    suffix: "%",
    staticValue: "",
    title: "Automation rate",
    label: "Documents processed without manual review",
  },
  {
    value: 0,
    prefix: "",
    suffix: "",
    staticValue: "Weeks",
    title: "Time to production",
    label: "No migration. No legacy replacement.",
  },
  {
    value: 0,
    prefix: "",
    suffix: "",
    staticValue: "Multi-vertical",
    title: "Platform architecture",
    label: "One core engine. Infinite industry depth.",
  },
] as const;

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

function useCountUp(target: number, run: boolean, durationMs = 1200) {
  const [value, setValue] = useState(0);
  useEffect(() => {
    if (!run || target === 0) { setValue(target === 0 ? 0 : 0); return; }
    let raf: number;
    const start = performance.now();
    const tick = (now: number) => {
      const t = Math.min((now - start) / durationMs, 1);
      const eased = 1 - Math.pow(1 - t, 3);
      setValue(Math.round(eased * target));
      if (t < 1) raf = requestAnimationFrame(tick);
    };
    raf = requestAnimationFrame(tick);
    return () => cancelAnimationFrame(raf);
  }, [run, target, durationMs]);
  return value;
}

export default function StatsBar() {
  const reducedMotion = useReducedMotion();
  const ref = useRef<HTMLDivElement>(null);
  const [inView, setInView] = useState(false);

  useEffect(() => {
    if (reducedMotion) { setInView(true); return; }
    const el = ref.current;
    if (!el) return;
    const io = new IntersectionObserver(
      ([entry]) => { if (entry.isIntersecting) { setInView(true); io.disconnect(); } },
      { threshold: 0.3 }
    );
    io.observe(el);
    return () => io.disconnect();
  }, [reducedMotion]);

  return (
    <div ref={ref} className="w-full border-y"
      style={{ backgroundColor: "#F8FAFC", borderColor: "rgba(0,0,0,0.07)" }}>
      <div className="max-w-6xl mx-auto px-6 py-10 lg:py-12">
        <div className="grid grid-cols-2 lg:grid-cols-4 gap-x-6 gap-y-8">
          {items.map((item, i) => (
            <MetricCell key={item.title} item={item} index={i} inView={inView} reducedMotion={reducedMotion} />
          ))}
        </div>
      </div>
    </div>
  );
}

function MetricCell({
  item, index, inView, reducedMotion,
}: { item: typeof items[number]; index: number; inView: boolean; reducedMotion: boolean }) {
  const delay = index * 90;
  const [run, setRun] = useState(false);

  useEffect(() => {
    if (!inView) return;
    if (reducedMotion) { setRun(true); return; }
    const t = setTimeout(() => setRun(true), delay);
    return () => clearTimeout(t);
  }, [inView, reducedMotion, delay]);

  const counted = useCountUp(item.value, run);
  const isStatic = Boolean(item.staticValue);
  const display = isStatic
    ? item.staticValue
    : `${item.prefix}${reducedMotion ? item.value : counted}${item.suffix}`;

  return (
    <div className="flex flex-col"
      style={reducedMotion ? {} : {
        opacity: inView ? 1 : 0,
        transform: inView ? "translateY(0px)" : "translateY(14px)",
        transition: `opacity 500ms ease ${delay}ms, transform 500ms ease ${delay}ms`,
      }}>
      <p className="font-bold tracking-tight leading-none mb-2"
        style={{ fontSize: "clamp(1.75rem,3vw,2.25rem)", color: "#2563EB", fontVariantNumeric: "tabular-nums" }}>
        {display}
      </p>
      <p className="text-sm font-semibold text-neutral-900 tracking-tight mb-1">{item.title}</p>
      <p className="text-xs text-neutral-400 leading-relaxed">{item.label}</p>
    </div>
  );
}
