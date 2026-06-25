# System Diagrams

_Inversiq — June 2026_
_All diagrams are Mermaid. Render with any Mermaid-compatible viewer._

---

## 1. System Architecture Map

```mermaid
graph TB
    subgraph CLIENTS["Client Surfaces"]
        CF["Customer Intake Forms\n(Public, Jinja2 HTML)"]
        NS["Next.js Operator SPA\n(frontend/, port 3000)"]
        OD["Ops Dashboard\n(Jinja2 + HTMX, construction vertical)"]
    end

    subgraph BACKEND["FastAPI Backend (app/main.py)"]
        subgraph MIDDLEWARE["Middleware Stack"]
            RI["RequestIdMiddleware"]
            RL["SlowAPI Rate Limiter"]
            BA["BasicAuthMiddleware\n(/sales, /api)"]
            CO["CORSMiddleware"]
            LG["HTTP Logging Middleware"]
        end

        subgraph ROUTERS["~70 Routers"]
            PUB["Public Intake\n/intake, /public"]
            AUTH["Auth / User\n/auth, /me"]
            BILL["Billing\n/billing, /stripe"]
            PIPE["Pipeline & Runs\n/pipeline-runs, /ops"]
            INT["Intelligence Layer\n/anomalies, /intelligence\n/trends, /health\n/reasoning, /focus"]
            GOV["Governance\n/proposed-changes\n/proposed-change-*"]
            PAINT["Construction Vertical\n/app, /htmx, /integrations"]
        end

        subgraph PIPELINE["Estimation Pipeline"]
            VIS["Vision Stage\n(photo quality + OpenAI)"]
            PRIC["Pricing Stage\n(JSON rules + overrides)"]
            OUT["Output Builder\n(branding + structure)"]
            REV["Review Decision\n(hard/soft blockers)"]
            REND["HTML Render + S3 Store"]
        end

        subgraph INTEL["Intelligence Layer"]
            ANOM["Anomaly Engine\n5 detectors"]
            IE["Intelligence Engine\n5 detectors"]
            TE["Trend Engine\n(pure fn)"]
            HL["Health Layer\n(per-pipeline, per-vertical)"]
            RE["Reasoning Engine\n(pure fn, 8 categories)"]
            FE["Focus Engine\n(pure fn, score 0-100)"]
        end

        subgraph GOVERN["Governance Layer"]
            PC["Proposed Changes\n(pure fn)"]
            LS["6-Model Lifecycle"]
        end

        OUT2["Outreach Module\n(follow-up, Gmail, reply classifier)"]
        ENT["Billing Entitlements\n(plan features, usage limits)"]
        OBS["Prometheus /metrics"]
    end

    subgraph INFRA["Infrastructure"]
        PG[("PostgreSQL 15\nPrimary DB")]
        RD[("Redis 7\nCelery Broker")]
        S3[("AWS S3\nPhotos + HTML")]
        OAI["OpenAI Vision API\n(external)"]
        STR["Stripe\n(external)"]
    end

    subgraph ENGINE["inversiq.engine package"]
        ER["Engine Runner\nrunner.py"]
        EC["Engine Config\nconfig.py"]
        EG["Step Registry\nregistry.py"]
    end

    CF --> PUB
    NS --> AUTH
    NS --> BILL
    NS --> INT
    NS --> GOV
    OD --> PAINT

    PUB --> PIPELINE
    PAINT --> PIPELINE

    VIS --> PRIC --> OUT --> REV --> REND

    PIPELINE --> ANOM --> IE --> TE --> HL --> RE --> FE --> PC --> LS

    PIPELINE --> PG
    REND --> S3
    VIS --> OAI
    BILL --> STR
    OUT2 --> PG
    LS --> PG

    PIPELINE --> RD

    ER --> PIPELINE

    OBS --> OBS
```

---

## 2. Data Flow Map (Intake to Intelligence)

