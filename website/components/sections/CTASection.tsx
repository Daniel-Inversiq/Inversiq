import { ArrowRight } from "lucide-react";

export default function CTASection() {
  return (
    <section className="py-12 lg:py-16 bg-neutral-50">
      <div className="max-w-6xl mx-auto px-6">
        <div className="relative overflow-hidden rounded-3xl bg-[#080C14] px-6 py-14 lg:px-8 lg:py-20 text-center">

          {/* Grid overlay */}
          <div className="absolute inset-0 opacity-[0.04] pointer-events-none"
            style={{
              backgroundImage: "linear-gradient(white 1px, transparent 1px), linear-gradient(90deg, white 1px, transparent 1px)",
              backgroundSize: "40px 40px",
            }} />

          {/* Blue glow */}
          <div className="absolute inset-0 flex items-center justify-center pointer-events-none" aria-hidden>
            <div className="w-[600px] h-[400px]"
              style={{ background: "radial-gradient(ellipse, rgba(37,99,235,0.22) 0%, transparent 70%)" }} />
          </div>

          <div className="relative max-w-2xl mx-auto">
            {/* Badge */}
            <div className="inline-flex items-center gap-2 px-3 py-1.5 rounded-full mb-6 text-[11px] font-semibold tracking-widest uppercase"
              style={{ backgroundColor: "rgba(37,99,235,0.12)", color: "rgba(147,197,253,1)", border: "1px solid rgba(37,99,235,0.25)" }}>
              <span className="w-1.5 h-1.5 rounded-full bg-blue-400" />
              Ready to deploy AI infrastructure?
            </div>

            <h2 className="text-4xl lg:text-5xl font-semibold tracking-tight text-white leading-tight text-balance mb-6">
              See Inversiq running
              on your own processes.
            </h2>

            <p className="text-lg text-neutral-400 leading-relaxed mb-10">
              A custom demo on your document types, your workflows, your systems.
              Not a generic walkthrough — real AI execution on what you actually do.
            </p>

            <div className="flex flex-col sm:flex-row gap-3 justify-center">
              <a href="/contact"
                className="inline-flex items-center justify-center gap-2 px-7 py-3.5 rounded-full text-[0.9375rem] font-semibold text-white transition-all duration-150 hover:opacity-90 active:scale-[0.98]"
                style={{ backgroundColor: "#2563EB", boxShadow: "0 0 0 1px rgba(59,130,246,0.3), 0 4px 16px rgba(37,99,235,0.35)" }}>
                Request a Custom Demo
                <ArrowRight size={16} />
              </a>
              <a href="/#platform"
                className="inline-flex items-center justify-center gap-2 px-7 py-3.5 rounded-full text-[0.9375rem] font-semibold transition-all duration-150"
                style={{ color: "#94A3B8", border: "1px solid rgba(255,255,255,0.12)", backgroundColor: "rgba(255,255,255,0.04)" }}>
                Explore the Platform
              </a>
            </div>

            <p className="mt-8 text-xs text-neutral-600">
              No sales pitch. No commitment. A real look at what Inversiq delivers for your operations.
            </p>
          </div>
        </div>
      </div>
    </section>
  );
}
