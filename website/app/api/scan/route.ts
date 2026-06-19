/**
 * POST /api/scan
 * Slaat een voltooide AI-automatisering scan op in de database.
 *
 * Aangeroepen door AIScan.tsx direct nadat het rapport is gegenereerd.
 * De gebruiker merkt hier niets van — fire-and-forget vanuit de client.
 */

import { NextRequest, NextResponse } from "next/server";
import { insertScan } from "@/lib/db";
import type { ScanInsert } from "@/lib/db";

export async function POST(req: NextRequest) {
  try {
    const body = await req.json();

    // ── Basis-validatie (server-side) ──────────────────────────────
    const required: (keyof ScanInsert)[] = [
      "company_name", "industry", "employees",
      "pain_points", "hours_lost", "urgency",
      "name", "email", "score", "generated_report",
    ];

    for (const field of required) {
      if (body[field] === undefined || body[field] === null || body[field] === "") {
        return NextResponse.json(
          { error: `Veld '${field}' is verplicht.` },
          { status: 400 }
        );
      }
    }

    if (!/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(body.email)) {
      return NextResponse.json({ error: "Ongeldig e-mailadres." }, { status: 400 });
    }

    // ── Opslaan ────────────────────────────────────────────────────
    const id = await insertScan({
      company_name:               body.company_name,
      industry:                   body.industry,
      employees:                  body.employees,
      tools:                      Array.isArray(body.tools)       ? body.tools       : [],
      pain_points:                Array.isArray(body.pain_points) ? body.pain_points : [],
      custom_problem_description: body.custom_problem_description ?? undefined,
      hours_lost:                 body.hours_lost,
      urgency:                    body.urgency,
      timeline:                   body.timeline ?? undefined,
      name:                       body.name,
      email:                      body.email,
      phone:                      body.phone ?? undefined,
      score:                      Number(body.score),
      generated_report:           body.generated_report,
    });

    console.log(`[scan] Opgeslagen: id=${id}, bedrijf="${body.company_name}", score=${body.score}`);

    // ── TODO: E-mail notificatie ───────────────────────────────────
    //
    // Stuur hier een notificatie-e-mail naar het Inversiq-team zodra
    // een scan is afgerond. Gebruik dezelfde Resend-integratie als in
    // app/api/contact/route.ts.
    //
    // Voorbeeld:
    //
    //   import { Resend } from "resend";
    //   const resend = new Resend(process.env.RESEND_API_KEY);
    //   await resend.emails.send({
    //     from: `Inversiq Scan <${process.env.CONTACT_FROM_EMAIL}>`,
    //     to: [process.env.CONTACT_TO_EMAIL ?? "dvanlieshout00@gmail.com"],
    //     subject: `Nieuwe AI-scan: ${body.company_name} (score: ${body.score})`,
    //     html: scanEmailTemplate({ id, ...body }),
    //   });
    //
    // Bouw scanEmailTemplate() analoog aan emailTemplate() in
    // app/api/contact/route.ts — inclusief score, top kansen en
    // contactgegevens van de invuller.
    // ─────────────────────────────────────────────────────────────

    return NextResponse.json({ success: true, id }, { status: 201 });

  } catch (err) {
    console.error("[scan API error]", err);
    return NextResponse.json(
      { error: "Opslaan mislukt. Probeer het later opnieuw." },
      { status: 500 }
    );
  }
}