```mermaid
sequenceDiagram
    participant C as Customer
    participant API as FastAPI
    participant S3 as AWS S3
    participant OAI as OpenAI Vision
    participant DB as PostgreSQL
    participant OPS as Operator

    C->>API: POST /intake/{slug} (form data)
    API->>DB: CREATE Lead (status=NEW)
    API-->>C: Redirect to /processing/{lead_id}

    C->>API: GET /uploads/presign (for each photo)
    API-->>C: Presigned S3 URL
    C->>S3: PUT photo directly
    C->>API: POST /uploads/verify

    API->>DB: CREATE LeadFile (s3_key)
    API->>API: Trigger pipeline

    Note over API: Vision Stage
    API->>API: Photo quality screen (local PyTorch)
    API->>OAI: Send usable photos + vision prompt
    OAI-->>API: Structured signals (area, scope, modifiers, damages)
    API->>API: Aggregate per-image → lead-level signals

    Note over API: Pricing Stage
    API->>DB: READ Tenant.pricing_json
    API->>API: Apply JSON rules + tenant overrides → line items

    Note over API: Output + Review
    API->>API: Build estimate structure + branding
    API->>API: Evaluate hard/soft blockers → needs_review?

    Note over API: Storage
    API->>API: Render HTML (Jinja2)
    API->>S3: Store HTML estimate
    API->>DB: UPDATE Lead (estimate_json, html_key, status=DONE or NEEDS_REVIEW)
    API->>DB: CREATE PipelineRun + PipelineStepRuns

    API->>C: Send estimate email

    C->>API: GET /estimate/{public_token}
    API->>DB: SET Lead.viewed_at
    C->>API: Accept/Reject
    API->>DB: SET Lead.accepted_at or reject_reason

    OPS->>API: POST /lead-feedback (won/lost, actual_price)
    API->>DB: CREATE LeadFeedback

    Note over API,DB: Intelligence Loop (on-demand)
    OPS->>API: GET /anomalies, /intelligence, /trends, /health, /reasoning, /focus
    API->>DB: READ PipelineRuns, LeadFeedback (lookback window)
    API-->>OPS: Signals, health scores, proposed changes
```

---

## 3. Pipeline Execution Flow

```mermaid
flowchart TD
    START([Lead Created\nstatus=NEW]) --> FILES{Any uploaded\nphoto files?}

    FILES -->|Yes| QS[Photo Quality Screening\nlocal PyTorch/timm model]
    FILES -->|No| DEMO[Demo Vision\nfallback signals\n75m2 / light prep]

    QS --> USABLE{Usable photos?}
    USABLE -->|Yes| OPENAI[OpenAI Vision API\nvision.md prompt\narea, scope, modifiers, damages]
    USABLE -->|No| DEMO

    OPENAI --> AGG[Vision Aggregate\nvision_aggregate_us.py\nper-image → lead-level signals]
    DEMO --> AGG

    AGG --> PRICING[Pricing Engine\nprice_rules_eu/us.json\n+ Tenant.pricing_json overrides\n→ line items, totals, VAT]

    PRICING --> OUTPUT[Output Builder\npricing_output_builder.py\nmerge vision meta + branding]

    OUTPUT --> REVIEW{Review Decision\nneeds_review_from_output}

    REVIEW -->|Hard blocker:\nmissing/zero total| NEEDSREV[status = NEEDS_REVIEW\nreason codes set]
    REVIEW -->|2+ soft signals\nstacking| NEEDSREV
    REVIEW -->|0-1 soft signals| AUTODELIVER

    AUTODELIVER[Auto-deliver path] --> HTML[Render HTML\nJinja2 template]
    NEEDSREV --> HTML

    HTML --> STORE[Store to S3\nleads/{id}/estimates/{date}/{uuid}.html]
    STORE --> TOKEN[Generate public_token\nif not exists]
    TOKEN --> DONE([Return estimate_json\nestimate_html_key\nneeds_review])

    DONE --> PIPELINE_RUN[(PipelineRun\nCOMPLETED/NEEDS_REVIEW\nwith step runs + snapshots)]
```

