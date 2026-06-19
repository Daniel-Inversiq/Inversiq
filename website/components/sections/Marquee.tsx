const ITEMS = [
  "AI Agents op maat",
  "Workflow automatisering",
  "AI documentverwerking",
  "CRM automatisering",
  "Inbox automatisering",
  "GDPR-compliant",
  "Nederlandse AI consultancy",
  "Maatwerk per proces",
  "Meetbare resultaten",
];

// Duplicate for seamless loop
const TRACK = [...ITEMS, ...ITEMS];

export default function Marquee() {
  return (
    <div
      className="w-full overflow-hidden select-none"
      style={{ backgroundColor: "#111111" }}
      aria-hidden="true"
    >
      <div className="py-3.5 flex items-center">
        <div
          className="flex items-center gap-0 whitespace-nowrap"
          style={{
            animation: "marquee 32s linear infinite",
            willChange: "transform",
          }}
        >
          {TRACK.map((item, i) => (
            <span key={i} className="inline-flex items-center gap-4">
              <span
                className="text-[11px] font-medium tracking-widest uppercase"
                style={{ color: "rgba(255,255,255,0.65)" }}
              >
                {item}
              </span>
              {/* Dot separator */}
              <span
                className="w-1 h-1 rounded-full flex-shrink-0"
                style={{ backgroundColor: "#22c55e", opacity: 0.7 }}
              />
            </span>
          ))}
        </div>
      </div>

      <style>{`
        @keyframes marquee {
          from { transform: translateX(0); }
          to   { transform: translateX(-50%); }
        }
        @media (prefers-reduced-motion: reduce) {
          .marquee-track { animation: none; }
        }
      `}</style>
    </div>
  );
}
