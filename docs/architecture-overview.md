# Architecture Overview

_Inversiq — June 2026_
_Quick reference for engineers and technical stakeholders_

---

## One-Page System Overview

Inversiq is the AI Operating System for Operational Industries. It is a FastAPI backend (Python 3.11) backed by PostgreSQL and Redis, serving two frontend surfaces: a Next.js SPA for operators and Jinja2-rendered HTML views for the ops dashboard. AWS S3 stores uploaded photos and rendered HTML estimates. The OpenAI Vision API is the only external AI dependency. A `inversiq.engine` package provides a formally typed pipeline runner that sits alongside (and is in the process of replacing) the imperative construction pipeline.

```
Customer            Operator               Ops Dashboard
   │                   │                       │
   ▼                   ▼                       ▼
Intake Form         Next.js SPA           Jinja2 + HTMX
(Jinja2, public)   (localhost:3000)       (painting vertical)
       │                │                       │
       └───────────────►▼◄──────────────────────┘
                   FastAPI Backend
                   app/main.py (~70 routers)
                        │
          ┌─────────────┼─────────────┐
          ▼             ▼             ▼
      Pipeline       Intelligence   Governance
      Engine         Layer          Layer
          │             │             │
     ┌────┴────┐    ┌───┴──┐    ┌───┴──────────┐
   Vision   Pricing  Anomaly  Health  Proposed   Audit
  (OpenAI)  (JSON)  Intel   Health  Changes     Trail
              rules)  Trend  Reason
                      Focus
          │
    ┌─────┼─────┐
    ▼     ▼     ▼
  PG    Redis   S3
```

---

## Component Responsibilities

| Component | Location | Responsibility |
|---|---|---|
| **FastAPI App** | `app/main.py` | HTTP routing, middleware stack, startup |
| **Vertical Registry** | `app/verticals/registry.py` | Plugin system for trade verticals |
| **Construction Pipeline** | `app/verticals/construction/pipeline.py` | Production estimation pipeline (imperative) |
| **Engine Runner** | `inversiq/engine/runner.py` | Next-gen config-driven pipeline (emerging) |
| **Vision Task** | `app/tasks/vision_task.py` | Photo quality screening + OpenAI Vision |
| **Pricing Engine** | `app/verticals/construction/pricing_engine_us.py` | JSON-rules-based estimate calculation |
| **Review Decision** | `app/verticals/construction/needs_review.py` | Hard/soft blocker review routing |
| **Anomaly Engine** | `app/anomaly/engine.py` | Structural contradiction detection (5 detectors) |
| **Intelligence Engine** | `app/intelligence/engine.py` | Behavioral pattern detection (5 detectors) |
| **Trend Engine** | `app/services/trend_engine.py` | Metric direction classification (pure function) |
| **Health Layer** | `app/health/summary.py` | Pipeline/vertical health aggregation |
| **Reasoning Engine** | `app/services/reasoning_engine.py` | Root-cause diagnosis (pure function) |
| **Focus Engine** | `app/services/focus_engine.py` | Operator attention queue prioritization |
| **Proposed Changes** | `app/services/proposed_changes.py` | Change proposal generation (pure function) |
| **Outreach Module** | `app/modules/outreach/` | Email follow-up, reply sync, Gmail OAuth |
| **Billing/Entitlements** | `app/billing/entitlements.py` | Plan-based feature gating and usage limits |
| **Observability** | `app/observability/metrics.py` | Prometheus metrics at `/metrics` |
| **Auth** | `app/auth/` | JWT token generation, password hashing |
| **Storage** | `app/services/storage.py` | S3 abstraction with local mock fallback |

---

## Key Design Decisions

| Decision | Why |
|---|---|
| Weakest-link confidence | Overall confidence = min(step scores). One uncertain step prevents auto-delivery. Conservative by design. |
| Pure functions for analysis | Reasoning, trend, focus, and proposed changes are pure functions: no side effects, testable without DB. |
| Governance lifecycle (6 models) | Automated pricing changes carry real financial risk. Human approval is non-negotiable. |
| Deterministic change IDs | Same system state always produces the same proposal ID. Prevents duplicate proposals. |
| No static AWS keys | Machine-enforced at startup. IAM roles or profiles required. |
| JSON pricing rules | Rules are files, not database state. Auditable, version-controlled, replaceable. |
| Dual pipeline (imperative + engine runner) | Incremental migration. Engine runner has richer observability but is not yet driving production. Construction is the reference implementation. |
| Shared-schema multi-tenancy | `tenant_id` on every entity. Isolation at application layer. Simpler than per-tenant schemas for current scale. |
| Explicit rules over ML | Pricing, review logic, reasoning: all explicit code. Only AI: OpenAI Vision (photos) and local photo quality model. |

