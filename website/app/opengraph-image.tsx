import { ImageResponse } from "next/og";

export const runtime = "edge";
export const alt = "Inversiq — AI Automatisering voor Bedrijfsprocessen";
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
        {/* Subtle grid background */}
        <div
          style={{
            position: "absolute",
            inset: 0,
            backgroundImage:
              "linear-gradient(rgba(37,99,235,0.04) 1px, transparent 1px), linear-gradient(90deg, rgba(37,99,235,0.04) 1px, transparent 1px)",
            backgroundSize: "60px 60px",
          }}
        />

        {/* Blue accent glow top-right */}
        <div
          style={{
            position: "absolute",
            top: -120,
            right: -80,
            width: 500,
            height: 500,
            borderRadius: "50%",
            background:
              "radial-gradient(circle, rgba(37,99,235,0.12) 0%, transparent 70%)",
          }}
        />

        {/* Blue accent glow bottom-left */}
        <div
          style={{
            position: "absolute",
            bottom: -100,
            left: -60,
            width: 400,
            height: 400,
            borderRadius: "50%",
            background:
              "radial-gradient(circle, rgba(37,99,235,0.08) 0%, transparent 70%)",
          }}
        />

        {/* Content */}
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
            {/* Logo mark */}
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
              {/* Plus icon — approximated with two rectangles */}
              <div style={{ position: "relative", width: 24, height: 24, display: "flex", alignItems: "center", justifyContent: "center" }}>
                <div style={{ position: "absolute", width: 14, height: 2.5, backgroundColor: "white", borderRadius: 2 }} />
                <div style={{ position: "absolute", width: 2.5, height: 14, backgroundColor: "white", borderRadius: 2 }} />
              </div>
            </div>
            {/* Wordmark */}
            <span
              style={{
                fontSize: 26,
                fontWeight: 700,
                color: "#0a0a0a",
                letterSpacing: "-0.5px",
              }}
            >
              Inversiq
            </span>
          </div>

          {/* Main text */}
          <div style={{ display: "flex", flexDirection: "column", gap: 24, maxWidth: 760 }}>
            {/* Badge */}
            <div
              style={{
                display: "inline-flex",
                alignItems: "center",
                backgroundColor: "rgba(37,99,235,0.08)",
                border: "1px solid rgba(37,99,235,0.18)",
                borderRadius: 100,
                padding: "8px 18px",
                width: "fit-content",
              }}
            >
              <span
                style={{
                  fontSize: 13,
                  fontWeight: 700,
                  letterSpacing: "1.5px",
                  color: "#2563EB",
                  textTransform: "uppercase",
                }}
              >
                AI Automation Consultancy
              </span>
            </div>

            {/* Headline */}
            <div style={{ display: "flex", flexDirection: "column", gap: 4 }}>
              <span
                style={{
                  fontSize: 64,
                  fontWeight: 800,
                  color: "#0a0a0a",
                  letterSpacing: "-2px",
                  lineHeight: 1.05,
                }}
              >
                Stop met repetitief werk.
              </span>
              <span
                style={{
                  fontSize: 64,
                  fontWeight: 800,
                  letterSpacing: "-2px",
                  lineHeight: 1.05,
                  color: "#2563EB",
                }}
              >
                Laat AI het uitvoeren.
              </span>
            </div>

            {/* Subtext */}
            <span
              style={{
                fontSize: 22,
                color: "#737373",
                lineHeight: 1.5,
                fontWeight: 400,
              }}
            >
              Wij helpen organisaties repetitieve processen automatiseren met AI,
              workflows en maatwerk software.
            </span>
          </div>

          {/* Bottom bar */}
          <div
            style={{
              display: "flex",
              alignItems: "center",
              justifyContent: "space-between",
            }}
          >
            <span style={{ fontSize: 17, color: "#a3a3a3", fontWeight: 500 }}>
              inversiq.com
            </span>
            <div
              style={{
                display: "flex",
                alignItems: "center",
                gap: 10,
                backgroundColor: "#2563EB",
                borderRadius: 100,
                padding: "14px 28px",
              }}
            >
              <span style={{ fontSize: 17, fontWeight: 700, color: "white" }}>
                Offerte aanvragen →
              </span>
            </div>
          </div>
        </div>
      </div>
    ),
    { ...size }
  );
}