---

## 4. Intelligence Loop Flow

```mermaid
flowchart LR
    subgraph DATA["Source Data"]
        PR["PipelineRun\n+ PipelineStepRun\n(run history)"]
        LF["LeadFeedback\n(won/lost, prices)"]
    end

    subgraph ANOMALY["Anomaly Engine\napp/anomaly/"]
        A1["PRICE_DELTA_LARGE\n>50% from baseline"]
        A2["FAILED_HIGH_CONFIDENCE\nlogical contradiction"]
        A3["MISSING_STEP_OUTPUT\nobservability gap"]
        A4["CONFIDENCE_ABSENT\non completion"]
        A5["REPEATED_FAILURE\n3+ in 24h window"]
    end

    subgraph INTEL["Intelligence Engine\napp/intelligence/"]
        I1["LIKELY_UNDERPRICING\n10%+ below, 60%+ fraction"]
        I2["LIKELY_OVERPRICING\n60%+ loss rate"]
        I3["REPEATED_LOW_CONFIDENCE\n<0.40 on 5+ runs"]
        I4["REPEATED_FALLBACK\n3+ fallback runs"]
        I5["REPEATED_REVIEW_FLAG\n3+ review-routed runs"]
    end

    subgraph ANALYSIS["Analysis Layer"]
        TREND["Trend Engine\ncurrent vs prior window\nper-metric direction + severity"]
        HEALTH["Health Layer\nhealthy / watch / unhealthy\nper pipeline_name + per vertical"]
        REASON["Reasoning Engine\n8 diagnostic categories\npure function"]
        FOCUS["Focus Engine\nscore = health + trend + signals\npriority: critical/high/medium/low"]
    end

    subgraph GOVERN["Governance"]
        PROP["Proposed Changes\nchange_id = scope:category:param\nrisk_level, rollback_hint"]
        STATE["ProposedChangeReviewState\npending / approved / rejected"]
        AUDIT["ProposedChangeAuditEvent\nimmutable trail"]
    end

    PR --> ANOMALY
    PR --> INTEL
    LF --> INTEL

    ANOMALY --> HEALTH
    INTEL --> HEALTH
    INTEL --> TREND
    TREND --> REASON
    HEALTH --> REASON
    REASON --> FOCUS
    FOCUS --> PROP
    PROP --> STATE
    STATE --> AUDIT
```

---

## 5. Governance Flow (Proposed Change Lifecycle)

```mermaid
stateDiagram-v2
    [*] --> Generated : compute_proposed_changes()\n(pure function)

    Generated --> Persisted : Caller persists\nProposedChangeReviewState\nstatus=pending

    Persisted --> Reviewed : Operator views\nin review queue

    Reviewed --> Approved : Operator approves
    Reviewed --> Rejected : Operator rejects

    Approved --> ApplyIntent : ProposedChangeApplyIntent\ncreated

    ApplyIntent --> ExecutionRequest : ProposedChangeExecutionRequest\ncreated

    ExecutionRequest --> Attempting : ProposedChangeExecutionAttempt\n(per try)

    Attempting --> Outcome : ProposedChangeExecutionOutcome\n(success / failure)

    Rejected --> AuditTrail : ProposedChangeAuditEvent\n(immutable)
    Outcome --> AuditTrail : ProposedChangeAuditEvent\n(immutable)

    AuditTrail --> [*]
```

---

## 6. Database Schema Relationships

