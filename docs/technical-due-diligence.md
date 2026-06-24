# Technical Due Diligence Report

_Inversiq — June 2026_
_Prepared for: Potential investors and strategic acquirers_
_Basis: Direct analysis of the production codebase_

---

## Executive Assessment

Inversiq has built a technically ambitious and well-structured platform for a real market gap. The codebase shows meaningful architectural maturity: explicit intelligence layers, a formal governance model, multi-tenant data isolation, and a clear evolution path toward a horizontal platform. The painting vertical is production-grade and revenue-generating. The primary technical risks are execution-stage concerns (migration backlog, missing scheduled intelligence runs, the imperative-to-engine-runner migration) rather than architectural flaws. There is no evidence of critical security vulnerabilities or data model decisions that would require significant rework.

**Overall technical risk: Medium-Low** for a company at this stage.

---

## 1. Technology Risk Assessment

### Dependency Stack (Verified against `requirements.txt`)

| Dependency | Assessment |
|---|---|
| FastAPI | Industry-standard Python ASGI framework. Low risk. |
| SQLAlchemy (modern Mapped style) | Modern ORM syntax, well-maintained. Low risk. |
| PostgreSQL 15 | Mature, reliable. Low risk. |
| OpenAI API | **Concentration risk.** Vision inference is fully dependent on OpenAI. Fallback path exists but is limited. If OpenAI degrades or prices increase significantly, vision quality degrades. Mitigated by: fallback provider, local photo quality model. |
| PyTorch/timm/OpenCV | Stable ML stack for local photo quality classifier. Low risk. The local model reduces OpenAI API spend. |
| Stripe | Standard B2B billing. Low risk. |
| Celery + Redis | Standard async task infrastructure. Low risk. |
| WeasyPrint | PDF generation library present but no active PDF generation code found. Low risk (likely dormant). |
| alembic | Listed in requirements.txt but **no migration files exist**. See Technical Debt section. |
| sqlmodel | Listed but codebase uses SQLAlchemy native `Mapped` style. Likely a transitional/legacy dependency. Low risk but worth cleanup. |

### External Service Dependencies

| Service | Criticality | Risk |
|---|---|---|
| OpenAI Vision API | Revenue-critical (drives estimates) | Medium — no viable substitute with same quality at short notice |
| AWS S3 | Revenue-critical (stores estimates and photos) | Low — S3 is highly reliable; local mock exists |
| Stripe | Revenue-critical (billing) | Low — Stripe is highly reliable |
| Gmail OAuth | Feature (outreach) | Low — feature degrades gracefully |

### Language/Runtime Risk

Python 3.11, FastAPI, and SQLAlchemy are well-maintained ecosystem choices with large talent pools. No exotic language choices. Risk is low.

---

## 2. Code Quality Signals

### Positive Signals

**Architectural separation of concerns.** The intelligence layer (anomaly, intelligence, trend, health, reasoning, focus, proposed changes) is entirely pure-function or read-only. This is a strong architectural signal — analysis is decoupled from mutation, making it testable and composable.

**Modern SQLAlchemy patterns.** The codebase uses the modern `Mapped`/`mapped_column` declarative style with `Optional` typing throughout. The `none_as_null=True` on JSON columns (a subtle but important correctness detail) appears in `PipelineStepRun`. This signals attention to data semantics.

**Formal governance model.** The six-model proposed change lifecycle (proposal → review → intent → request → attempt → outcome → audit) is architecturally complete and reflects genuine domain thinking about risk management in automated systems.

**Confidence scoring throughout.** Per-step confidence scores with a weakest-link aggregation model is sophisticated and correct. The `CONFIDENCE_ABSENT_ON_COMPLETION` anomaly detector enforces that this system remains well-instrumented over time.

**Deterministic IDs for proposals.** `change_id = scope_type:scope_id:category:parameter` prevents duplicate proposals and makes the governance system idempotent. Reflects careful system design.

**Security-conscious AWS credential handling.** The startup guard that refuses to start with static AWS keys in environment variables is production-quality security thinking.

**Structured logging.** structlog JSON logging with per-request `request_id`, `tenant_id`, and `latency_ms` binding is the correct pattern for a B2B SaaS platform.

**Multi-tenant data isolation is architecturally embedded** from the first model: `tenant_id` on every entity, slug-based routing, ORM-level sector validation.

### Areas of Concern

