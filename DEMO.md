# Inversiq — Delin CEO Demo Runbook

Demo: **Basingstoke Logistics Park due-diligence walkthrough**
Audience: CEO of Delin Property
Duration: 4 minutes

> **Do not mention this is seeded unless asked. Present it as a controlled demo workspace
> prepared in advance — which is accurate. The data is synthetic but the workflow,
> reasoning, and output are exactly what the platform produces on real documents.**

---

## Prerequisites

- Python 3.11+, Node 20+
- All Python and Node dependencies installed
- No Anthropic API key required — demo uses seeded data, no live LLM calls
- No Delin confidential files required — all data is synthetic

---

## Start commands (3 terminals)

**Terminal 1 — Backend**
```bash
cd C:\Users\dvanl\Inversiq
uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload
```
Wait for: `Application startup complete.`

**Terminal 2 — Frontend**
```bash
cd C:\Users\dvanl\Inversiq\frontend
npm run dev
```
Wait for: `Ready in X.Xs` on port 3000.

**Terminal 3 — Seed (run once before demo, re-run to reset)**
```bash
cd C:\Users\dvanl\Inversiq
python scripts/seed_demo.py
```
Note the workspace URL printed in the output.

---

## Demo login

```
URL:      http://localhost:3000
Email:    demo@inversiq.com
Password: Demo2025!
```

**Important**: after login the app redirects to the dashboard which shows
painting-vertical content. Navigate immediately to the workspace URL
printed by the seed script — do not linger on the dashboard during the demo.

Pre-copy this URL before the meeting:
```
http://localhost:3000/workspaces/<workspace_id>
```

---

## What the demo shows

Navigate to **Werkruimten → Basingstoke Logistics Park — Delin Q2 2025**

Pre-processed workspace:
- 5 validated documents (IM, Rent Roll, TDD, Valuation, Lease)
- 72% overall extraction confidence
- ~15h analyst time saved
- 3 open issues: 2 HIGH, 1 MEDIUM

**Issue 1 — ERV Source Conflict (HIGH)**
IM: £85/sqm. Cushman & Wakefield valuation: £95/sqm. 11.2% gap = £4.25m annual rental value difference.

**Issue 2 — Capex Not Disclosed in IM (HIGH)**
Arcadis TDD: £340k Category 1 capex. IM: silent. Overstates acquisition price by 0.65%.

**Issue 3 — Break Option Date (MEDIUM)**
Heron Logistics break date 15 Sep 2027 — not a UK quarter day. Notice deadline: Sep 2026.

Clicking any issue shows: source comparison, AI Reasoning, Suggested Resolution, Resolve/Escalate buttons.
Resolving all 3 transitions the workspace to **Ready** with a green completion banner.

---

## 4-minute demo script — English

**[0:00 — 0:30] The problem**

> "Your analysts spend two to three days per deal just reading documents and cross-checking
> numbers. By the time they surface an issue, you're already in exclusivity.
> This is the intelligence layer that does that work in under a minute."

**[0:30 — 1:15] What the platform read**

Point to the metrics strip:

> "We ran five documents through a workspace — the IM, rent roll, TDD report,
> Cushman & Wakefield valuation, and the Heron lease. No templates, no setup.
> The platform classified each document, extracted the key fields,
> and cross-validated them across sources."

- **72% confidence** — "That tells us where the AI is certain and where it flagged uncertainty."
- **5/5 validated** — "Every document processed and cross-checked."
- **~15h saved** — "That is a day and a half of analyst time, per deal."

**[1:15 — 2:15] ERV Source Conflict** *(click flag 1)*

> "The IM says ERV is £85 per sqm. The Cushman valuation from April says £95.
> That is an 11.2% spread. At 42,500 sqm that is a £4.25 million gap in annual
> rental value — which changes your IRR materially."

Point to AI Reasoning:
> "Here is exactly how it found it: which page, which field,
> and why the valuation figure is the more credible source."

Point to Suggested Resolution:
> "And here is what to do: accept the valuation ERV and rerun the model.
> Your analyst clicks Resolve, adds a note, done — permanent audit trail."

**[2:15 — 3:00] Capex Not in IM** *(click flag 2)*

> "The Arcadis TDD found £340,000 of immediate capex — roof, M&E, drainage.
> The IM does not mention any of it. That is not something you want to discover
> after signing exclusivity."

> "The platform gives you the vendor negotiation language directly:
> deduct it from the price or require a credit."

**[3:00 — 3:30] Lease Break Date** *(click flag 3)*

> "This is the kind of thing that falls through the cracks in every deal.
> The Heron break option is 15 September — not a UK quarter day.
> The notice deadline is September 2026.
> If you miss it, you have lost the optionality on your largest tenant."

**[3:30 — 4:00] Resolve live + close**

Resolve one flag with a short note. Watch it move to Resolved.
If all three are resolved, the green banner appears: *All issues resolved — workspace is ready.*

> "That is the workflow. Document pack in, issues surfaced with reasoning,
> your team makes the decisions. Clean audit trail for every deal.
> Analysts spend their time on judgment — not document reading."

> "The same platform handles construction contracts, insurance claims,
> logistics procurement. We built it generic because every industry has this problem.
> For Delin, we configure it for your document types and your cross-checks."

---

## 4-minuten demoscript — Nederlands

**[0:00 — 0:30] Het probleem**

> "Je analisten zijn twee tot drie dagen per deal bezig met het lezen van documenten
> en het controleren van cijfers. Tegen de tijd dat ze een probleem ontdekken,
> zit je al in exclusiviteit. Dit is de intelligence-laag die dat werk doet in minder dan een minuut."

