# New Engineer Onboarding Guide

_Inversiq — June 2026_

Welcome to Inversiq. This guide gets you from zero to productive in the first week. It is written for engineers who have not seen the codebase before and need accurate context fast.

---

## The Business in Two Paragraphs

Inversiq automates the gap between a customer submitting an inquiry and receiving a priced estimate. A construction operator gets 40 lead requests per week. Without Inversiq: manual site visits, inconsistent pricing, missed follow-ups, no systematic feedback on whether prices were right.

With Inversiq: the customer fills in an intake form, uploads photos, and receives a branded HTML estimate within seconds. The system screens photos for quality, sends usable ones to OpenAI Vision to extract area and condition signals, runs them through a JSON-rules pricing engine, and decides automatically whether to deliver the estimate or route it to human review. After the deal closes, the operator records the outcome, and the intelligence layer uses that feedback to detect systematic pricing errors over time.

---

## Day 1: Get the Dev Environment Running

### Prerequisites

- Docker Desktop
- Python 3.11 (for running linters/tests outside Docker)
- Node.js 18+ (for the Next.js frontend)
- An `.env` file (get this from the team — it contains `OPENAI_API_KEY`, Stripe keys, etc.)

### Step 1: Clone and configure

```bash
git clone <repo-url>
cd Inversiq
cp .env.example .env   # fill in values from the team's secrets store
```

### Step 2: Start the backend stack

```bash
docker-compose up --build
```

This starts:
- `app` — FastAPI backend on port 8080
- `postgres` — PostgreSQL 15
- `redis` — Redis 7

On first start, `SQLALCHEMY_CREATE_ALL_AT_STARTUP=true` (the default) will create all database tables automatically.

### Step 3: Verify the backend

```bash
curl http://localhost:8080/health
# → {"status": "ok", "service": "inversiq"}
```

```bash
curl http://localhost:8080/metrics
# → Prometheus text format
```

### Step 4: Start the frontend (optional for most backend work)

```bash
cd frontend
npm install
npm run dev
# Frontend on http://localhost:3000
```

The frontend proxies all API calls through `frontend/src/app/api/backend/[...path]/route.ts` to the backend at port 8080.

### Step 5: Start the observability stack (optional)

```bash
docker-compose -f docker-compose.observability.yml up
# Prometheus at :9090, Grafana at :3001
```

### Working Without AWS

If you don't have AWS credentials, set `USE_MOCK_STORAGE=true` in your `.env`. The mock storage backend (`app/mock_storage/`) saves files to local disk instead of S3. Never set `AWS_ACCESS_KEY_ID` in your environment — the app will refuse to start (this is intentional security policy).

---

## Week 1: Understanding the Codebase

### Day 2: Read the Core Pipeline

The entire product is `app/verticals/construction/pipeline.py`. Read it completely. It is about 400 lines and contains:

1. `_demo_vision()` — fallback when no photos are uploaded
2. `_extract_estimated_area()` — reads m² from intake payload
3. `compute_quote_for_lead()` — the full pipeline:
   - Calls `run_vision_for_lead()` → photo quality screening + OpenAI Vision
   - Calls `run_pricing_engine()` → JSON rules + tenant overrides
   - Calls `build_pricing_output()` → structure + branding
   - Calls `needs_review_from_output()` → review routing decision
   - Renders HTML → stores to S3
   - Returns `{estimate_json, estimate_html_key, needs_review}`

This 400 lines is the product. Everything else is infrastructure, observability, or governance around this core.

### Day 3: Read the Data Model

Read in this order:

1. `app/models/lead.py` — the `Lead` and `LeadFile` models. A lead is the central entity: a customer request from intake through estimate delivery and outcome recording.

2. `app/models/tenant.py` — the `Tenant` model. Note the `@validates("sector")` decorator that enforces valid verticals at ORM save time. Note `pricing_json` and `enabled_verticals`.

3. `app/models/pipeline_run.py` — `PipelineRun` and `PipelineStepRun`. This is what the engine writes on every execution. Note `config_hash`, `overall_confidence_score`, `error_category`, and the `input_snapshot`/`output_snapshot` JSON columns.