**Dutch-language code artifacts.** Variable names, comments, and some model labels are in Dutch (e.g. `schilder`, `offertes`, comments like `// registreert SQLAlchemy modellen`). This is not a quality issue per se but will slow international engineering hiring. Handbook note: first market is the Netherlands. Acceptable at current stage.

**The in-process job runner is a development stub.** `app/jobs/runner.py` polls the `Job` table every 5 seconds and sleeps 2 seconds to "simulate work." This is not a production job processing system. For the current workload (where vision processing runs through Celery), this may be acceptable. It should not be expanded without replacing the `time.sleep(2)` stub.

**Directory name typo.** `app/ml/photo_qualtity/` (not "quality") is a minor issue but suggests the ML directory was not deeply reviewed.

**Disabled router.** `app/routers/app_dashboard.py` is commented out in `main.py`. Its purpose is unclear from the router file name alone. Dead code in the router registration is a minor smell.

**Two pipeline execution paths.** The imperative `painting/pipeline.py` and the formal `inversiq/engine/runner.py` coexist. The engine runner has better observability (EngineEvent emission, structlog integration, Prometheus metrics) but is not yet driving production traffic. This dual path is a known transition state, not a fundamental architectural problem.

**No test files found in the verified paths.** A systematic test suite was not found during repository analysis. This is the most significant code quality concern and is addressed in the Technical Debt section.

---

## 3. Scalability Assessment

### Current Architecture Scalability

**FastAPI + Gunicorn multi-worker:** Scales horizontally. Each worker is stateless except for the in-process job runner thread (which would create duplicate processing with multiple workers — the `SQLALCHEMY_CREATE_ALL_AT_STARTUP=false` comment acknowledges this for SQLite, but the job runner has the same multi-worker concern).

**Database:** Shared-schema multi-tenancy on a single PostgreSQL instance. At current tenant counts, this is entirely appropriate. At significant scale (1000+ tenants with heavy pipeline traffic), the lack of per-tenant sharding or read replicas could become a bottleneck. The data model supports migration to a horizontally partitioned approach without schema redesign.

**OpenAI Vision:** At low-to-medium volume, direct API calls are fine. At high volume, the synchronous vision call in the HTTP request path becomes a latency concern. Celery infrastructure exists for async processing but is not yet wired into the main pipeline path.

**Redis + Celery:** Standard async task infrastructure that scales horizontally. No concerns at current stage.

**S3:** Effectively unlimited storage scale. No concerns.

### Scalability Path

The architecture is well-designed for scale-up:
1. Decouple vision from the HTTP path (Celery already available)
2. Add PostgreSQL read replicas for intelligence/analytics queries
3. Complete the `inversiq.engine` migration for portable, worker-executable pipelines
4. Consider per-tenant data partitioning at very high tenant counts

None of these require architectural rework — they are evolutionary steps on a solid foundation.

---

## 4. Security Posture

### Strengths

- **No static AWS keys:** Machine-enforced at startup. IAM roles required. This is production-grade.
- **Password hashing:** `passlib[bcrypt]` with explicit version pin. Correct.
- **JWT authentication:** Standard implementation.
- **Rate limiting:** SlowAPI middleware protects public endpoints.
- **Pydantic validation:** All FastAPI request bodies are typed and validated.
- **ORM-level validation:** `Tenant.sector` validates against the vertical registry at save time.
- **Sentry integration:** Unhandled exceptions captured with context.

### Concerns

- **Shared-schema multi-tenancy:** Data isolation is enforced at the application layer only. A query bug could expose one tenant's data to another. There is no database-level row security (PostgreSQL RLS). For a platform handling business pricing data, this is an acceptable risk at early stage but should be addressed before enterprise customers with strict compliance requirements.

- **CORS configuration:** `allow_methods=["*"]` and `allow_headers=["*"]` are permissive. This is standard for API-first SaaS where the frontend is the expected CORS origin, but should be reviewed if the API is ever exposed to third-party integrations.

- **BasicAuthMiddleware on `/sales` and `/api`:** The specific scope of basic auth protection and the credentials used were not verified. This needs review in a live environment assessment.

- **No evidence of secret scanning in CI.** No `.github/workflows/` directory was examined. Secret scanning (e.g. detect-secrets, gitleaks) is a best-practice gap if not implemented.

---

## 5. Technical Debt Inventory

### Critical