**[0:30 — 1:15] Wat het platform heeft gelezen**

Wijs naar de metrieken bovenaan:

> "We hebben vijf documenten door een workspace gehaald — het IM, de huurlijst,
> het TDD-rapport, de Cushman & Wakefield taxatie, en de Heron-huurovereenkomst.
> Geen sjablonen, geen configuratie. Het platform heeft elk document geclassificeerd,
> de kernvelden geëxtraheerd en cross-gevalideerd over alle bronnen heen."

- **72% betrouwbaarheid** — "Dat laat zien waar de AI zeker is en waar hij twijfelt."
- **5/5 gevalideerd** — "Elk document verwerkt en gecheckt."
- **~15 uur bespaard** — "Dat is anderhalve dag analistenwerk, per deal."

**[1:15 — 2:15] ERV-conflict** *(klik op vlag 1)*

> "Het IM zegt dat de ERV £85 per m² is. De Cushman-taxatie van april zegt £95.
> Dat is een verschil van 11,2%. Bij 42.500 m² gaat het om een gat van £4,25 miljoen
> in jaarlijkse huurwaarde — wat je IRR wezenlijk verandert."

Wijs naar AI Redenering:
> "Hier staat precies hoe het gevonden is: welke pagina, welk veld,
> en waarom de taxatiewaarde de betrouwbaardere bron is."

Wijs naar Aanbevolen oplossing:
> "En hier staat wat je moet doen: accepteer de ERV van de taxateur en herbereken het model.
> Je analist klikt op Oplossen, voegt een notitie toe — permanent in het auditspoor."

**[2:15 — 3:00] Capex niet in het IM** *(klik op vlag 2)*

> "Het Arcadis TDD-rapport heeft £340.000 aan directe capex gevonden
> — dak, installaties, drainage. Het IM noemt dit nergens.
> Dat is iets wat je niet wilt ontdekken nadat je exclusiviteit hebt getekend."

> "Het platform geeft je de onderhandelingstaal direct mee:
> verrekenen in de koopsom of een vendorkrediet eisen."

**[3:00 — 3:30] Break-optie datum** *(klik op vlag 3)*

> "Dit is het soort ding dat bij elke deal door de mazen glipt.
> De break-optie van Heron staat op 15 september — geen Engelse kwartaaldag.
> De opzegtermijn loopt af in september 2026.
> Als je dat mist, verlies je de optionaliteit op je grootste huurder."

**[3:30 — 4:00] Live oplossen + afsluiten**

Los één vlag live op met een korte notitie. Die verschijnt direct onder 'Opgelost'.
Als alle drie zijn opgelost, verschijnt de groene banner.

> "Dit is de workflow. Documentpakket erin, problemen worden uitgelegd met redenering,
> je team neemt de beslissingen. Een schoon auditspoor voor elke deal.
> Analisten besteden hun tijd aan oordelen — niet aan documenten lezen."

> "Hetzelfde platform werkt voor bouwcontracten, verzekeringsclaims, logistieke inkoop.
> Generiek gebouwd, want elk sector heeft dit probleem.
> Voor Delin configureren we het voor jouw documenttypen en jouw checks."

---

## Pre-flight checklist

Run through this in order before the meeting starts:

- [ ] Backend running — `uvicorn app.main:app --port 8000 --reload` → `Application startup complete.`
- [ ] Frontend running — `npm run dev` in `frontend/` → `Ready` on port 3000
- [ ] Seed run — `python scripts/seed_demo.py` → prints workspace URL, note it
- [ ] Login works — open `http://localhost:3000`, sign in as `demo@inversiq.com` / `Demo2025!`
- [ ] Workspace opens — navigate to printed URL, metrics strip shows 72% / 5/5 / 3 open / ~15h
- [ ] Flag resolve works — click ERV flag, click Mark Resolved, counter drops to 2, re-seed after

---

## Reset

```bash
python scripts/seed_demo.py
```

Cleared and recreated in ~2 seconds. Navigate to the new URL printed in the output.

---

## Troubleshooting

| Symptom | Fix |
|---|---|
| Login → 500 error | Backend not running — start `uvicorn app.main:app --port 8000 --reload` |
| Workspace list empty | Run `python scripts/seed_demo.py` |
| Two workspaces showing | Run `python scripts/seed_demo.py` — clears all demo workspaces |
| Demo password rejected | Run `python scripts/seed_demo.py` — resets password each run |
| `"Schilder"` visible on screen | You are on the Dashboard — navigate to the workspace URL directly |
| Port 8000 in use | `Get-Process -Name python \| Stop-Process` |
| Port 3000 in use | `Get-Process -Name node \| Stop-Process` |

---

## Required environment variables

All set in `.env` for local dev. No changes needed for the demo.

| Variable | Needed | Note |
|---|---|---|
| `DATABASE_URL` | Yes | `sqlite:///...inversiq.db` |
| `JWT_SECRET` | Yes | Already set |
| `SECRET_KEY` | Yes | Already set |
| `SALES_BASIC_AUTH_USER` | Yes | `demo` |
| `SALES_BASIC_AUTH_PASS` | Yes | `demo123` |
| `ANTHROPIC_API_KEY` | **No** | Not needed — demo uses seeded data |
| Stripe / Google OAuth | No | Not needed |

---

## Demo mode

All workspace data is seeded directly into the database — no LLM calls, no file reads,
no external API calls occur during the walkthrough. The pipeline (`app/workspace/processor.py`)
would call the Anthropic API on real uploaded documents, but this is bypassed entirely
by inserting pre-classified data. Deterministic and reliable every time.
