import { ImageResponse } from "next/og";

export const runtime = "edge";
export const alt = "Offerte aanvragen — Inversiq";
export const size = { width: 1200, height: 630 };
export const contentType = "image/png";

export default function OGImage() {
  return new ImageResponse(
    (
      <div
        style={{
          width: 1200,
          height: 630,
          display: "flex",
          flexDirection: "column",
          backgroundColor: "#ffffff",
          fontFamily: "sans-serif",
          position: "relative",
          overflow: "hidden",
        }}
      >
        {/* Grid background */}
        <div
          style={{
            position: "absolute",
            inset: 0,
            backgroundImage:
              "linear-gradient(rgba(37,99,235,0.04) 1px, transparent 1px), linear-gradient(90deg, rgba(37,99,235,0.04) 1px, transparent 1px)",
            backgroundSize: "60px 60px",
          }}
        />

        {/* Glow */}
        <div
          style={{
            position: "absolute",
            top: -100,
            right: -60,
            width: 480,
            height: 480,
            borderRadius: "50%",
            background: "radial-gradient(circle, rgba(37,99,235,0.10) 0%, transparent 70%)",
          }}
        />

        <div
          style={{
            position: "relative",
            display: "flex",
            flexDirection: "column",
            justifyContent: "space-between",
            height: "100%",
            padding: "64px 80px",
          }}
        >
          {/* Logo */}
          <div style={{ display: "flex", alignItems: "center", gap: 16 }}>
            <div
              style={{
                width: 48,
                height: 48,
                borderRadius: 12,
                backgroundColor: "#0a0a0a",
                display: "flex",
                alignItems: "center",
                justifyContent: "center",
              }}
            >
              <div style={{ position: "relative", width: 24, height: 24, display: "flex", alignItems: "center", justifyContent: "center" }}>
                <div style={{ position: "absolute", width: 14, height: 2.5, backgroundColor: "white", borderRadius: 2 }} />
                <div style={{ position: "absolute", width: 2.5, height: 14, backgroundColor: "white", borderRadius: 2 }} />
              </div>
            </div>
            <span style={{ fontSize: 26, fontWeight: 700, color: "#0a0a0a", letterSpacing: "-0.5px" }}>
              Inversiq
            </span>
          </div>

          {/* Main */}
          <div style={{ display: "flex", flexDirection: "column", gap: 24, maxWidth: 720 }}>
            <div
              style={{
                display: "inline-flex",
                backgroundColor: "rgba(37,99,235,0.08)",
                border: "1px solid rgba(37,99,235,0.18)",
                borderRadius: 100,
                padding: "8px 18px",
                width: "fit-content",
              }}
            >
              <span style={{ fontSize: 13, fontWeight: 700, letterSpacing: "1.5px", color: "#2563EB", textTransform: "uppercase" }}>
                Gratis · Vrijblijvend
              </span>
            </div>

            <div style={{ display: "flex", flexDirection: "column", gap: 4 }}>
              <span style={{ fontSize: 66, fontWeight: 800, color: "#0a0a0a", letterSpacing: "-2px", lineHeight: 1.05 }}>
                Offerte aanvragen.
              </span>
            </div>

            <span style={{ fontSize: 22, color: "#737373", lineHeight: 1.5 }}>
              Ontdek welke processen binnen jouw organisatie geautomatiseerd kunnen worden.
            </span>
          </div>

          {/* Bottom */}
          <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between" }}>
            <span style={{ fontSize: 17, color: "#a3a3a3", fontWeight: 500 }}>inversiq.com/contact</span>
            <div style={{ display: "flex", alignItems: "center", gap: 28 }}>
              {["Geen verplichtingen", "Binnen 1 werkdag reactie", "Gericht op jouw processen"].map((item) => (
                <div key={item} style={{ display: "flex", alignItems: "center", gap: 8 }}>
                  <div style={{ width: 7, height: 7, borderRadius: "50%", backgroundColor: "#2563EB" }} />
                  <span style={{ fontSize: 15, color: "#525252", fontWeight: 500 }}>{item}</span>
                </div>
              ))}
            </div>
          </div>
        </div>
      </div>
    ),
    { ...size }
  );
}