| Item | Description | Impact |
|---|---|---|
| No Alembic migrations | Schema creation via `create_all()` at startup. `alembic` is in requirements.txt but no migration files exist. | Blocks safe multi-instance production deployment. Any schema change requires manual coordination. |
| No automated test suite found | No test files were encountered during codebase analysis. | Regression risk on any change. Engineering velocity cap as the codebase grows. |

### High

| Item | Description | Impact |
|---|---|---|
| No scheduled intelligence runs | The intelligence loop (anomalies → proposals) is on-demand only. There is no cron job or scheduler. | The platform's core differentiator — continuous improvement — requires manual operator invocation to deliver value. |
| Vision processing in HTTP path | OpenAI Vision API calls are synchronous within the pipeline, blocking the HTTP response. | Latency degrades with photo count. Reliability risk on OpenAI transient errors. |
| In-process job runner is a stub | `app/jobs/runner.py` sleeps 2 seconds to simulate work. | Not production-suitable for any real job processing beyond the current near-zero volume. |

### Medium

| Item | Description | Impact |
|---|---|---|
| Dual pipeline (imperative + engine runner) | Production pipeline is imperative; engine runner is more sophisticated but not active. | Two codepaths to maintain. Engine runner observability improvements not reaching production. |
| No pricing rule governance | Rule changes are file changes. No version history, no diff, no governance connection. | Cannot track which rule version produced which estimate. |
| `sqlmodel` listed but not dominant | SQLModel in requirements.txt; codebase uses SQLAlchemy native style. | Dependency confusion, potential import conflicts. |
| Dutch-language code artifacts | Comments and variable names in Dutch throughout. | International engineering hiring friction. |

### Low

| Item | Description | Impact |
|---|---|---|
| `app/ml/photo_qualtity/` typo | Directory has a spelling error ("qualtity"). | Cosmetic; no functional impact. |
| Disabled dashboard router | `app_dashboard_router` commented out in `main.py`. | Dead import; unclear intent. |
| Grafana not deeply configured | docker-compose.observability.yml provisions Grafana but no dashboard definitions exist. | Monitoring infrastructure provisioned but not operationalized. |

---

## 6. Key Architectural Strengths

**The intelligence loop is architecturally complete.** The full chain from run telemetry through anomaly detection, behavioral pattern detection, trend analysis, health scoring, root-cause reasoning, prioritization, and governed change proposals is implemented. This is not a demo — it is running code with real data models, real database queries, and real governance enforcement.

**Confidence scoring as a first-class system.** Mandatory confidence scores per step, weakest-link aggregation, automated detection of confidence gaps, and confidence-driven review routing is a sophisticated approach to uncertainty management that most production ML-adjacent systems lack.

**Pure function architecture for analysis.** The entire analysis stack (reasoning, trend, focus, proposed changes) is pure functions over data structures. This is testable without infrastructure, composable, and safe for simulation mode. The `/simulation_preview` endpoint exists specifically to leverage this.

**Formal governance model.** The six-model proposed change lifecycle with an immutable audit trail is a production-quality governance system. This reflects genuine domain understanding of the risk profile of automated pricing systems in B2B contexts.

**The `inversiq.engine` package** represents a well-designed second-generation execution layer. The engine runner handles: step contract validation, per-step confidence accumulation, weakest-link aggregation, EngineEvent emission, Prometheus metrics, structlog integration, and error categorization — all in a single composable function. When the migration is complete, the platform will have a significantly more capable execution substrate.

**Multi-tenant isolation is architecturally embedded.** Not added as an afterthought. Every entity has `tenant_id`. ORM-level validation prevents invalid tenant configuration. This is foundational for compliance and trust.

---

## 7. Key Risks and Mitigations

### Risk 1: OpenAI API Concentration

**Risk:** All vision inference depends on OpenAI. A pricing change, service degradation, or API terms change directly impacts product quality.

**Current mitigations:** Fallback provider exists (`fallback_provider.py`). Local photo quality model reduces API call volume. Demo vision path handles zero-photo leads.

**Recommended mitigation:** Design vision provider as a pluggable interface. Evaluate Azure OpenAI Service or Anthropic Vision as alternative providers. The abstraction in `app/services/vision/` makes this feasible.

### Risk 2: Missing Alembic Migrations

**Risk:** Schema changes in production require downtime or careful manual coordination. Multi-instance deployments risk race conditions.

