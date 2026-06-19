/**
 * scanReport.ts
 * Rule-based rapport-generator voor de AI-automatisering scan.
 *
 * ─── AI INTEGRATION POINT ──────────────────────────────────────────────────
 * Om dit te vervangen door een echte AI-call:
 *
 * 1. Vervang de body van `generateReport()` door een fetch naar `/api/scan`
 * 2. Maak `website/app/api/scan/route.ts` aan
 * 3. Roep daar de Anthropic SDK aan:
 *
 *    import Anthropic from "@anthropic-ai/sdk";
 *    const client = new Anthropic();
 *    const message = await client.messages.create({
 *      model: "claude-opus-4-5",
 *      max_tokens: 1024,
 *      messages: [{ role: "user", content: buildPrompt(data) }],
 *    });
 *
 * De signatuur van `generateReport(data: ScanData): ScanReport` blijft gelijk.
 * ───────────────────────────────────────────────────────────────────────────
 */

/* ── Types ─────────────────────────────────────────────── */

export interface ScanData {
  // Stap 1
  bedrijfsnaam: string;
  branche: string;
  medewerkers: string;
  software: string[];

  // Stap 2
  tijdverlies: string[];
  beschrijving: string;

  // Stap 3
  tijdPerWeek: string;
  urgentie: string;

  // Stap 4
  naam: string;
  email: string;
  telefoon: string;
  timing?: string;  // "Wanneer wil je hier iets mee doen?" — optioneel, voor lead scoring
}

export interface Kans {
  titel: string;
  beschrijving: string;
  tijdsbesparing: string;
}

export interface ScanReport {
  score: number;                // 0–100
  scorelabel: string;           // "Laag" | "Gemiddeld" | "Hoog" | "Zeer hoog"
  samenvatting: string;
  kansen: Kans[];               // top 3
  tijdsbesparing: string;       // bijv. "8–12 uur per week"
  eersteStap: string;
}

/* ── Kansen-bibliotheek ────────────────────────────────── */

const KANSEN_MAP: Record<string, Kans> = {
  Offerteproces: {
    titel: "Geautomatiseerd offerteproces",
    beschrijving:
      "Offertes automatisch samenstellen op basis van klantinformatie, productcatalogus en sjablonen — zonder handmatig werk.",
    tijdsbesparing: "2–5 uur/week",
  },
  "E-mailverwerking": {
    titel: "AI e-mailsortering en -routing",
    beschrijving:
      "Inkomende e-mails automatisch categoriseren, prioriteren en doorsturen naar de juiste persoon of afdeling.",
    tijdsbesparing: "3–6 uur/week",
  },
  Documentverwerking: {
    titel: "Intelligente documentextractie",
    beschrijving:
      "Facturen, contracten en formulieren automatisch uitlezen, valideren en verwerken in bestaande systemen.",
    tijdsbesparing: "4–8 uur/week",
  },
  "CRM-updates": {
    titel: "Automatische CRM-synchronisatie",
    beschrijving:
      "Contactgegevens, dealstatus en interacties automatisch bijhouden zonder handmatige invoer.",
    tijdsbesparing: "2–4 uur/week",
  },
  Facturatie: {
    titel: "Geautomatiseerde facturatieworkflow",
    beschrijving:
      "Facturen automatisch genereren, verzenden en opvolgen — inclusief herinneringen en betalingsverwerking.",
    tijdsbesparing: "2–5 uur/week",
  },
  Klantadministratie: {
    titel: "Slimme klantdossiers",
    beschrijving:
      "Klantgegevens, correspondentie en documenten automatisch organiseren en up-to-date houden.",
    tijdsbesparing: "3–5 uur/week",
  },
  Rapportages: {
    titel: "Automatische rapportgeneratie",
    beschrijving:
      "Wekelijkse en maandelijkse rapporten automatisch samenstellen uit meerdere databronnen.",
    tijdsbesparing: "2–4 uur/week",
  },
  Planning: {
    titel: "AI-gestuurde planningsoptimalisatie",
    beschrijving:
      "Capaciteitsplanning, afspraken en resourceallocatie automatisch coördineren en aanpassen.",
    tijdsbesparing: "2–4 uur/week",
  },
  Anders: {
    titel: "Maatwerk procesautomatisering",
    beschrijving:
      "Op basis van jouw specifieke situatie een gerichte automatisering ontwerpen die direct waarde oplevert.",
    tijdsbesparing: "variabel",
  },
};

