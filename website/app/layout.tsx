import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: {
    default: "Inversiq — AI Operating System for Operational Industries",
    template: "%s | Inversiq",
  },
  description:
    "Inversiq is an AI platform that reads documents, interprets field data, applies business logic, and executes workflows — across the operational industries that run the world.",
  keywords: [
    "AI platform",
    "document intelligence",
    "workflow orchestration",
    "AI execution engine",
    "construction AI",
    "operational AI",
    "decision engine",
    "AI agents",
    "enterprise AI",
    "EU AI Act",
    "GDPR compliant AI",
  ],
  authors: [{ name: "Inversiq", url: "https://inversiq.com" }],
  creator: "Inversiq",
  metadataBase: new URL("https://inversiq.com"),
  icons: {
    icon: [{ url: "/icon.svg", type: "image/svg+xml" }],
    apple: [{ url: "/apple-icon.svg", type: "image/svg+xml" }],
  },
  openGraph: {
    title: "Inversiq — AI Operating System for Operational Industries",
    description:
      "Inversiq is an AI platform that reads documents, interprets field data, applies business logic, and executes workflows — across the operational industries that run the world.",
    url: "https://inversiq.com",
    siteName: "Inversiq",
    locale: "en_US",
    type: "website",
    images: [
      {
        url: "/opengraph-image",
        width: 1200,
        height: 630,
        alt: "Inversiq — AI Operating System for Operational Industries",
      },
    ],
  },
  twitter: {
    card: "summary_large_image",
    title: "Inversiq — AI Operating System for Operational Industries",
    description:
      "The intelligence layer between work and decisions. Document intelligence, workflow orchestration, and AI agents — built for operational industries.",
    creator: "@inversiq",
    images: ["/opengraph-image"],
  },
  robots: {
    index: true,
    follow: true,
    googleBot: { index: true, follow: true },
  },
};

export default function RootLayout({
  children,
}: Readonly<{ children: React.ReactNode }>) {
  return (
    <html lang="en">
      <head>
        <link rel="preconnect" href="https://fonts.googleapis.com" />
        <link rel="preconnect" href="https://fonts.gstatic.com" crossOrigin="anonymous" />
        <link
          href="https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&display=swap"
          rel="stylesheet"
        />
      </head>
      <body className="antialiased">{children}</body>
    </html>
  );
}