```mermaid
erDiagram
    Tenant {
        string id PK
        string name
        string slug
        string sector
        json pricing_json
        json enabled_verticals
        string plan_code
        string stripe_customer_id
    }

    User {
        int id PK
        string tenant_id FK
        string email
        string company_name
        string logo_url
        bool is_active
    }

    Lead {
        string id PK
        string tenant_id FK
        string vertical
        string name
        string email
        string status
        text intake_payload
        text estimate_json
        string estimate_html_key
        string public_token
        datetime sent_at
        datetime accepted_at
    }

    LeadFile {
        int id PK
        string lead_id FK
        string s3_key
        int size_bytes
        string content_type
    }

    LeadFeedback {
        int id PK
        string lead_id FK
        string tenant_id
        string outcome
        float actual_price
        float estimated_price
        string override_reason
    }

    PipelineRun {
        int id PK
        string tenant_id
        string lead_id
        string vertical_id
        string trace_id
        string pipeline_name
        string engine_version
        string config_hash
        string status
        string failure_step
        string error_category
        float overall_confidence_score
        string overall_confidence_label
    }

    PipelineStepRun {
        int id PK
        int pipeline_run_id FK
        string step_name
        string step_use
        int step_order
        string status
        json input_snapshot
        json output_snapshot
        float confidence_score
        string confidence_label
        int duration_ms
        string error_category
    }

    ProposedChangeReviewState {
        int id PK
        string tenant_id
        string change_id
        string scope_type
        string status
        json proposal_payload
    }

    ProposedChangeAuditEvent {
        int id PK
        string tenant_id
        string change_id
        string event_type
        datetime occurred_at
        json payload
    }

    EngineEvent {
        int id PK
        string tenant_id
        string lead_id
        string vertical_id
        string trace_id
        int pipeline_run_id
        string event_type
        string status
        json payload
    }

    Tenant ||--o{ User : "has"
    Tenant ||--o{ Lead : "owns"
    Lead ||--o{ LeadFile : "has"
    Lead ||--o| LeadFeedback : "has"
    Lead ||--o{ PipelineRun : "has"
    PipelineRun ||--o{ PipelineStepRun : "has"
    PipelineRun ||--o{ EngineEvent : "emits"
    Tenant ||--o{ ProposedChangeReviewState : "has"
    ProposedChangeReviewState ||--o{ ProposedChangeAuditEvent : "generates"
```

---

## 7. Multi-Tenant Isolation Model

```mermaid
graph TB
    subgraph TENANT_A["Tenant A (construction operator)"]
        LA["Leads"]
        PA["Pipeline Runs"]
        FA["Feedback"]
        CA["Proposed Changes"]
    end

    subgraph TENANT_B["Tenant B (roofing company)"]
        LB["Leads"]
        PB["Pipeline Runs"]
        FB["Feedback"]
        CB["Proposed Changes"]
    end

    subgraph SHARED_DB["Shared PostgreSQL Schema"]
        TBL_L["leads\n(tenant_id column)"]
        TBL_P["pipeline_runs\n(tenant_id column)"]
        TBL_F["lead_feedback\n(tenant_id column)"]
        TBL_C["proposed_change_review_states\n(tenant_id + change_id UNIQUE)"]
    end

    LA --> TBL_L
    PA --> TBL_P
    FA --> TBL_F
    CA --> TBL_C

    LB --> TBL_L
    PB --> TBL_P
    FB --> TBL_F
    CB --> TBL_C

    subgraph ISOLATION["Isolation Enforcement"]
        APP["Application layer\ntenant_id scoping\non every query"]
        JWT["JWT token\ncarries tenant_id"]
        SLUG["Tenant slug\nfor public routing"]
        VALID["@validates sector\nORM-level vertical validation"]
    end

    APP --> TBL_L
    APP --> TBL_P
    JWT --> APP
    SLUG --> APP
    VALID --> SHARED_DB
```

**Isolation model:** Shared-schema multi-tenancy. All tenant data coexists in the same database tables, separated by `tenant_id`. Isolation is enforced at the application query layer, not at the database schema or row-level security layer.

**Unique constraint:** `ProposedChangeReviewState` has a `UNIQUE(tenant_id, change_id)` constraint — one review state per proposed change per tenant, database-enforced.
