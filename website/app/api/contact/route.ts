import { NextRequest, NextResponse } from "next/server";
import { Resend } from "resend";

const TO_EMAIL   = process.env.CONTACT_TO_EMAIL   ?? "dvanlieshout00@gmail.com";
const FROM_EMAIL = process.env.CONTACT_FROM_EMAIL ?? "onboarding@resend.dev";

export async function POST(req: NextRequest) {
  const apiKey = process.env.RESEND_API_KEY;
  if (!apiKey) {
    return NextResponse.json({ error: "Email service is not configured" }, { status: 500 });
  }

  const resend = new Resend(apiKey);

  try {
    const body = await req.json();
    const { naam, bedrijf, email, telefoon, bericht } = body;

    // ── Server-side validatie ──────────────────────────────────────
    if (!naam?.trim())    return NextResponse.json({ error: "Naam is verplicht."             }, { status: 400 });
    if (!bedrijf?.trim()) return NextResponse.json({ error: "Bedrijfsnaam is verplicht."     }, { status: 400 });
    if (!email?.trim())   return NextResponse.json({ error: "E-mailadres is verplicht."      }, { status: 400 });
    if (!bericht?.trim()) return NextResponse.json({ error: "Berichtinhoud is verplicht."    }, { status: 400 });
    if (!/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(email))
                          return NextResponse.json({ error: "Ongeldig e-mailadres."          }, { status: 400 });

    // ── E-mail versturen ───────────────────────────────────────────
    const { error } = await resend.emails.send({
      from: `Inversiq Contact <${FROM_EMAIL}>`,
      to:   [TO_EMAIL],
      replyTo: email,
      subject: `Nieuwe aanvraag van ${naam} — ${bedrijf}`,
      html: emailTemplate({ naam, bedrijf, email, telefoon, bericht }),
    });

    if (error) {
      console.error("[Resend error]", error);
      return NextResponse.json(
        { error: "Verzenden mislukt. Probeer het later opnieuw." },
        { status: 500 }
      );
    }

    return NextResponse.json({ success: true }, { status: 200 });

  } catch (err) {
    console.error("[Contact API error]", err);
    return NextResponse.json(
      { error: "Er is iets misgegaan. Probeer het later opnieuw." },
      { status: 500 }
    );
  }
}

// ── E-mail template ────────────────────────────────────────────────
function emailTemplate({
  naam, bedrijf, email, telefoon, bericht,
}: {
  naam: string; bedrijf: string; email: string;
  telefoon?: string; bericht: string;
}) {
  const escape = (s: string) =>
    s.replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;");

  return `<!DOCTYPE html>
<html lang="nl">
<head>
  <meta charset="UTF-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1.0" />
  <title>Nieuwe aanvraag — Inversiq</title>
</head>
<body style="margin:0;padding:0;background:#f5f5f5;font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',sans-serif;">
  <table width="100%" cellpadding="0" cellspacing="0" style="background:#f5f5f5;padding:40px 16px;">
    <tr>
      <td align="center">
        <table width="600" cellpadding="0" cellspacing="0" style="background:#ffffff;border-radius:12px;overflow:hidden;border:1px solid #e5e5e5;max-width:600px;width:100%;">

          <!-- Header -->
          <tr>
            <td style="background:#0a0a0a;padding:28px 40px;">
              <table cellpadding="0" cellspacing="0">
                <tr>
                  <td style="background:#1a1a1a;border-radius:8px;width:36px;height:36px;text-align:center;vertical-align:middle;padding:0 10px;">
                    <span style="color:white;font-size:20px;font-weight:700;line-height:36px;">+</span>
                  </td>
                  <td style="padding-left:12px;">
                    <span style="color:white;font-size:18px;font-weight:700;letter-spacing:-0.3px;">Inversiq</span>
                  </td>
                </tr>
              </table>
            </td>
          </tr>

          <!-- Body -->
          <tr>
            <td style="padding:40px;">

              <p style="margin:0 0 8px;font-size:13px;font-weight:600;text-transform:uppercase;letter-spacing:1.2px;color:#2563EB;">
                Nieuwe demo-aanvraag
              </p>
              <h1 style="margin:0 0 32px;font-size:24px;font-weight:700;color:#0a0a0a;letter-spacing:-0.5px;">
                ${escape(naam)} wil een demo plannen.
              </h1>

              <!-- Fields -->
              ${field("Naam",            escape(naam))}
              ${field("Bedrijf",         escape(bedrijf))}
              ${field("E-mailadres",     `<a href="mailto:${escape(email)}" style="color:#2563EB;text-decoration:none;">${escape(email)}</a>`)}
              ${telefoon?.trim() ? field("Telefoon", escape(telefoon)) : ""}

              <!-- Message -->
              <table width="100%" cellpadding="0" cellspacing="0" style="margin-top:8px;">
                <tr>
                  <td style="padding:0 0 6px;">
                    <span style="font-size:11px;font-weight:600;text-transform:uppercase;letter-spacing:1px;color:#a3a3a3;">
                      Wat wil je automatiseren?
                    </span>
                  </td>
                </tr>
                <tr>
                  <td style="background:#f8f8f8;border:1px solid #e5e5e5;border-radius:8px;padding:16px 20px;">
                    <p style="margin:0;font-size:15px;color:#404040;line-height:1.7;white-space:pre-wrap;">${escape(bericht)}</p>
                  </td>
                </tr>
              </table>

              <!-- CTA -->
              <table width="100%" cellpadding="0" cellspacing="0" style="margin-top:32px;">
                <tr>
                  <td>
                    <a href="mailto:${escape(email)}"
                       style="display:inline-block;background:#2563EB;color:white;font-size:14px;font-weight:600;padding:12px 24px;border-radius:100px;text-decoration:none;">
                      Beantwoord ${escape(naam)} →
                    </a>
                  </td>
                </tr>
              </table>

            </td>
          </tr>

          <!-- Footer -->
          <tr>
            <td style="padding:24px 40px;border-top:1px solid #f0f0f0;">
              <p style="margin:0;font-size:12px;color:#a3a3a3;line-height:1.6;">
                Verstuurd via het contactformulier op <a href="https://inversiq.com/contact" style="color:#2563EB;text-decoration:none;">inversiq.com/contact</a>
              </p>
            </td>
          </tr>

        </table>
      </td>
    </tr>
  </table>
</body>
</html>`;
}

function field(label: string, value: string): string {
  return `
  <table width="100%" cellpadding="0" cellspacing="0" style="margin-bottom:16px;">
    <tr>
      <td style="padding:0 0 4px;">
        <span style="font-size:11px;font-weight:600;text-transform:uppercase;letter-spacing:1px;color:#a3a3a3;">${label}</span>
      </td>
    </tr>
    <tr>
      <td style="padding:10px 16px;background:#fafafa;border:1px solid #e5e5e5;border-radius:8px;">
        <span style="font-size:15px;color:#0a0a0a;font-weight:500;">${value}</span>
      </td>
    </tr>
  </table>`;
}
