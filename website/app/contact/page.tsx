import type { Metadata } from "next";
import Navbar from "@/components/layout/Navbar";
import Footer from "@/components/layout/Footer";
import DemoForm from "@/components/sections/DemoForm";

export const metadata: Metadata = {
  title: "Request a Demo | Inversiq",
  description:
    "See Inversiq running on your document types, workflows, and systems. A custom demo — not a generic walkthrough.",
  openGraph: {
    title: "Request a Demo | Inversiq",
    description:
      "See Inversiq running on your document types, workflows, and systems. A custom demo — not a generic walkthrough.",
    url: "https://inversiq.com/contact",
    siteName: "Inversiq",
    locale: "en_US",
    type: "website",
    images: [
      {
        url: "/contact/opengraph-image",
        width: 1200,
        height: 630,
        alt: "Request a Demo — Inversiq",
      },
    ],
  },
  twitter: {
    card: "summary_large_image",
    title: "Request a Demo | Inversiq",
    description:
      "See Inversiq running on your document types, workflows, and systems.",
    images: ["/contact/opengraph-image"],
  },
  alternates: {
    canonical: "https://inversiq.com/contact",
  },
};

export default function ContactPage() {
  return (
    <>
      <Navbar />
      <DemoForm />
      <Footer />
    </>
  );
}
