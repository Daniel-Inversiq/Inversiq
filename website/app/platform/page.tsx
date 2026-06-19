import type { Metadata } from "next";
import Navbar from "@/components/layout/Navbar";
import Footer from "@/components/layout/Footer";
import PlatformOverviewPage from "@/components/sections/PlatformOverviewPage";

export const metadata: Metadata = {
  title: "Platform",
  description:
    "Inversiq decision infrastructure transforms documents, images and operational data into governed decisions, automated workflows and measurable business outcomes.",
  openGraph: {
    title: "Platform Overview | Inversiq",
    description:
      "How Inversiq works: Document Intelligence, Computer Vision, Decision Infrastructure, Workflow Orchestration, AI Agents and Observability — in a single unified platform.",
    url: "https://inversiq.com/platform",
    siteName: "Inversiq",
    locale: "en_US",
    type: "website",
  },
  alternates: { canonical: "https://inversiq.com/platform" },
};

export default function Page() {
  return (
    <>
      <Navbar />
      <main>
        <PlatformOverviewPage />
      </main>
      <Footer />
    </>
  );
}
