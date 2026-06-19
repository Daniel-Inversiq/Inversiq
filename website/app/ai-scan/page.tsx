import type { Metadata } from "next";
import Navbar from "@/components/layout/Navbar";
import Footer from "@/components/layout/Footer";
import AIScan from "@/components/sections/AIScan";

export const metadata: Metadata = {
  title: "Gratis AI-automatisering scan | Inversiq",
  description:
    "Ontdek in 3 minuten welke processen binnen jouw organisatie geautomatiseerd kunnen worden en hoeveel tijd dat oplevert.",
};

export default function AIScanPage() {
  return (
    <>
      <Navbar />
      <AIScan />
      <Footer />
    </>
  );
}