4. `app/models/lead_feedback.py` — `LeadFeedback`. The ground truth: `outcome` (won/lost), `actual_price`, `estimated_price`. This is what feeds the intelligence layer.

5. `app/models/__init__.py` — see all 25+ models imported. Note the `proposed_change_*` family (six models for the governance workflow).

### Day 4: Read the Intelligence Layer

The intelligence layer sits above the pipeline and analyzes run history. Read in this order:

1. `app/anomaly/engine.py` + `app/anomaly/detectors.py` — five detectors that flag structural contradictions in run history

2. `app/intelligence/engine.py` + `app/intelligence/detectors.py` — five detectors that flag behavioral patterns (underpricing, overpricing, repeated fallback, etc.)

3. `app/services/trend_engine.py` — pure function: takes two metric dicts (current window vs prior), returns trend directions and severity

4. `app/health/summary.py` — aggregates run counts and intelligence signals into health status per pipeline name

5. `app/services/reasoning_engine.py` — pure function: diagnoses root causes from the combination of health, trends, and signals

6. `app/services/focus_engine.py` — pure function: produces a priority score [0, 100] and priority label

7. `app/services/proposed_changes.py` — pure function: maps diagnoses to formally structured change proposals

The key pattern: **every layer is a pure function or read-only query over DB state**. Nothing in the intelligence layer writes new data except the persistence of `ProposedChangeReviewState`.

### Day 5: Read the Next-Gen Engine

The `inversiq/engine/` package is the next-generation pipeline runner. It is more sophisticated than the imperative pipeline in `painting/pipeline.py`. Read:

1. `inversiq/engine/context.py` — `EngineContext`, `PipelineState`, `StepResult`, `ConfidenceResult`
2. `inversiq/engine/config.py` — `EngineConfig`, `StepConfig`, step definitions
3. `inversiq/engine/registry.py` — `StepRegistry`, register/get/peek operations
4. `inversiq/engine/runner.py` — the main `run_pipeline()` function

The runner handles: DB persistence of PipelineRun/PipelineStepRun, EngineEvent emission, confidence accumulation, structured logging, Prometheus metrics, error categorization, step contract validation. It is decoupled from the app layer via lazy imports.

The `ConstructionVertical.get_workflows()` in `app/verticals/construction/__init__.py` defines the step configuration that will drive this runner when the migration is complete.

---

## Key Concepts to Internalize

### Confidence Scores

Every pipeline step that produces meaningful output is expected to also produce a confidence score (0.0–1.0). The overall run confidence is `min(all_step_scores)` — the weakest link. This drives the review routing decision. A step that returns 0.2 confidence pulls the whole run down to 0.2, even if other steps were at 0.9. This is intentional and conservative.

### The Review Decision

`needs_review_from_output()` returns a list of reason codes. Empty list = auto-deliver. Non-empty = NEEDS_REVIEW. Hard blockers trigger immediately (missing/zero/negative total). Soft signals only trigger review when 2+ accumulate ("Preset B" stacking logic). This reduces false positives while maintaining safety.

### Multi-Tenancy

Every database entity carries `tenant_id`. Every query that touches tenant-specific data must scope by `tenant_id`. The `Tenant.sector` field determines which vertical handles intake and estimation. `Tenant.pricing_json` lets each operator customize their pricing rules without touching the base rule files.

### The Governance Model

The system identifies problems and proposes changes, but applies nothing without human approval. This is the `ProposedChange*` family of models and services. A proposal is generated by a pure function, persisted as `ProposedChangeReviewState`, reviewed by an operator, converted to an `ApplyIntent`, then an `ExecutionRequest`, then attempted, and the outcome stored — all with an immutable `AuditEvent` trail. This is not optional complexity — it exists because automated pricing changes have real financial consequences.

### The `aether-api` Service Name

You will see `service=aether-api` in startup logs and `aether_` prefixes on Prometheus metric names. This is the original internal API service name from before the Inversiq brand. Do not change it — it is a stable identifier used in monitoring and log queries.

---

## Understanding the Business Domain

### What a "Vertical" Is

A vertical is a trade/service category: painting, insurance, logistics, real_estate. Each vertical has:
- Its own intake form (collects relevant fields)
- Its own pricing rules (different trade = different cost structure)
- Its own vision prompt (painting vs roofing requires different photo analysis)

