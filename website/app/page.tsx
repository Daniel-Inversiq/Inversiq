import type { Metadata } from "next";

export const metadata: Metadata = {
  title: "Inversiq — AI Operating System for Operational Industries",
  description:
    "Inversiq is the AI decision infrastructure platform that reads documents, interprets field data, applies business logic, and executes workflows — built for construction, insurance, logistics, and field services.",
  openGraph: {
    title: "Inversiq — AI Operating System for Operational Industries",
    description:
      "The intelligence layer between work and decisions. Document intelligence, workflow orchestration, and AI agents — built for the industries that run the world.",
    url: "https://inversiq.com",
    siteName: "Inversiq",
    locale: "en_US",
    type: "website",
  },
  twitter: {
    card: "summary_large_image",
    title: "Inversiq — AI Operating System for Operational Industries",
    description:
      "Inversiq: AI decision infrastructure that reads, decides, and acts. Built for operational industries.",
  },
  alternates: { canonical: "https://inversiq.com" },
};

import Navbar from "@/components/layout/Navbar";
import Footer from "@/components/layout/Footer";
import Hero from "@/components/sections/Hero";
import StatsBar from "@/components/sections/StatsBar";
import ProblemSection from "@/components/sections/ProblemSection";
import WhatWeDo from "@/components/sections/WhatWeDo";
import PlatformArchitecture from "@/components/sections/PlatformArchitecture";
import IndustryVerticals from "@/components/sections/IndustryVerticals";
import ResultsSection from "@/components/sections/ResultsSection";
import HowItWorks from "@/components/sections/HowItWorks";
import WhyInversiq from "@/components/sections/WhyInversiq";
import OverInversiq from "@/components/sections/OverInversiq";
import Careers from "@/components/sections/Careers";
import FAQSection from "@/components/sections/FAQSection";
import CTASection from "@/components/sections/CTASection";
import FloatingCTA from "@/components/ui/FloatingCTA";

export default function Home() {
  return (
    <>
      <Navbar />
      <main>
        <Hero />
        <StatsBar />
        <ProblemSection />
        <WhatWeDo />
        <PlatformArchitecture />
        <IndustryVerticals />
        <ResultsSection />
        <HowItWorks />
        <WhyInversiq />
        <OverInversiq />
        <Careers />
        <FAQSection />
        <CTASection />
      </main>
      <Footer />
      <FloatingCTA />
    </>
  );
}
