# Inversiq Engineering Handbook

_Version 1.0 — June 2026_

---

## Table of Contents

1. [Inversiq Overview](#1-inversiq-overview)
2. [Product Vision](#2-product-vision)
3. [High-Level Architecture](#3-high-level-architecture)
4. [Technology Stack](#4-technology-stack)
5. [Core Components](#5-core-components)
6. [Data Model Guide](#6-data-model-guide)
7. [Execution Lifecycle](#7-execution-lifecycle)
8. [Engineering Principles](#8-engineering-principles)
9. [Repository Guide](#9-repository-guide)
10. [Future Architecture Opportunities](#10-future-architecture-opportunities)

---

## 1. Inversiq Overview

### What Inversiq Is

Inversiq is a **decision infrastructure platform** for trade and service businesses. It enables companies in verticals like painting, roofing, and solar to fully automate the journey from customer intake to delivered estimate — replacing manual quoting, inconsistent pricing, and missed leads with a structured, observable, and continuously improving engine.

The name of the internal API service (visible in `app/main.py` startup logging and throughout the codebase) was previously called `aether-api`, which reflects the platform's origin as an AI-native estimation engine before it was productized under the Inversiq brand.

### What Problem It Solves

Trade and home services businesses share a universal bottleneck: turning inbound customer interest into a priced, delivered quote takes too long, varies too much between operators, and produces outcomes that are hard to analyze or improve. A painting contractor who receives 40 lead requests a week cannot manually visit all of them, price them consistently, and track which pricing decisions led to won or lost deals.

Inversiq automates the full intake-to-estimate workflow by:

1. Capturing structured customer data through vertical-specific intake forms
2. Analyzing customer-provided photos using computer vision
3. Running deterministic pricing rules against those visual signals
4. Deciding automatically whether an estimate can be auto-delivered or requires human review
5. Delivering a branded estimate directly to the customer
6. Capturing outcome feedback to detect pricing drift, underpricing, and rule coverage gaps
7. Surfacing intelligence signals and proposed governance changes to operators

### Core Philosophy

The platform is built around three architectural commitments that distinguish it from generic SaaS tools:

**Determinism over magic.** Every output — pricing, review routing, confidence scoring, anomaly flags, proposed changes — is produced by explicit, inspectable rules. There is no black-box model that "just decides." The reasoning at every step can be traced, audited, and challenged.

**Observability as a first-class product.** The system is instrumented not just for DevOps purposes but for business intelligence. Operators can see not only that a run failed but *why*, at what step, with what confidence score, using what pricing rules. This observability layer is the foundation for the self-improvement loop.

**Human-in-the-loop governance.** The system identifies problems and proposes changes, but nothing is applied without explicit human approval. The governance model — `ProposedChangeReviewState`, execution requests, audit events — exists because automated pricing changes in a B2B context carry real financial risk.

### Why the Platform Exists

Trade businesses are underserved by generic SaaS. CRMs help with pipeline management. Scheduling tools help with dispatch. But the core problem — turning a customer's vague request into a defensible, margin-protecting price — has no good generic solution. Inversiq is purpose-built for that gap, with the ambition of becoming the "operating system" layer that every vertical-specific trade business runs underneath.

---

## 2. Product Vision

### Workflow Engine

The immediate product is a **Workflow Engine**: a configurable pipeline that takes a lead through a sequence of steps — intake validation, vision analysis, pricing, review routing, estimate delivery — and produces a consistent, branded output every time.

The painting vertical (`app/verticals/painting/`) is the reference implementation. It is fully operational and production-grade. Roofing and Solar (`app/verticals/roofing/`, `app/verticals/solar/`) are scaffolded, demonstrating that the platform is designed for multi-vertical expansion from the start.

The workflow engine is increasingly driven by a proper engine abstraction visible in `app/verticals/painting/pipeline_engine.py`:

```python
from inversiq.engine.config import load_engine_config
from inversiq.engine.registry import StepRegistry
from inversiq.engine.runner import run_pipeline
```

This `inversiq.engine` package (separate from `app/`) represents the next-generation execution layer — a formally typed, config-driven pipeline runner that will eventually replace the current imperative pipeline in `app/verticals/painting/pipeline.py`.

### Decision Infrastructure

Above the workflow engine sits a **Decision Infrastructure layer** — a set of analytical systems that observe pipeline behavior and produce structured, human-reviewable recommendations:

- **Anomaly Engine** (`app/anomaly/`): detects structural contradictions in run outputs (e.g. a run that failed despite high confidence, or a price delta that exceeds a threshold)
- **Intelligence Engine** (`app/intelligence/`): detects persistent behavioral patterns across runs (repeated fallback usage, systematic underpricing, repeated review flags)
- **Trend Engine** (`app/services/trend_engine.py`): classifies metric directions (improving, stable, degrading) with severity classification
- **Health Layer** (`app/health/`): aggregates signals into per-pipeline and per-vertical health scores
- **Reasoning Engine** (`app/services/reasoning_engine.py`): produces root-cause diagnoses from signal combinations
- **Proposed Changes** (`app/services/proposed_changes.py`): transforms diagnostics into formally structured, human-reviewable change proposals with risk levels and rollback hints

### Intelligence Platform Direction

The trajectory in the codebase is toward a fully closed intelligence loop:

```
Run → Feedback → Anomalies → Intelligence Signals → Trend Analysis
  → Health Score → Reasoning → Proposed Changes → Human Approval
  → Execution → Audit Trail → Next Run
```

The data model already reflects this ambition. The `proposed_change_*` model family (six models, see `app/models/`) represents a complete governance workflow: proposal → review → approval intent → execution request → execution attempt → execution outcome. The full audit trail (`ProposedChangeAuditEvent`) ensures every system-suggested change has a permanent, inspectable record.

### Future Evolution

The platform is evolving from a **vertical-specific automation tool** toward a **horizontal decision infrastructure** that any operator-facing business can configure. The `inversiq.engine` abstraction (referenced in `pipeline_engine.py`) and the vertical registry system point toward a future where new verticals are added through configuration and step registration, not code changes.

---

## 3. High-Level Architecture

### System Overview

```
┌─────────────────────────────────────────────────────────────────┐
│                          CLIENTS                                │
│  ┌──────────────────┐  ┌───────────────┐  ┌─────────────────┐  │
│  │  Customer Intake │  │ Operator App  │  │  Ops Dashboard  │  │
│  │  (public forms)  │  │ (Next.js SPA) │  │  (Jinja2 HTML)  │  │
│  └────────┬─────────┘  └───────┬───────┘  └────────┬────────┘  │
└───────────┼────────────────────┼───────────────────┼───────────┘
            │                    │                   │
            ▼                    ▼                   ▼
┌─────────────────────────────────────────────────────────────────┐
│                     FastAPI Backend (app/)                       │
│                                                                 │
│  ┌──────────────┐  ┌────────────────┐  ┌───────────────────┐   │
│  │ Public Intake│  │ Auth & Billing  │  │  Ops / Analytics  │   │
│  │   Routers    │  │    Routers      │  │    Routers        │   │
│  └──────┬───────┘  └────────────────┘  └────────┬──────────┘   │
│         │                                        │              │
│         ▼                                        ▼              │
│  ┌──────────────────────────────────────────────────────────┐   │
│  │                  Pipeline Engine                          │   │
│  │  Vision Stage → Pricing Stage → Output Builder           │   │
│  │            → Needs Review Decision                        │   │
│  └─────────────────────────┬────────────────────────────────┘   │
│                            │                                    │
│  ┌──────────────┐  ┌───────▼───────┐  ┌──────────────────────┐ │
│  │ Intelligence │  │  Anomaly Eng  │  │  Trend / Health /    │ │
│  │   Engine     │  │               │  │  Reasoning / Focus   │ │
│  └──────────────┘  └───────────────┘  └──────────────────────┘ │
│                                                                 │
│  ┌──────────────────────────────────────────────────────────┐   │
│  │          Proposed Change Governance Layer                 │   │
│  │  Proposals → Review → Approval → Execution → Audit       │   │
│  └──────────────────────────────────────────────────────────┘   │
└────────────────────────────┬────────────────────────────────────┘
                             │
          ┌──────────────────┼──────────────────┐
          ▼                  ▼                  ▼
    ┌───────────┐     ┌───────────┐      ┌──────────┐
    │ PostgreSQL│     │   Redis   │      │  AWS S3  │
    │ (primary) │     │(cache/job)│      │(storage) │
    └───────────┘     └───────────┘      └──────────┘
```

### Major Services

| Service | Entry Point | Purpose |
|---|---|---|
| FastAPI App | `app/main.py` | HTTP API, routing, middleware |
| Pipeline Engine | `app/verticals/painting/pipeline.py` | Per-lead estimation pipeline |
| Vision Service | `app/services/vision/` | OpenAI vision API integration |
| Pricing Engine | `app/verticals/painting/pricing_engine_us.py` | JSON-rules-based pricing |
| Anomaly Engine | `app/anomaly/engine.py` | Structural contradiction detection |
| Intelligence Engine | `app/intelligence/engine.py` | Behavioral pattern detection |
| Trend Engine | `app/services/trend_engine.py` | Metric direction classification |
| Health Layer | `app/health/summary.py` | Per-pipeline/vertical health scoring |
| Reasoning Engine | `app/services/reasoning_engine.py` | Root-cause diagnosis |
| Proposed Changes | `app/services/proposed_changes.py` | Governance change proposals |
| Outreach Module | `app/modules/outreach/` | Email follow-up and reply handling |
| Background Jobs | `app/jobs/runner.py` | In-process task runner |
| Observability | `app/observability/metrics.py` | Prometheus metrics endpoint |

### Data Flow

**Intake path (synchronous):**
```
POST /intake → Lead created → Pipeline triggered →
Vision (OpenAI) → Pricing (JSON rules) → Output builder →
Needs-review decision → HTML stored (S3) → Quote delivered
```

**Analytics path (read-only, derived from run history):**
```
PipelineRun + PipelineStepRun + LeadFeedback →
Metrics aggregation → Trend engine → Health summary →
Intelligence signals → Anomaly detection → Reasoning →
Proposed changes → Human review queue
```

**Governance path (human-gated write):**
```
Proposed change → Operator approval → ProposedChangeApplyIntent →
ProposedChangeExecutionRequest → Execution attempt → Outcome → Audit event
```

### Infrastructure Overview

The production stack runs on Docker with:
- **Gunicorn + UvicornWorker** as the ASGI server (`docker-compose.yml`)
- **PostgreSQL 15** as the primary database
- **Redis 7** for background task queuing
- **AWS S3** for file storage (HTML estimates, uploaded photos)
- **Prometheus** for metrics collection (`/metrics` endpoint)
- A separate `docker-compose.observability.yml` for Grafana/Prometheus stack

The codebase contains a safety guard in `app/main.py` (`assert_no_static_aws_keys_in_env()`) that prevents startup if static AWS credentials are present in environment variables — IAM roles or AWS profiles are required.

---

## 4. Technology Stack

### Python 3.11

**What:** Primary backend language across the entire platform.

**Why:** FastAPI's async model and type annotation system pair cleanly with Python 3.11's performance improvements. The entire domain logic — pipeline steps, pricing rules, analytics engines — is pure Python, making it easily testable and portable.

**How:** The `app/` package is the main application. The `inversiq/` package (referenced in `pipeline_engine.py`) is the emerging engine abstraction layer, intended to be independently versioned and importable.

### FastAPI

**What:** ASGI web framework powering the HTTP layer.

**Why:** FastAPI provides automatic OpenAPI schema generation, native async support, and Pydantic-based request validation without boilerplate. The router system allows clean separation of concerns — each functional domain (intake, quotes, pipeline runs, proposed changes, billing) has its own router file.

**How:** `app/main.py` mounts roughly 60 routers. The entry point is `app.main:app`. Both Jinja2-rendered HTML responses (for the operator app) and JSON API responses (for the Next.js frontend) coexist in the same FastAPI instance. Vertical-specific routers (`paintly_app_router`, `paintly_htmx_router`, `paintly_integrations_router`) are registered alongside core platform routers.

**Middleware stack** (in `app/main.py`):
- `RequestIdMiddleware` — attaches a request ID to every request for log correlation
- `SlowAPIMiddleware` — rate limiting via `slowapi`
- `BasicAuthMiddleware` — guards `/sales` and `/api` prefixes
- `CORSMiddleware` — configured from `settings.allowed_origins_list`
- HTTP logging middleware — structured request/response logging with latency

### PostgreSQL

**What:** Primary relational database. Development can fall back to SQLite via `DATABASE_URL` env.

**Why:** The data model has meaningful relational structure (leads → lead files, pipeline runs → step runs, proposed changes → audit events) that benefits from referential integrity. PostgreSQL's JSON column support is used extensively (e.g. `Tenant.pricing_json`, `PipelineStepRun.input_snapshot`, `PipelineStepRun.output_snapshot`).

**How:** Connection is managed via `app/db/session.py`. Schema creation happens at startup via `Base.metadata.create_all(bind=engine)` when `SQLALCHEMY_CREATE_ALL_AT_STARTUP=true` (default for local dev). Production deployments should use Alembic migrations.

### SQLAlchemy

**What:** ORM layer for all database access. Uses the modern `Mapped`/`mapped_column` declarative style throughout.

**Why:** Type-safe ORM with relationship management. The codebase uses `none_as_null=True` on JSON columns (see `PipelineStepRun`) so Python `None` maps to SQL `NULL` rather than the string `"null"` — a subtle correctness detail that signals attention to data semantics.

**How:** All models inherit from `app.db.Base`. The models package (`app/models/`) is imported at startup in `main.py` (`from app import models  # noqa: F401`) to ensure all model classes are registered with SQLAlchemy's metadata before `create_all` runs.

### Celery

**What:** Distributed task queue for background processing.

**Why:** Vision analysis (calling OpenAI) and email delivery are I/O-bound operations that should not block HTTP request handlers. Celery enables async processing with Redis as the broker.

**How:** `app/celery_app.py` defines the Celery application. `app/celery_tasks.py` defines the tasks. The vision task pipeline runs through `app/tasks/vision_task.py` → `app/tasks/vision.py`. There is also a lightweight in-process background worker (`app/jobs/runner.py` / `start_worker()`) for simpler job scheduling, started at app startup.

### Redis

**What:** In-memory data store used as Celery broker and general cache.

**Why:** Celery requires a broker. Redis provides low-latency task queuing and can serve as a response cache for expensive analytics computations. `REDIS_URL` is injected via environment variable.

**How:** Connection is referenced in `docker-compose.yml` as `redis://redis:6379/0`. The `app/config/cache_config.py` manages cache settings.

### AWS S3

**What:** Object storage for generated HTML estimates and customer-uploaded photos.

**Why:** Storing binary files (images, rendered HTML documents) in the database is an anti-pattern. S3 provides durable, scalable storage with presigned URL support for secure client-side uploads.

**How:** The storage layer is abstracted behind `app/services/storage.py` (`get_storage()`), which returns either an `S3Storage` instance or a local filesystem mock (`app/mock_storage/`). Presigned uploads flow through `app/api/routes/presign.py`. S3 keys follow the pattern `leads/{lead_id}/estimates/{date}/{filename}` (visible in `app/verticals/painting/pipeline.py`).

The `app/aws/s3_ops.py` and `app/aws/s3_errors.py` modules handle S3 operations. A startup guard (`assert_no_static_aws_keys_in_env`) forces IAM role or AWS profile usage — no static key credentials in environment.

### Prometheus

**What:** Metrics collection and exposition.

**Why:** The platform needs operational visibility at the infrastructure level (request counts, latency, upload sizes) alongside business-level visibility (pipeline success rates, confidence scores). Prometheus is the standard for both.

**How:** `app/observability/metrics.py` defines four metrics:
- `aether_presign_total` — presign request counter
- `aether_verify_total` — upload verify counter
- `aether_upload_size_bytes` — upload size histogram
- `aether_api_latency_seconds` — per-route latency histogram

The `/metrics` endpoint is exposed at `GET /metrics` and scraped by Prometheus. `docker-compose.observability.yml` provisions the Prometheus + Grafana stack.

### Grafana

**What:** Dashboard and visualization layer over Prometheus metrics.

**Why:** Prometheus stores time series; Grafana makes them readable. Operators and developers need dashboards that show pipeline health, error rates, and latency trends without writing PromQL.

**How:** Provisioned via `docker-compose.observability.yml`. Not yet deeply configured in the codebase — this is an infrastructure concern sitting outside the application.

### Docker

**What:** Container runtime for all services.

**Why:** Reproducible environments across development, staging, and production. The Dockerfile defines the application image; `docker-compose.yml` orchestrates the full local stack.

**How:** The production command is `gunicorn -k uvicorn.workers.UvicornWorker app.main:app --bind 0.0.0.0:8080`. Three Docker Compose files exist:
- `docker-compose.yml` — core stack (app, postgres, redis)
- `docker-compose.dev.yml` — local development overrides
- `docker-compose.observability.yml` — Prometheus + Grafana
- `docker-compose.redis.yml` — Redis-only for development

### OpenAI API

**What:** Vision inference provider for analyzing customer-uploaded photos.

**Why:** The platform's core value proposition — automated estimation from photos — requires a multimodal model. OpenAI's GPT-4 Vision (or equivalent) is used to extract area estimates, surface conditions, damage signals, and preparation requirements from photos.

**How:** `app/services/vision/openai_provider.py` implements the primary provider. `app/services/vision/fallback_provider.py` implements a fallback path when the primary provider fails. `app/services/vision/aggregate.py` combines per-image predictions into a lead-level aggregate. The prompt lives in `app/verticals/painting/prompts/vision.md`.

### PyTorch / OpenCV / timm

**What:** Local ML stack for photo quality scoring.

**Why:** Before sending photos to OpenAI (which costs money per call), the platform can screen out low-quality or unusable photos using a lightweight local classifier. This avoids wasting vision API budget on blurry, dark, or irrelevant images.

**How:** `app/ml/photo_qualtity/` contains training code (`train.py`), evaluation (`eval.py`), and export (`export.py`). The inference layer is `app/services/photo_quality/inference.py`. The model is trained on a labeled dataset in `app/ml/photo_qualtity/data/`.

### Stripe

**What:** Payment and subscription billing infrastructure.

**Why:** Inversiq is a B2B SaaS product. Tenant plans (`plan_code` on the `Tenant` model) gate feature access — branding customization, for example, is only available on higher tiers (see `app/services/branding.py`).

**How:** `app/services/stripe_service.py` handles subscription management. `app/routers/stripe_webhook.py` handles Stripe webhooks. `app/billing/entitlements.py` and `app/billing/features.py` translate plan codes into feature flags.

### structlog / Sentry

**What:** Structured logging and error tracking.

**Why:** Traditional string logging is unqueryable. structlog produces JSON log lines with key-value fields that can be ingested by log aggregation systems (Datadog, CloudWatch, etc.). Sentry captures unhandled exceptions with full context.

**How:** `app/core/logging_config.py` configures structlog. Every request is logged with `request_id`, `tenant_id`, `ip`, `endpoint`, `method`, `status_code`, and `latency_ms`. The logger is bound at the request level in the `logging_middleware` in `app/main.py`.

### Next.js (Frontend)

**What:** The operator-facing single-page application lives in `frontend/`.

**Why:** The operator app (leads management, settings, billing, review inbox, analytics) needs a modern, interactive UI. Next.js provides server-side rendering, file-based routing, and a strong TypeScript ecosystem.

**How:** The frontend communicates with the backend via `frontend/src/app/api/backend/[...path]/route.ts` — a catch-all API proxy that forwards requests to the FastAPI backend. Auth is handled via `frontend/src/app/api/auth/register/route.ts`. The frontend is not the only UI surface — the operator application also has Jinja2-rendered HTML views (the painting vertical's `templates/app/` directory) served directly by FastAPI using HTMX for partial page updates.

### i18n (Dutch / English)

**What:** Internationalization service for customer-facing content.

**Why:** The platform's first market is the Netherlands (the painting vertical manifest sets `locale: nl-NL`). Customer intake forms and estimate emails must render in the customer's language.

**How:** `app/i18n/` contains `en.json` and `nl.json` translation files and a `service.py` that integrates with Jinja2 templates. Language is detected from a cookie or `?lang=xx` query parameter and persisted as a cookie by the logging middleware in `main.py`.

---

## 5. Core Components

### 5.1 Execution Engine (Pipeline)

**Purpose:** Transform a lead with intake data and optional photos into a structured estimate.

**Responsibilities:**
- Orchestrate the sequence: vision → pricing → output builder → review decision → HTML render → storage
- Capture per-step inputs and outputs as JSON snapshots for post-mortem debugging
- Assign confidence scores per step and compute an overall confidence as the weakest-link minimum
- Decide whether the output can be auto-delivered or requires human review

**Inputs:** `Lead` database record + `Session` (for tenant pricing config lookup)

**Outputs:**
```python
{
    "estimate_json": dict,        # Full structured estimate
    "estimate_html_key": str,     # S3 key of the rendered HTML
    "needs_review": bool,         # Whether human review is required
}
```

**Key files:**
- `app/verticals/painting/pipeline.py` — current imperative pipeline
- `app/verticals/painting/pipeline_engine.py` — next-generation engine-backed pipeline
- `app/models/pipeline_run.py` — `PipelineRun` and `PipelineStepRun` models

**Design note:** The pipeline deliberately uses a "weakest-link" confidence model: the overall run confidence is the minimum of all step confidence scores. A single step that produces low confidence drags down the entire run — this is intentional. The system is conservative by design.

### 5.2 Vision Layer

**Purpose:** Extract structured painting signals from customer-uploaded photos.

**Responsibilities:**
- Score each photo for usability (local ML model)
- Send usable photos to OpenAI for structured signal extraction
- Aggregate per-image predictions into a lead-level signal set
- Report confidence, coverage, uncertainty, and damage signals

**Inputs:** Lead ID + list of S3 file keys

**Outputs:** Structured dict with `area`, `scope`, `modifiers`, `damages`, `confidence`, `uncertainty_score`, `coverage_score`, `needs_review`, `review_reasons`

**Key files:**
- `app/tasks/vision_task.py` — entry point called from pipeline
- `app/services/vision/openai_provider.py` — primary vision inference
- `app/services/vision/fallback_provider.py` — fallback path
- `app/services/vision/aggregate.py` — per-image to lead-level aggregation
- `app/verticals/painting/vision_aggregate_us.py` — vertical-specific aggregation
- `app/services/photo_quality/inference.py` — local photo usability scorer
- `app/verticals/painting/prompts/vision.md` — the vision prompt

**Dependencies:** OpenAI API, AWS S3 (for image retrieval), PyTorch (photo quality model)

### 5.3 Pricing Engine

**Purpose:** Compute a structured, margin-protecting estimate from vision signals and tenant pricing configuration.

**Responsibilities:**
- Load JSON pricing rules (market-specific: EU or US)
- Apply area, scope, complexity, and prep level multipliers
- Apply tenant-level pricing overrides (stored in `Tenant.pricing_json`)
- Produce line-item-level output with subtotals, VAT, and grand total

**Inputs:** `Lead`, vision output dict, `tenant_pricing` dict (from `Tenant.pricing_json`)

**Outputs:** Structured pricing dict with line items, totals, assumptions, and timeline estimate

**Key files:**
- `app/verticals/painting/pricing_engine_us.py` — main pricing logic
- `app/verticals/painting/rules/paintly_price_rules_eu.json` — EU rule set
- `app/services/pricing_engine.py` — generic pricing engine (older, intake-based)
- `app/verticals/painting/pricing_output_builder.py` — constructs final output structure
- `app/services/tenant_pricing.py` — tenant-level pricing configuration service

**Design note:** The pricing engine supports both US and EU rule sets, selected based on `lead.market` or `lead.tenant.locale`. The `_pick_rules_from_lead()` function in `pricing_engine_us.py` handles this selection. Tenant pricing overrides are layered on top of base rules — the tenant's `pricing_json` can adjust any rule parameter without modifying the base rule file.

### 5.4 Review Decision Engine

**Purpose:** Determine whether an estimate can be automatically delivered to the customer or must be held for human review.

**Responsibilities:**
- Apply hard blockers (missing total, zero or negative total)
- Apply soft signals (low confidence, extreme area values, photo usability issues, high uncertainty, high-impact damage detection)
- Implement a stacking logic: auto-deliver unless 2+ soft signals accumulate
- Return an explicit list of reasons for any review decision (for operator visibility)

**Key file:** `app/verticals/painting/needs_review.py`

**Design note:** The review decision implements a "Preset B" strategy: hard blockers immediately require review; soft signals are only escalating when they stack (2+). This reduces false positives while maintaining safety. The function returns an explicit list of reason codes (e.g. `["risk:uncertainty_high", "risk:coverage_low"]`) — never just `True/False`. Operator-facing UIs can display these reasons directly.

### 5.5 Anomaly Engine

**Purpose:** Detect structural contradictions in completed pipeline runs.

**Responsibilities:**
- `PRICE_DELTA_LARGE`: flag runs where the estimate price deviates >50% from baseline
- `FAILED_HIGH_CONFIDENCE`: flag runs that failed despite reporting high confidence (logical contradiction)
- `MISSING_STEP_OUTPUT`: flag steps that completed successfully but produced no output snapshot
- `CONFIDENCE_ABSENT_ON_COMPLETION`: flag completed runs with no confidence score (observability gap)
- `REPEATED_FAILURE`: flag tenants experiencing repeated run failures within a rolling 24-hour window

**Key files:**
- `app/anomaly/engine.py` — orchestrator (`run_all()`)
- `app/anomaly/detectors.py` — individual detector functions
- `app/anomaly/types.py` — `Anomaly` and `AnomalyType` types

**Design note:** All anomaly thresholds are caller-supplied (not hardcoded in detectors). The `run_all()` function accepts `price_delta_threshold`, `confidence_threshold`, etc. as parameters. This allows the ops dashboard to expose threshold tuning without code changes.

### 5.6 Intelligence Engine

**Purpose:** Detect persistent behavioral patterns across runs that indicate systemic issues rather than one-off failures.

**Responsibilities:**
- `LIKELY_UNDERPRICING`: detect tenants where won deals have actual prices consistently below estimates
- `LIKELY_OVERPRICING`: detect tenants with persistently high loss rates suggesting systematic overpricing
- `REPEATED_LOW_CONFIDENCE`: flag pipeline runs that persistently produce low-confidence outputs
- `REPEATED_FALLBACK`: flag pipelines that repeatedly fall back to the fallback vision provider
- `REPEATED_REVIEW_FLAG`: flag pipelines that consistently route to human review (suggesting calibration issues)

**Key files:**
- `app/intelligence/engine.py` — orchestrator (`run_all()`)
- `app/intelligence/detectors.py` — individual signal detectors
- `app/intelligence/types.py` — `RuleSignal`, `SignalType`, `Severity`

**Dependencies:** `LeadFeedback` (for pricing signals), `PipelineRun`/`PipelineStepRun` (for operational signals)

### 5.7 Trend Engine

**Purpose:** Classify metric direction (improving / stable / degrading) with severity, comparing a current window against a prior window.

**Responsibilities:**
- Classify each metric (success_rate, failed_rate, review_rate, avg_confidence, fallback_rate, etc.)
- Apply semantic direction: some metrics are "up is good" (success_rate, avg_confidence), others "down is good" (failed_rate, review_rate)
- Apply absolute and relative delta thresholds to distinguish stable from genuinely changing
- Produce an aggregate scope-level direction

**Key file:** `app/services/trend_engine.py`

**Design note:** The trend engine is purely functional — `compute_scope_trend(current_metrics, previous_metrics)` takes two metric dicts and returns classified trend objects. No DB access, no state. This makes it trivially testable and composable.

### 5.8 Health Layer

**Purpose:** Aggregate anomaly signals and intelligence signals into a single per-pipeline and per-vertical health status.

**Responsibilities:**
- Classify each pipeline as `healthy`, `watch`, or `unhealthy` based on failed rate, review rate, and low confidence rate thresholds
- Incorporate intelligence signals (HIGH severity signals push pipelines toward `unhealthy`)
- Produce a `top_recommendation` per pipeline

**Key files:**
- `app/health/summary.py` — main aggregation logic
- `app/health/types.py` — `PipelineHealthSummary`, `VerticalHealthSummary`, threshold constants

### 5.9 Reasoning Engine

**Purpose:** Produce human-readable root-cause diagnoses from the combination of health status, metric trends, and intelligence signal counts.

**Responsibilities:**
- Run seven explicit diagnostic rules (no ML)
- Rank candidates by evidence weight
- Deduplicate recommendations across candidates
- Return structured reasoning with `category`, `root_cause`, `confidence`, `evidence`, and `recommendations`

**Key file:** `app/services/reasoning_engine.py`

**Design note:** Every rule is a named Python function with a clear decision condition. The rules are listed in `_RULES` and are ordered and explicit. Adding a new failure mode means adding a new rule function — not retraining a model. This is a deliberate architectural choice for auditability.

### 5.10 Proposed Change Governance Layer

**Purpose:** Transform system-generated diagnostics into formally structured, human-reviewable change proposals with full lifecycle tracking.

**Responsibilities:**
- Map reasoning categories to change types (e.g. `confidence_threshold_tuning` → `threshold_adjustment`)
- Assign risk levels and approval types (operator confirmation vs. senior review)
- Generate stable, deterministic change IDs so the same proposal for the same scope is always the same change
- Attach preconditions, rollback hints, and evidence lists to every proposal
- Persist proposal review state (`ProposedChangeReviewState`)
- Track the full execution lifecycle: intent → request → attempt → outcome
- Maintain a complete audit trail (`ProposedChangeAuditEvent`)

**Key files:**
- `app/services/proposed_changes.py` — proposal generation (pure function)
- `app/models/proposed_change_review_state.py` — persisted review state
- `app/models/proposed_change_apply_intent.py` — operator approval intent
- `app/models/proposed_change_execution_request.py` — execution request
- `app/models/proposed_change_execution_attempt.py` — individual attempt
- `app/models/proposed_change_execution_outcome.py` — final outcome
- `app/models/proposed_change_audit_event.py` — audit trail
- Routers: `app/routers/proposed_changes.py` through `app/routers/proposed_change_execution_attempts.py`

**Design note:** The proposal generation service is a **pure function**. It takes suggestions and signals and returns proposals — no DB access, no side effects. Persistence is the caller's responsibility. This separates reasoning from state management and allows the same logic to be used in simulation mode (`/simulation_preview`).

### 5.11 Outreach Module

**Purpose:** Manage automated follow-up communication with leads after estimate delivery.

**Responsibilities:**
- Suggest outbound follow-up messages for leads with no response
- Track message state (sent, replied, bounced)
- Classify incoming replies (interested, not interested, already hired, etc.)
- Sync Gmail replies via OAuth integration

**Key files:**
- `app/modules/outreach/` — full module with models, repositories, services
- `app/modules/outreach/services/gmail_provider.py` — Gmail OAuth integration
- `app/modules/outreach/services/reply_classifier.py` — reply intent classification

### 5.12 Focus Engine

**Purpose:** Produce a prioritized attention queue for operators, ranking pipelines by urgency based on health, trend, and signal severity.

**Key file:** `app/services/focus_engine.py`

**Scoring formula:** `score = clamp(health_base + trend_modifier + signal_bonus, 0, 100)`
- Health base: `unhealthy=60`, `watch=30`, `healthy=5`
- Trend modifier: up to `+30` for high-severity degrading metrics
- Signal bonus: up to `+20` capped, `+10` per HIGH signal, `+5` per MEDIUM
- Priority tiers: `critical ≥ 75`, `high ≥ 50`, `medium ≥ 25`, `low < 25`

---

## 6. Data Model Guide

### Lead

**File:** `app/models/lead.py`

**Purpose:** The central entity. Represents a single customer request from the moment of intake through estimate delivery and outcome recording.

**Key fields:**
| Field | Purpose |
|---|---|
| `id` | UUID hex string primary key |
| `tenant_id` | Multi-tenant scope |
| `vertical` | Which vertical processed this lead (e.g. `"painting"`) |
| `status` | Lifecycle stage: `NEW` → `PROCESSING` → `DONE` / `FAILED` / `NEEDS_REVIEW` |
| `intake_payload` | Raw JSON string of the customer's intake form submission |
| `estimate_json` | Raw JSON string of the computed estimate |
| `estimate_html_key` | S3 key of the rendered HTML estimate file |
| `estimate_overrides_json` | Operator-applied manual overrides |
| `final_price` | The final agreed price (set after acceptance or override) |
| `public_token` | Unique token used in the customer-facing estimate URL |
| `sent_at`, `viewed_at`, `accepted_at` | Quote lifecycle timestamps |
| `reject_reason` | Why the customer declined (if captured) |

**Relationships:** `files: List[LeadFile]` — the uploaded photos

**Lifecycle:** `NEW` (created on intake) → pipeline processes → `DONE` (estimate generated) or `NEEDS_REVIEW` (flagged) or `FAILED` (pipeline error). After delivery: `sent_at` set → customer views → `accepted_at` or rejection captured.

### LeadFile

**File:** `app/models/lead.py`

**Purpose:** Represents a single uploaded file (photo) attached to a lead.

**Key fields:** `s3_key` (canonical storage path), `size_bytes`, `content_type`

**Lifecycle:** Created when a customer completes a file upload (after the presigned URL workflow completes). Consumed by the vision layer during pipeline execution.

### Tenant

**File:** `app/models/tenant.py`

**Purpose:** A business customer of Inversiq. Each tenant has isolated data, their own pricing configuration, and access to one or more verticals.

**Key fields:**
| Field | Purpose |
|---|---|
| `id` | String primary key |
| `sector` | The vertical this tenant operates in (validated against vertical registry) |
| `enabled_verticals` | JSON list of vertical IDs the tenant has access to |
| `pricing_json` | Tenant-specific pricing rule overrides |
| `plan_code` | Stripe subscription plan (gates feature access) |
| `stripe_customer_id`, `stripe_subscription_id` | Billing references |
| `slug` | URL-safe identifier for public routing |

**Business meaning:** A new painting contractor signs up → a `Tenant` is created with `sector="painting"` → they get their own intake form URL (`/intake/{slug}`) → their leads are scoped to their `tenant_id` → their pricing overrides are read at pipeline time.

### PipelineRun

**File:** `app/models/pipeline_run.py`

**Purpose:** Records a single execution of the estimation pipeline for a lead. The authoritative record of what happened during processing.

**Key fields:**
| Field | Purpose |
|---|---|
| `trace_id` | Correlation ID linking log lines to this run |
| `vertical_id` | Which vertical's pipeline ran |
| `engine_version` | Version of the engine that produced this run |
| `config_hash` | 12-char SHA-256 prefix of the pipeline structure — same hash means same pipeline shape |
| `status` | `RUNNING` → `COMPLETED` / `FAILED` |
| `failure_step` | Which step failed (if any) |
| `error_category` | Taxonomy: `transient` / `permanent` / `validation` / `external_dependency` |
| `overall_confidence_score` | Weakest-link minimum of all step confidence scores |
| `overall_confidence_label` | Human-readable tier (`high`, `medium`, `low`) |

**Relationships:** `steps: List[PipelineStepRun]`

**Business meaning:** A `PipelineRun` is the unit of analysis for the entire intelligence layer. Anomaly detectors, trend engines, and health summaries all query `PipelineRun` records. The `config_hash` enables detecting when pipeline structure changes affect outcomes.

### PipelineStepRun

**File:** `app/models/pipeline_run.py`

**Purpose:** Records the execution of a single step within a `PipelineRun`. Contains input and output snapshots for debugging.

**Key fields:** `step_name`, `step_use` (registry key), `step_order`, `status`, `input_snapshot`, `output_snapshot`, `confidence_score`, `confidence_reason`, `duration_ms`, `error_category`

**Business meaning:** When a run fails, engineers inspect `PipelineStepRun.input_snapshot` and `output_snapshot` to identify the exact transformation that went wrong. The `step_use` field records which version of a step function was used, enabling reproducibility analysis.

### LeadFeedback

**File:** `app/models/lead_feedback.py`

**Purpose:** Records deal outcome and pricing accuracy after a lead is resolved. This is the ground truth for the intelligence layer's pricing signals.

**Key fields:**
| Field | Purpose |
|---|---|
| `outcome` | `"won"` or `"lost"` |
| `actual_price` | What the deal actually closed at |
| `estimated_price` | What the system estimated |
| `override_reason` | Why the price was manually overridden (if applicable) |

**Business meaning:** The delta between `estimated_price` and `actual_price` on `"won"` deals is the primary signal for the `LIKELY_UNDERPRICING` intelligence detector. A pattern of winning deals at prices significantly higher than the estimate means the pricing engine is underpricing.

### ProposedChangeReviewState

**File:** `app/models/proposed_change_review_state.py`

**Purpose:** Persists the current review status of a proposed system change. The source of truth for the operator's governance workflow.

**Key fields:**
| Field | Purpose |
|---|---|
| `change_id` | Stable deterministic ID (`scope_type:scope_id:category:parameter`) |
| `scope_type` | `"pipeline"` or `"vertical"` |
| `status` | `pending` / `approved` / `rejected` / `archived` |
| `proposal_payload` | Snapshot of the proposal at persist time |

**Unique constraint:** `(tenant_id, change_id)` — one review state per change per tenant.

**Business meaning:** This model is the bridge between the automated intelligence layer and human action. A proposed change is generated deterministically by `compute_proposed_changes()`, persisted here for operator review, then acted upon through the execution lifecycle models.

### RunReviewState

**File:** `app/models/run_review_state.py`

**Purpose:** Tracks the human review state of a specific `PipelineRun` that was flagged as needing review.

### ActivityEvent

**File:** `app/models/activity_event.py`

**Purpose:** Append-only log of user actions within the platform (e.g. "user sent quote", "user overrode price"). Supports the activity feed in the operator app.

### EngineEvent

**File:** `app/models/engine_event.py`

**Purpose:** Records significant events emitted by the pipeline engine during execution. Provides a higher-level narrative of pipeline progress, distinct from the step-by-step `PipelineStepRun` trace.

---

## 7. Execution Lifecycle

### Complete Run: Intake to Feedback

```
[1. INTAKE]
  Customer submits form at /intake/{tenant_slug}
  │
  ├── Lead created in DB (status: NEW)
  ├── Files uploaded via presigned S3 URLs
  └── Pipeline triggered

[2. VISION]
  app/tasks/vision_task.py → run_vision_for_lead()
  │
  ├── Each photo scored for usability (local PyTorch model)
  ├── Usable photos sent to OpenAI Vision API
  │   └── Prompt: app/verticals/painting/prompts/vision.md
  ├── Per-image predictions aggregated → lead-level signals
  │   └── area_m2, scope, modifiers, damages, uncertainty, coverage
  └── Fallback: if no photos, demo_vision() returns placeholder signals

[3. PRICING]
  app/verticals/painting/pricing_engine_us.py → run_pricing_engine()
  │
  ├── Rules loaded from JSON (EU or US based on locale)
  ├── Tenant pricing overrides applied (Tenant.pricing_json)
  ├── Vision signals → area × base_rate × scope × complexity × prep_level
  └── Output: line items, subtotals, VAT, grand total, assumptions

[4. OUTPUT BUILDER]
  app/verticals/painting/pricing_output_builder.py → build_pricing_output()
  │
  ├── Merges vision meta into estimate output
  ├── Resolves branding (company name, logo) based on plan tier
  └── Produces structured estimate dict

[5. REVIEW DECISION]
  app/verticals/painting/needs_review.py → needs_review_from_output()
  │
  ├── Hard blockers: missing total, zero/negative total → REVIEW
  ├── Soft signals: low confidence, extreme areas, photo issues, damages
  ├── Risk score: uncertainty + coverage + fallback + damage severity
  └── Decision: auto-deliver if 0–1 soft signals; review if 2+

[6. HTML RENDER + STORAGE]
  app/verticals/painting/render_estimate.py → render_estimate_html()
  │
  ├── Jinja2 renders estimate to HTML
  ├── HTML stored in S3: leads/{lead_id}/estimates/{date}/{filename}.html
  └── public_token generated (for customer-facing URL)

[7. DELIVERY]
  app/routers/quotes.py / app/verticals/painting/estimate_email.py
  │
  ├── Email sent to customer with estimate link
  ├── Customer views at /estimate/{public_token}
  └── Customer accepts or rejects → timestamps recorded

[8. FEEDBACK]
  app/routers/lead_feedback.py
  │
  ├── Operator records outcome: won/lost, actual price
  └── LeadFeedback persisted

[9. INTELLIGENCE LOOP]
  (periodic / on-demand)
  │
  ├── Metrics aggregated per pipeline / vertical
  ├── Anomaly engine runs → structural contradictions flagged
  ├── Intelligence engine runs → behavioral patterns detected
  ├── Trend engine compares current vs. prior window
  ├── Health layer produces pipeline/vertical health scores
  ├── Reasoning engine diagnoses root causes
  ├── Focus engine prioritizes attention queue
  └── Proposed changes generated → operator review queue
```

### Pipeline Run Execution Trace

Every run through steps 2–6 above is recorded as a `PipelineRun` with one `PipelineStepRun` per step. Engineers can query `GET /pipeline-runs/{run_id}` to see the full trace of any historical execution, including input/output snapshots at each step, confidence scores, and error details.

---

## 8. Engineering Principles

### 1. Determinism Over Magic

Every output the system produces — estimates, confidence scores, anomaly flags, proposed changes — can be reproduced by re-running the same inputs through the same code. There is no non-determinism except at the OpenAI API boundary (vision inference).

This is enforced structurally:
- Pricing rules are JSON files, not database state
- The reasoning engine is a pure function over dicts
- Proposed changes produce stable IDs from deterministic inputs
- The `config_hash` on `PipelineRun` identifies whether two runs used the same pipeline structure

**Why it matters:** When an estimate is wrong, engineers can replay the exact inputs and reproduce the output. When a pricing change is proposed, operators can predict exactly what will happen. Trust requires reproducibility.

### 2. Observability First

The system instruments itself not just for DevOps purposes but as a product feature. Pipeline step inputs and outputs are snapshots. Confidence scores are per-step and per-run. Anomalies are first-class entities, not log lines.

**Why it matters:** The intelligence layer — everything above the pipeline in the architecture — is only possible because the pipeline produces rich, queryable telemetry. Observability is not added on top; it is structurally embedded.

### 3. Human-in-the-Loop Governance

The system identifies problems and proposes solutions, but applies nothing without explicit human approval. The governance model (six `proposed_change_*` models, complete audit trail) exists precisely because automated changes to pricing logic carry real business risk.

**Why it matters:** A pricing system that silently adjusts its own rules without human oversight is not trustworthy. The proposed change layer makes the system's suggestions actionable while preserving human control. The audit trail ensures every change is attributable.

### 4. Confidence as a First-Class Signal

Every pipeline step that produces a meaningful output is expected to also produce a confidence score. Steps that cannot produce confidence scores create an observability gap (flagged by the `CONFIDENCE_ABSENT_ON_COMPLETION` anomaly). The overall run confidence is the weakest-link minimum — a system is only as confident as its least confident step.

**Why it matters:** Confidence scores drive the review routing decision. Without them, the system cannot distinguish between "I'm certain this is right" and "I'm guessing." Making confidence explicit and mandatory prevents the system from masking uncertainty.

### 5. Explicit Rules Over Learned Models

The pricing engine, review decision logic, reasoning engine, trend classifier, and focus scoring engine are all implemented as explicit, readable rules — not ML models. The only ML inference is at the OpenAI Vision boundary (photo analysis) and the local photo quality classifier.

**Why it matters:** Rules are auditable, debuggable, and changeable through the governance process. A rule that produces wrong outputs can be identified, explained, and corrected. A model that produces wrong outputs requires retraining and validation. For a pricing system, auditability is non-negotiable.

### 6. Config Over Code for Verticals

New verticals are added through the vertical registry (`app/verticals/registry.py`) and a manifest (`vertical.yaml`). The `Tenant.sector` field is validated against registered verticals. Tenants can have multiple enabled verticals (`Tenant.enabled_verticals`).

**Why it matters:** The platform is designed to expand to new trade verticals (roofing and solar are already scaffolded) without architectural changes. A new vertical should require a new `app/verticals/{vertical}/` package, not changes to core platform code.

### 7. Multi-Tenancy by Default

Every entity in the system — leads, pipeline runs, feedback records, proposed changes — carries a `tenant_id`. Database queries scope to tenant by default. There is no "global" state except for platform-level configuration.

**Why it matters:** Data isolation is not an afterthought. From the first model onwards, tenant isolation is structurally enforced. This is foundational for compliance, trust, and scalability.

### 8. Separation of Proposal and Execution

The `compute_proposed_changes()` function is a pure function that generates proposals. Persistence is a separate operation. Execution is gated by human approval and runs through a separate lifecycle. This separation is repeated throughout: the reasoning engine is pure; the trend engine is pure; the health layer is read-only.

**Why it matters:** Pure functions are composable, testable, and safe to run in simulation mode. The `/simulation_preview` endpoint leverages this to show operators what a proposed change would produce without persisting anything.

---

## 9. Repository Guide

### Folder Structure

```
Inversiq/
├── app/                        # Main application package
│   ├── main.py                 # Application entry point, router mounting, middleware
│   ├── models/                 # SQLAlchemy ORM models (30+ files)
│   ├── routers/                # FastAPI route handlers (60+ files)
│   ├── services/               # Business logic services
│   ├── verticals/              # Vertical plugin system
│   │   ├── base.py             # BaseVertical abstract class
│   │   ├── registry.py         # Vertical registry (VERTICALS dict)
│   │   ├── painting/           # Fully implemented painting vertical
│   │   ├── roofing/            # Scaffolded roofing vertical
│   │   └── solar/              # Scaffolded solar vertical
│   ├── intelligence/           # Behavioral pattern detectors
│   ├── anomaly/                # Structural anomaly detectors
│   ├── health/                 # Pipeline/vertical health aggregation
│   ├── auth/                   # JWT authentication, password hashing
│   ├── billing/                # Stripe integration, plan entitlements
│   ├── modules/
│   │   └── outreach/           # Email follow-up module (models, repos, services)
│   ├── observability/          # Prometheus metrics
│   ├── aws/                    # S3 operations
│   ├── db/                     # Database session and base
│   ├── core/                   # Settings, logging, contracts, rate limiting
│   ├── tasks/                  # Celery tasks (vision processing)
│   ├── jobs/                   # In-process background job runner
│   ├── ml/                     # Local ML model training/eval (photo quality)
│   ├── templates/              # Jinja2 HTML templates (ops dashboard)
│   ├── i18n/                   # Translation files (en.json, nl.json)
│   ├── schemas/                # Pydantic request/response schemas
│   ├── pipeline/               # Pipeline context
│   ├── workflow/               # Workflow status
│   └── static/                 # Static assets
├── frontend/                   # Next.js operator SPA
│   └── src/
│       ├── app/                # Next.js App Router pages
│       └── components/         # React components (dashboard, billing, layout)
├── inversiq/                   # Emerging engine abstraction package
│   └── engine/                 # Engine context, config, registry, runner, steps
├── docs/                       # Documentation (requirements, architecture)
├── docker-compose.yml          # Core stack
├── docker-compose.observability.yml  # Prometheus + Grafana
├── Dockerfile                  # Application image
├── requirements.txt            # Python dependencies
└── pyproject.toml              # Project metadata
```

### Entry Points

| Entry Point | Description |
|---|---|
| `app/main.py` | FastAPI application — start here to understand routing and middleware |
| `app/verticals/painting/pipeline.py` | The estimation pipeline — the core business logic |
| `app/verticals/registry.py` | How verticals are registered and resolved |
| `app/models/__init__.py` | All SQLAlchemy models imported in one place |
| `app/intelligence/engine.py` | The intelligence layer entry point |
| `app/services/reasoning_engine.py` | The reasoning / diagnosis engine |
| `app/services/proposed_changes.py` | The governance proposal generator |

### Important Configuration Files

| File | Purpose |
|---|---|
| `.env` | Environment variables (DATABASE_URL, REDIS_URL, OPENAI_API_KEY, STRIPE keys) |
| `app/verticals/painting/manifest.yaml` | Painting vertical metadata (locale, currency, units) |
| `app/verticals/painting/rules/paintly_price_rules_eu.json` | EU pricing rule set |
| `app/verticals/painting/intake_schema.json` | JSON Schema for intake form validation |
| `app/verticals/painting/prompts/vision.md` | The OpenAI vision prompt |
| `app/core/settings.py` | Pydantic settings model (all env vars typed) |
| `app/config/plans.py` | Plan code definitions |

### Where to Start Reading

**If you want to understand the business domain:** Start with `app/verticals/painting/pipeline.py`. This is the core product in 400 lines.

**If you want to understand the data model:** Start with `app/models/lead.py`, then `app/models/pipeline_run.py`, then `app/models/lead_feedback.py`.

**If you want to understand the intelligence layer:** Start with `app/intelligence/engine.py`, then `app/services/trend_engine.py`, then `app/services/reasoning_engine.py`.

**If you want to understand the governance layer:** Start with `app/services/proposed_changes.py`, then `app/models/proposed_change_review_state.py`.

**If you want to understand the multi-tenant system:** Start with `app/models/tenant.py`, then `app/verticals/registry.py`.

**If you want to add a new vertical:** Read `app/verticals/painting/__init__.py` and `app/verticals/roofing/__init__.py` side by side. Then read `app/verticals/registry.py`.

---

## 10. Future Architecture Opportunities

### 1. Complete the `inversiq.engine` Migration

The `inversiq/engine/` package (referenced in `app/verticals/painting/pipeline_engine.py`) represents the next-generation pipeline runner. It introduces formal concepts like `EngineContext`, `StepRegistry`, and `load_engine_config`. The current production pipeline (`app/verticals/painting/pipeline.py`) is an imperative function — not yet using this abstraction.

**Opportunity:** Migrate all verticals to the `inversiq.engine` runner. This enables:
- Config-driven pipeline definitions (JSON) rather than code
- Step versioning and registry-based step resolution
- Portable pipelines that can run outside the FastAPI context (CLI, worker processes)
- The `config_hash` concept to detect pipeline shape changes automatically

### 2. Alembic for Database Migrations

Schema creation currently uses `Base.metadata.create_all()` at startup (suitable for development/SQLite). The `docker-compose.yml` references a `./migrations/` directory for PostgreSQL initialization, but no Alembic migration files are present.

**Opportunity:** Set up Alembic with versioned migrations. This is a prerequisite for zero-downtime production deployments and safe schema evolution across multiple tenants.

### 3. Async Vision Pipeline

The vision stage calls the OpenAI API synchronously within the pipeline. For leads with many photos, this creates latency that blocks the HTTP response. Celery tasks exist (`app/tasks/vision_task.py`, `app/celery_tasks.py`) but integration into the main pipeline is partial.

**Opportunity:** Decouple vision from the synchronous HTTP path entirely. The intake endpoint creates the lead and returns immediately; vision processing runs in Celery; the operator app polls for status. This also enables retry logic for transient OpenAI errors.

### 4. Pricing Rule Governance

Pricing rules are currently stored as JSON files in the repository (`app/verticals/painting/rules/`). Tenant overrides are stored in `Tenant.pricing_json`. There is no version history of rule changes, no diff view, and no connection between a rule change and its effect on output.

**Opportunity:** The proposed change governance layer is already built. The missing piece is making the rule files themselves a governed artifact: storing rule sets in the database, versioning them, and routing changes through the `ProposedChangeReviewState` workflow. The `config_hash` on `PipelineRun` already captures the pipeline structure — extending this to capture the rule set version would close the loop.

### 5. Feedback Loop Automation

The feedback loop (intake → estimate → feedback → intelligence → proposals) currently requires manual operator action at several steps (recording feedback, approving proposals). The data model and service layer support full automation, but the execution is not yet wired.

**Opportunity:** Introduce scheduled intelligence runs (e.g. nightly) that automatically:
- Aggregate feedback from the past 30 days
- Run the anomaly and intelligence engines
- Compute trends
- Generate and persist proposed changes to the review queue

This transforms the intelligence layer from an on-demand diagnostic tool into a continuous operational feedback loop.

### 6. Step Contract Versioning

`PipelineStepRun` has a `step_contract_version` field (`step_contract_version: Mapped[Optional[str]]`) intended to capture the semantic version of the step implementation at run time. The model is in place but the mechanism for steps to declare their contract version is not consistently enforced.

**Opportunity:** Define a formal step contract protocol in the `inversiq.engine` package where step functions declare their version, input schema, and output schema. This enables detecting schema drift between step versions and producing accurate "this run used step v1.2, current is v1.3" diagnostics.

### 7. Multi-Vertical Lead Routing

The `Tenant.enabled_verticals` field allows a tenant to access multiple verticals, but the current routing assumes a single vertical per tenant (derived from `Tenant.sector`). A roofing company that also does solar would need manual handling today.

**Opportunity:** Route leads to verticals based on the intake form's declared vertical, not the tenant's sector. This enables multi-service contractors to use a single tenant account across multiple verticals.

### 8. Confidence Score Calibration

The confidence scoring system is structurally sound but thresholds are currently fixed constants (e.g. review triggered at confidence < 0.45, low-confidence signal at < 0.40 in the intelligence engine). There is no feedback loop that adjusts these thresholds based on which confidence-gated decisions led to good versus bad outcomes.

**Opportunity:** Use `LeadFeedback` records to calibrate confidence thresholds: if runs with confidence 0.45–0.55 that were auto-delivered consistently produce won deals, the review threshold can safely be lowered. This is the natural extension of the proposed changes governance layer to confidence configuration.

---

_This handbook reflects the codebase as of June 2026. It should be updated whenever significant architectural decisions are made. The authoritative source of truth for any specific behavior is always the code._
