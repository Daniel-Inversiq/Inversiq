import type { Metadata } from "next";
import { Inter } from "next/font/google";
import "./globals.css";
import { AppProviders } from "@/components/shared/app-providers";
import { cn } from "@/lib/utils";

const inter = Inter({
  subsets: ["latin", "latin-ext"],
  display: "swap",
  variable: "--font-inter",
  adjustFontFallback: true,
});

export const metadata: Metadata = {
  title: "Inversiq SaaS Frontend",
  description: "Modern Next.js frontend for Inversiq",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="nl" className={cn(inter.variable, "h-full antialiased")}>
      <body className="min-h-full bg-background font-sans text-foreground">
        <AppProviders>{children}</AppProviders>
      </body>
    </html>
  );
}
