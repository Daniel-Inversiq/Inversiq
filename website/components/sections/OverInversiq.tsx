const pillars = [
  {
    title: "Platform, not product",
    description:
      "We build infrastructure that serves multiple clients, multiple verticals, and multiple use cases — from a single, maintained codebase. One core. Infinite depth.",
    icon: (
      <svg width="18" height="18" viewBox="0 0 18 18" fill="none">
        <path d="M3 5.5h12M3 9h7M3 12.5h5M13 10l2 2-2 2" stroke="#2563EB" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" />
      </svg>
    ),
  },
  {
    title: "Technology ownership",
    description:
      "Every core capability — from document intelligence to workflow orchestration — is built and owned by Inversiq. No third-party automation dependency. No vendor lock-in risk for our customers.",
    icon: (
      <svg width="18" height="18" viewBox="0 0 18 18" fill="none">
        <path d="M9 2.5v2M9 13.5v2M2.5 9h2M13.5 9h2M4.4 4.4l1.4 1.4M12.2 12.2l1.4 1.4M4.4 13.6l1.4-1.4M12.2 5.8l1.4-1.4" stroke="#2563EB" strokeWidth="1.5" strokeLinecap="round" />
        <circle cx="9" cy="9" r="2.5" stroke="#2563EB" strokeWidth="1.5" />
      </svg>
    ),
  },
  {
    title: "Industry depth",
    description:
      "We do not generalize. Each vertical module is built with deep domain knowledge — delivering accuracy and outcomes that horizontal tools cannot match.",
    icon: (
      <svg width="18" height="18" viewBox="0 0 18 18" fill="none">
        <path d="M3 13.5l4-4 3 3 5-6" stroke="#2563EB" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" />
        <path d="M14 4h-3M14 4v3" stroke="#2563EB" strokeWidth="1.5" strokeLinecap="round" />
      </svg>
    ),
  },
];

export default function OverInversiq() {
  return (
    <section id="about" className="py-12 lg:py-16 bg-white">
      <div className="max-w-6xl mx-auto px-6">
        <div className="lg:grid lg:grid-cols-[1fr_1fr] lg:gap-20 xl:gap-28 items-start">

          {/* Left */}
          <div className="mb-16 lg:mb-0 lg:sticky lg:top-32">
            <p className="text-xs font-semibold uppercase tracking-widest text-neutral-400 mb-4">About Inversiq</p>
            <h2 className="text-4xl lg:text-5xl font-semibold tracking-tight text-neutral-900 leading-tight text-balance mb-6">
              We&apos;re building the AI operating system
              for <span style={{ color: "#2563EB" }}>operational industries.</span>
            </h2>
            <p className="text-base text-neutral-500 leading-relaxed mb-5">
              Inversiq was founded on a single conviction: the industries that build, move, inspect, and maintain
              the physical world have been systematically underserved by enterprise software.
            </p>
            <p className="text-base text-neutral-500 leading-relaxed mb-5">
              These industries run on information that no existing system can read — inspection reports,
              damage assessments, field forms, contractor documents. The result is operational bottlenecks
              that cost time, money, and competitive advantage.
            </p>
            <p className="text-base text-neutral-500 leading-relaxed mb-8">
              We are building the infrastructure layer that changes this. Inversiq is an AI decision infrastructure platform
              designed for multi-tenant deployment across multiple industries — starting with construction,
              expanding systematically.
            </p>

            {/* Credo */}
            <div className="rounded-2xl px-6 py-5 flex flex-col gap-2"
              style={{ backgroundColor: "rgba(37,99,235,0.04)", border: "1px solid rgba(37,99,235,0.10)" }}>
              {[
                "Not a consultancy.",
                "Not a point solution.",
                "AI infrastructure for industries that run the world.",
              ].map((line, i) => (
                <div key={i} className="flex items-center gap-3">
                  <div className="w-1 h-1 rounded-full flex-shrink-0" style={{ backgroundColor: "#2563EB" }} />
                  <p className="text-sm font-medium" style={{ color: i === 2 ? "#2563EB" : "#404040" }}>{line}</p>
                </div>
              ))}
            </div>
          </div>

          {/* Right */}
          <div className="flex flex-col gap-4">
            {pillars.map((p) => (
              <div key={p.title}
                className="rounded-2xl p-6 flex items-start gap-5 transition-all duration-200 hover:shadow-[0_4px_16px_-4px_rgba(37,99,235,0.10)] hover:border-blue-200"
                style={{ backgroundColor: "#fafafa", border: "1px solid rgba(0,0,0,0.07)" }}>
                <div className="w-10 h-10 rounded-xl flex items-center justify-center flex-shrink-0 mt-0.5"
                  style={{ backgroundColor: "rgba(37,99,235,0.08)", border: "1px solid rgba(37,99,235,0.12)" }}>
                  {p.icon}
                </div>
                <div>
                  <p className="text-[0.9375rem] font-semibold text-neutral-900 mb-1 tracking-tight">{p.title}</p>
                  <p className="text-sm text-neutral-500 leading-relaxed">{p.description}</p>
                </div>
              </div>
            ))}

            {/* CTA nudge */}
            <div className="rounded-2xl p-6 mt-2"
              style={{ backgroundColor: "#0a0a0a", border: "1px solid rgba(255,255,255,0.06)" }}>
              <p className="text-sm font-medium text-white mb-1">
                Ready to see Inversiq in action on your processes?
              </p>
              <p className="text-sm text-neutral-400 mb-4 leading-relaxed">
                A custom demo. Your documents. Your workflows. No generic walkthrough.
              </p>
              <a href="/contact"
                className="inline-flex items-center gap-2 px-5 py-2.5 rounded-full text-sm font-semibold text-white transition-all duration-150 hover:opacity-90 active:scale-[0.98]"
                style={{ backgroundColor: "#2563EB" }}>
                Request a Demo
                <svg width="14" height="14" viewBox="0 0 14 14" fill="none">
                  <path d="M2.5 7h9M8 4l3.5 3L8 10" stroke="white" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" />
                </svg>
              </a>
            </div>
          </div>
        </div>
      </div>
    </section>
  );
}
