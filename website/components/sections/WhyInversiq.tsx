import { Zap, Target, Puzzle, TrendingUp, ShieldCheck } from "lucide-react";

const reasons = [
  {
    icon: Zap,
    title: "Weeks, not months",
    description:
      "Inversiq is built from proven, production-tested components. We configure the platform to your environment — not from scratch every time — so you see results fast.",
    stat: "Avg. 3–6 weeks live",
    wide: false,
  },
  {
    icon: Target,
    title: "Outcomes before technology",
    description:
      "We build only what delivers measurable time savings or quality improvements. If the ROI case isn't there, we'll tell you that before writing a line of code.",
    stat: "ROI-driven",
    wide: false,
  },
  {
    icon: Puzzle,
    title: "Your systems. Your processes.",
    description:
      "Inversiq integrates with what you already use. No migrations, no tool replacements, no processes turned upside down. Your team keeps working the way they work.",
    stat: "Zero migration required",
    wide: false,
  },
  {
    icon: TrendingUp,
    title: "Scale built in",
    description:
      "Once a process is automated, it scales with your volume. More requests, more documents — Inversiq handles it without adding headcount or increasing error rates.",
    stat: "Unlimited scale",
    wide: false,
  },
  {
    icon: ShieldCheck,
    title: "European compliance by design",
    description:
      "Inversiq is built to GDPR, EU AI Act, and industry-specific regulatory requirements — embedded in the platform architecture, not added as an afterthought. Audit trails, explainability, and data residency controls are standard.",
    stat: "GDPR & EU AI Act",
    wide: true,
  },
];

export default function WhyInversiq() {
  return (
    <section id="why" className="py-14 lg:py-24 bg-white">
      <div className="max-w-6xl mx-auto px-6">

        <div className="text-center max-w-2xl mx-auto mb-10 lg:mb-16">
          <p className="text-xs font-semibold uppercase tracking-widest text-neutral-400 mb-4">Why Inversiq</p>
          <h2 className="text-4xl lg:text-5xl font-semibold tracking-tight text-neutral-900 leading-tight text-balance mb-6">
            Infrastructure, not integration.
          </h2>
          <p className="text-lg text-neutral-500 leading-relaxed">
            Most AI tools solve one problem. Inversiq builds the layer that solves all of them —
            with shared data, shared logic, and full observability across every automated decision.
          </p>
        </div>

        <div className="grid sm:grid-cols-2 gap-5">
          {reasons.map((reason, i) => {
            const Icon = reason.icon;
            const isFirst = i === 0;
            return (
              <div key={reason.title}
                className={`group rounded-2xl p-8 transition-all duration-200 ${reason.wide ? "sm:col-span-2" : ""} ${
                  isFirst
                    ? "bg-[#2563EB] border border-[#2563EB]"
                    : "bg-neutral-50 border border-neutral-100 hover:bg-white hover:border-blue-200 hover:shadow-[0_4px_16px_-4px_rgba(37,99,235,0.08)]"
                }`}>
                <div className={`w-11 h-11 rounded-xl flex items-center justify-center mb-6 ${
                  isFirst ? "bg-white/[0.18]" : "bg-blue-50 border border-blue-100"
                }`}>
                  <Icon size={20} className={isFirst ? "text-white" : "text-blue-600"} />
                </div>
                <div className="flex items-start justify-between gap-4 mb-4">
                  <h3 className={`font-semibold text-xl tracking-tight ${isFirst ? "text-white" : "text-neutral-900"}`}>
                    {reason.title}
                  </h3>
                  <span className={`text-xs font-semibold px-2.5 py-1 rounded-full flex-shrink-0 mt-0.5 ${
                    isFirst ? "bg-white/[0.15] text-white/80" : "bg-blue-50 text-blue-600 border border-blue-100"
                  }`}>
                    {reason.stat}
                  </span>
                </div>
                <p className={`text-sm leading-relaxed ${isFirst ? "text-white/65" : "text-neutral-500"}`}>
                  {reason.description}
                </p>
              </div>
            );
          })}
        </div>
      </div>
    </section>
  );
}