---

## Data Model Relationships

```
Tenant (1)
    ├── (n) Leads
    │       ├── (n) LeadFiles (uploaded photos)
    │       ├── (1) LeadFeedback (won/lost, actual price)
    │       └── (n) PipelineRuns
    │               └── (n) PipelineStepRuns
    │                       ├── input_snapshot (JSON)
    │                       └── output_snapshot (JSON)
    ├── (n) Users
    ├── (n) ProposedChangeReviewStates
    │       └── (n) ProposedChangeAuditEvents
    ├── (n) TenantUsage
    └── (n) OutboundMessages → (n) MessageReplies
```

**Key denormalizations:**
- `PipelineRun.tenant_id` is stored directly (no FK to tenants) — keeps the engine generic
- `PipelineRun.lead_id` is stored directly (no FK to leads) — same reason
- `PipelineRun.overall_confidence_score` denormalizes the min of step scores for easy querying

---

## Service Boundaries

| Boundary | Communication | Notes |
|---|---|---|
| Frontend ↔ Backend | HTTP REST via catch-all proxy | `frontend/src/app/api/backend/[...path]/route.ts` |
| Backend ↔ PostgreSQL | SQLAlchemy ORM | `app/db/session.py`, `SessionLocal` |
| Backend ↔ Redis | Celery broker | `redis://redis:6379/0` |
| Backend ↔ S3 | boto3 via `app/services/storage.py` | Abstracted; mock fallback available |
| Backend ↔ OpenAI | `openai` SDK | `app/services/vision/openai_provider.py` |
| Backend ↔ Stripe | `stripe` SDK | `app/services/stripe_service.py` |
| Backend ↔ Gmail | `google-api-python-client` | `app/modules/outreach/services/gmail_provider.py` |
| `inversiq.engine` ↔ `app/` | Lazy imports only | Engine stays decoupled; imports app models lazily |

---

## Infrastructure Topology

```
Internet
    │
    ▼
Load Balancer (assumed — not in repo)
    │
    ▼
Gunicorn (multi-worker UvicornWorker)
    │  app.main:app  port 8080
    │
    ├── PostgreSQL 15 (docker-compose: postgres service)
    │
    ├── Redis 7 (docker-compose: redis service)
    │       └── Celery workers (vision processing)
    │
    ├── AWS S3 (external — bucket name from env)
    │
    ├── OpenAI API (external)
    │
    ├── Prometheus (docker-compose.observability.yml)
    │       └── scrapes /metrics every N seconds
    │
    └── Grafana (docker-compose.observability.yml)
            └── dashboards over Prometheus data
```

---

## Middleware Stack (in `app/main.py`, innermost first)

1. `RequestIdMiddleware` — attaches `X-Request-ID` to every request for log correlation
2. `SlowAPIMiddleware` — rate limiting (slowapi library)
3. `BasicAuthMiddleware` — HTTP basic auth on `/sales` and `/api` path prefixes
4. `CORSMiddleware` — configured from `settings.allowed_origins_list`
5. HTTP logging middleware — structured JSON logs with `request_id`, `tenant_id`, `latency_ms`

---

## Vertical Plugin Interface

Each vertical must implement one of:

**`BaseVertical`** (Python class):
- `key: str` — registry key (e.g. "construction")
- `label: str` — display label
- `get_workflows() -> list[dict]` — step configuration for the engine runner
- `get_ui_workflows() -> list[str]`
- `get_dashboard_config() -> dict`
- `get_features() -> dict`

**`VerticalAdapter`** (structural protocol):
- `vertical_id: str`
- `render_intake_form(request, lead_id, tenant_id, ...) -> Response`
- `create_lead_from_form(request, db, tenant_id) -> IntakeResult`
- `upsert_lead_from_form(request, db, tenant_id) -> IntakeResult`

Registered verticals: `construction` (ConstructionVertical + ConstructionAdapter). Future verticals: `insurance`, `logistics`, `real_estate`.