The construction vertical is the reference implementation. Roofing and solar have intake forms but no estimation pipeline yet.

### What a "Lead" Is

A lead is a customer inquiry. It starts as `NEW` when the intake form is submitted. After the pipeline runs, it becomes `DONE` (estimate delivered), `NEEDS_REVIEW` (flagged for human), or `FAILED` (pipeline error). The customer can then view the estimate, accept it, or reject it.

### What "Feedback" Means

After a deal closes, the operator records whether they won or lost it and at what final price. This `LeadFeedback` record is the ground truth for the intelligence layer. If you win 20 deals at prices significantly higher than the estimate, the intelligence engine will flag `LIKELY_UNDERPRICING`. This is the signal that drives the learning loop.

### Plan Codes and Entitlements

Operators subscribe at different plan tiers. Plan codes gate feature access. `SEND_QUOTE` is the critical gated action — it checks subscription status, feature availability, and monthly usage limits. Custom branding (showing the operator's company name/logo on estimates) is tier-gated via `app/services/branding.py`. The entitlement check lives in `app/billing/entitlements.py`.

---

## Common Tasks and Where to Find Them

| Task | Where to Look |
|---|---|
| Add a field to intake forms | `app/verticals/construction/templates/intake_form_nl.html` (form), `app/verticals/construction/intake_schema.json` (validation), and potentially `app/models/lead.py` if it needs a DB column |
| Change pricing logic | `app/verticals/construction/pricing_engine_us.py` and/or the JSON rule files in `app/verticals/construction/rules/` |
| Change the vision prompt | `app/verticals/construction/prompts/vision.md` |
| Change review routing thresholds | `app/verticals/construction/needs_review.py` |
| Add an intelligence signal | `app/intelligence/detectors.py` (new detector function) + `app/intelligence/engine.py` (register in `run_all()`) + `app/intelligence/types.py` (add to `SignalType`) |
| Add a new vertical | Copy `app/verticals/roofing/__init__.py` and `app/verticals/roofing/adapter.py` as a template |
| Debug a failed pipeline run | Query `/pipeline-runs?status=FAILED`, inspect `failure_step` and step-level `error_message` |
| Check what's in the operator's review queue | Query `/proposed-changes?tenant_id={id}` |
| Add an API endpoint | Create a new router file in `app/routers/`, add `app.include_router()` in `app/main.py` |
| Change email templates | `app/verticals/construction/estimate_email.py` and associated template files |
| Understand a branding decision | Check `app/services/branding.py` — branding allowed/denied logic and `app/billing/entitlements.py` |

---

## Who to Ask / What to Read

### If you're stuck on the pipeline

The pipeline is `compute_quote_for_lead()` in `app/verticals/construction/pipeline.py`. The vision step calls `run_vision_for_lead()` in `app/tasks/vision_task.py`. The pricing step calls `run_pricing_engine()` in `app/verticals/construction/pricing_engine_us.py`. These are the three most important files in the product.

### If you're stuck on the data model

`app/models/__init__.py` imports everything. For any specific model, the file name is descriptive: `app/models/lead_feedback.py` is `LeadFeedback`. Read the model file — the comments and field names are clear.

### If you're stuck on routing

`app/main.py` shows all 68 mounted routers. The router files are in `app/routers/` and are named descriptively. If a router is commented out (e.g. `# app.include_router(app_dashboard_router)`), that feature is disabled.

### If something looks weird

Check if it might be a Dutch-language comment or variable name. The first market is the Netherlands. You'll see `nl` prefixes, `schilder` (painter), `offertes` (quotes), and `tenant_id="public"` defaults in the roofing/solar adapters.

### If you find a `TODO` or `NOTE`

Take it seriously. For example, `NOTE: rules expect light/medium/heavy; "standard" will map to multiplier 1.0` in `_demo_vision()` is a real edge case that affects pricing accuracy in demo mode.

### The handbook

`docs/engineering-handbook-v2.md` has complete reference documentation for every major component, all data models, the execution lifecycle, security posture, and architectural decisions. Read it after your first week for deeper context.
