# Inversiq

![Python](https://img.shields.io/badge/Python-3.11-blue)
![FastAPI](https://img.shields.io/badge/FastAPI-API-green)
![Docker](https://img.shields.io/badge/Docker-ready-blue)
![Architecture](https://img.shields.io/badge/Architecture-AI%20Operating%20System-orange)
![Status](https://img.shields.io/badge/status-active-success)

**Inversiq is the AI Operating System for Operational Industries.**

---

## What is Inversiq?

Inversiq automates complex operational workflows:

* intake and document processing
* pricing and estimation
* decision-making and review routing
* output generation and delivery

All through a **single configurable engine** — one platform, any operational industry.

---

## Core Idea

Instead of:

> AI → output

Inversiq does:

> Input → Rules + AI signals → Decision → Actions → Output

This ensures decisions are:

* explainable
* auditable
* controllable

---

## Layer Architecture

Inversiq is built as a **3-layer system**:

---

### Layer 1 — Core Engine

The foundation of everything.

* intake layer (forms, documents, API input)
* processing (validation, vision, structuring)
* workflow orchestration
* decision engine (rules + AI signals)
* pricing engine
* output generation

**All workflows run on the same engine.**

---

### Layer 2 — Vertical Workflows

Each vertical is a **configuration of the engine**, not a separate codebase.

A vertical defines:

* intake fields and document types
* pricing logic and business rules
* review and escalation thresholds
* output templates

**Current verticals:**

| Vertical | Status |
|---|---|
| Construction | Live |
| Insurance | Preview |
| Logistics | Preview |
| Real Estate | Preview |

New vertical = ~20–30% incremental work. Never a separate system.

---

### Layer 3 — Go-to-Market

Everything is sold under one brand:

> **Inversiq**

---

## Architecture Overview

```text
Input
  ↓
Validation & Processing
  ↓
Rule Evaluation
  ↓
AI Signals
  ↓
Decision State
  ↓
Actions
  ↓
Output
```

---

## Tech Stack

* **Backend:** FastAPI, Python 3.11
* **Async:** Celery, Redis
* **AI / Vision:** OpenAI Vision API
* **Infra:** Docker, AWS S3
* **Observability:** Prometheus, Grafana
* **Frontend:** Next.js, TypeScript

---

## Project Structure

```text
app/                # API, routers, services
inversiq/           # core decision engine
app/verticals/      # vertical workflow implementations
frontend/           # operator dashboard (Next.js)
```

---

## Design Principles

* Explainability first
* Rules over black-box decisions
* Configurable vertical workflows
* One engine for all industries
* Production-ready by design

---

## Positioning

> **Inversiq is the AI Operating System for Operational Industries.**
