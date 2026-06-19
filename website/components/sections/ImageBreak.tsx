export default function ImageBreak() {
  return (
    <section className="py-16 bg-white">
      <div className="max-w-6xl mx-auto px-6">
        <div
          className="relative w-full overflow-hidden rounded-3xl"
          style={{ height: "clamp(320px, 38vw, 480px)" }}
        >
          {/* Photo */}
          {/* eslint-disable-next-line @next/next/no-img-element */}
          <img
            src="https://images.unsplash.com/photo-1497366754035-f200968a6e72?w=1800&q=75&auto=format&fit=crop&crop=center"
            alt="Modern kantooromgeving — Inversiq"
            className="absolute inset-0 w-full h-full object-cover object-center"
            loading="lazy"
            style={{ filter: "saturate(0.6) brightness(0.92)" }}
          />

          {/* Soft dark overlay for contrast + mood */}
          <div
            className="absolute inset-0"
            style={{
              background:
                "linear-gradient(135deg, rgba(10,10,10,0.52) 0%, rgba(10,10,10,0.28) 55%, rgba(10,10,10,0.18) 100%)",
            }}
          />

          {/* Content overlay — bottom-left */}
          <div className="absolute bottom-0 left-0 right-0 p-8 md:p-12">
            <div className="max-w-xl">
              {/* Blue accent badge */}
              <div className="flex items-center gap-2 mb-4">
                <div
                  className="w-6 h-0.5 rounded-full"
                  style={{ backgroundColor: "#60a5fa" }}
                />
                <span
                  className="text-[10px] font-semibold uppercase tracking-widest"
                  style={{ color: "#93c5fd" }}
                >
                  Van analyse naar implementatie
                </span>
              </div>

              <h3 className="text-2xl md:text-3xl font-semibold text-white leading-tight tracking-tight mb-3 text-balance">
                Wij automatiseren processen die
                daadwerkelijk gebruikt worden.
              </h3>

              <p className="text-sm md:text-base text-white/60 leading-relaxed max-w-sm">
                Van intake en documentverwerking tot AI-agents en
                workflowautomatisering.
              </p>
            </div>
          </div>
        </div>
      </div>
    </section>
  );
}
