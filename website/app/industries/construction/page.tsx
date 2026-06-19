import type { Metadata } from "next";
import Navbar from "@/components/layout/Navbar";
import Footer from "@/components/layout/Footer";
import ConstructionPage from "@/components/sections/ConstructionPage";

export const metadata: Metadata = {
  title: "Construction",
  description:
    "Automate inspection reports, damage assessments, contractor quotes and project documentation with Inversiq — the AI decision infrastructure platform built for construction operations.",
  openGraph: {
    title: "AI Decision Infrastructure for Construction | Inversiq",
    description:
      "Automate the document-heavy workflows that slow down construction operations. Damage assessments, inspection reports, contractor quotes — all processed by Inversiq.",
    url: "https://inversiq.com/industries/construction",
    siteName: "Inversiq",
    locale: "en_US",
    type: "website",
  },
  alternates: { canonical: "https://inversiq.com/industries/construction" },
};

export default function Page() {
  return (
    <>
      <Navbar />
      <main>
        <ConstructionPage />
      </main>
      <Footer />
    </>
  );
}