const FALLBACK_KANSEN: Kans[] = [
  KANSEN_MAP["E-mailverwerking"],
  KANSEN_MAP["Documentverwerking"],
  KANSEN_MAP["CRM-updates"],
];

/* ── Hulpfuncties ──────────────────────────────────────── */

function tijdScore(tijdPerWeek: string): number {
  const map: Record<string, number> = {
    "Minder dan 5 uur": 20,
    "5–10 uur": 35,
    "10–20 uur": 52,
    "20–40 uur": 65,
    "Meer dan 40 uur": 78,
  };
  return map[tijdPerWeek] ?? 30;
}

function urgentieBonus(urgentie: string): number {
  const map: Record<string, number> = {
    Laag: 0,
    Gemiddeld: 7,
    Hoog: 13,
    "Zeer hoog": 18,
  };
  return map[urgentie] ?? 0;
}

function tijdsbesparingLabel(tijdPerWeek: string): string {
  const map: Record<string, string> = {
    "Minder dan 5 uur": "2–3 uur per week",
    "5–10 uur": "4–6 uur per week",
    "10–20 uur": "7–12 uur per week",
    "20–40 uur": "14–24 uur per week",
    "Meer dan 40 uur": "25–35+ uur per week",
  };
  return map[tijdPerWeek] ?? "meerdere uren per week";
}

function eersteStapTekst(kansen: Kans[], data: ScanData): string {
  const top = kansen[0];
  if (!top) return "Plan een gesprek om de mogelijkheden te verkennen.";

  const branchemap: Record<string, string> = {
    "Zakelijke dienstverlening": "jullie klantprocessen",
    "Bouw & vastgoed": "jullie project- en documentworkflow",
    "Handel & retail": "jullie order- en voorraadprocessen",
    "Financiële diensten": "jullie rapportage- en complianceprocessen",
  };

  const context = branchemap[data.branche] ?? "jullie processen";
  return `Start met een gerichte analyse van ${context} rondom "${top.titel}" — dit levert binnen 2–4 weken al meetbare tijdsbesparing op.`;
}

/* ── Hoofdfunctie ──────────────────────────────────────── */

export function generateReport(data: ScanData): ScanReport {
  // Score
  const base  = tijdScore(data.tijdPerWeek);
  const bonus = urgentieBonus(data.urgentie);
  const pains = Math.min(data.tijdverlies.length * 2, 8);
  const score = Math.min(base + bonus + pains, 100);

  // Score label
  const scorelabel =
    score >= 75 ? "Zeer hoog"
    : score >= 55 ? "Hoog"
    : score >= 35 ? "Gemiddeld"
    : "Laag";

  // Top 3 kansen
  const kansen: Kans[] = data.tijdverlies
    .filter((t) => KANSEN_MAP[t])
    .map((t) => KANSEN_MAP[t])
    .slice(0, 3);

  // Vul aan tot 3 met fallbacks als er te weinig zijn aangevinkt
  const fallbackPool = FALLBACK_KANSEN.filter(
    (f) => !kansen.some((k) => k.titel === f.titel)
  );
  while (kansen.length < 3 && fallbackPool.length > 0) {
    kansen.push(fallbackPool.shift()!);
  }

  // Samenvatting
  const samenvatting =
    `${data.bedrijfsnaam || "Jouw organisatie"} besteedt momenteel ${
      data.tijdPerWeek.toLowerCase()
    } aan handmatige processen. ` +
    `Op basis van de scan schatten we een automatiseringspotentieel van ${score} op 100 — ` +
    `${scorelabel.toLowerCase()} — met concrete kansen rondom ${
      kansen
        .slice(0, 2)
        .map((k) => k.titel.toLowerCase())
        .join(" en ")
    }.`;

  return {
    score,
    scorelabel,
    samenvatting,
    kansen,
    tijdsbesparing: tijdsbesparingLabel(data.tijdPerWeek),
    eersteStap: eersteStapTekst(kansen, data),
  };
}