**Mitigation:** Alembic is already in requirements.txt. Setting up migration files is a defined, well-understood engineering task. Low effort, high importance. Should be addressed before first enterprise customer.

### Risk 3: No Automated Test Suite

**Risk:** Every change carries regression risk. Engineering velocity will slow as the codebase grows without test coverage as a safety net.

**Mitigation:** The pure-function architecture of the intelligence and governance layers makes them excellent candidates for unit testing without infrastructure. The reasoning engine, trend engine, focus engine, and proposed changes generator can be tested with zero database dependencies. Starting a test suite here is high leverage.

### Risk 4: Intelligence Loop Not Automated

**Risk:** The platform's competitive differentiation — continuous improvement from feedback — requires manual operator action to trigger. Operators may not consistently run the analysis endpoints.

**Mitigation:** A nightly scheduled job running the intelligence loop and generating proposals is a straightforward addition. The Celery infrastructure is already available. This is a high-priority feature gap.

### Risk 5: Dual Execution Path Maintenance Cost

**Risk:** The imperative pipeline and the engine runner both require maintenance as business logic evolves. A change to pricing logic must be reflected in the active production path.

**Mitigation:** Complete the migration to the engine runner. The `PaintingVertical.get_workflows()` step configuration exists; wiring it to the engine runner requires implementation work but the architecture is clear.

---

## 8. Team and Hiring Considerations

### What the Codebase Tells Us About the Team

The architectural sophistication of the governance model, the intelligence loop design, and the engine runner suggests a technically strong founding team with real domain understanding. The choice of pure-function design for the analysis stack is a senior engineering pattern. The attention to confidence scoring and the weakest-link model reflects careful thinking about uncertainty in automated systems.

The Dutch-language artifacts and the Netherlands-first market positioning suggest a small founding team (possibly 1-2 engineers) working fast on a known market.

### What the First Engineering Hires Need

- **Backend Python experience** (FastAPI, SQLAlchemy, async patterns)
- **Comfort with domain-specific systems** — this is not a generic CRUD app; engineers must understand pricing, uncertainty, and governance concepts
- **Ability to read and reason about explicit rules** — the pricing engine, review decision logic, and reasoning engine are all rule-based code that requires careful reading before modification

### What Would Accelerate the Codebase

A **QA/Test Engineering hire** would have the highest leverage given the absence of an automated test suite. The pure-function architecture means a strong test suite can be built quickly with high coverage without complex infrastructure setup.

A **Data Engineer** would have high leverage on the intelligence loop: scheduled jobs, metrics aggregation, and feedback loop automation.

---

## 9. Roadmap Viability Assessment

### High Confidence (Clear path from current codebase)

- **Complete `inversiq.engine` migration:** Architecture is clear. Step configuration exists. Implementation work is well-defined.
- **Alembic migration setup:** Straightforward. Alembic is already installed.
- **Automated intelligence runs:** Celery infrastructure available. Scheduling is straightforward.
- **Async vision processing:** Celery infrastructure available. Decoupling from HTTP path is a known pattern.

### Medium Confidence (Requires design work)

- **Roofing and Solar pipelines:** Adapters and intake forms exist. Pricing rules, vision prompts, and estimation logic must be built from scratch per vertical. This is the core vertical expansion work.
- **Pricing rule governance in the database:** The proposed change governance infrastructure exists. Moving pricing rules from JSON files to database-versioned artifacts requires careful design.
- **Confidence score calibration:** The feedback loop data exists. Building a calibration mechanism from `LeadFeedback` to threshold adjustment requires statistical design.

### Longer Term (Requires significant work)

- **Multi-vertical lead routing** (one tenant, multiple verticals)
- **Enterprise compliance features** (PostgreSQL row-level security, audit log export, GDPR data deletion)
- **Horizontal platform expansion** (new verticals via config, not code)

### Summary

The roadmap is technically credible. The most valuable near-term items (intelligence loop automation, vision async, engine migration) have clear implementation paths from the current codebase. The vertical expansion roadmap (roofing, solar) requires significant domain work (pricing rules, vision prompts) but follows a well-established pattern set by the painting vertical.

---

_This report is based on direct repository analysis. Findings reflect the state of the codebase at the time of review. Live infrastructure, CI/CD configuration, and operational practices were not assessed. A complete due diligence process should include a live environment review, interview with the engineering team, and assessment of operational metrics from production._
