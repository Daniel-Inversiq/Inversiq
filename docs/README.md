# Inversiq

![Python](https://img.shields.io/badge/Python-3.11-blue)
![FastAPI](https://img.shields.io/badge/FastAPI-API-green)
![Docker](https://img.shields.io/badge/Docker-ready-blue)
![Architecture](https://img.shields.io/badge/Architecture-Decision%20Infrastructure-orange)
![Status](https://img.shields.io/badge/status-active-success)

**Inversiq is a decision infrastructure platform that turns real-world input into structured, explainable decisions and outputs.**

---

## 🚀 What is Inversiq?

Inversiq automates complex workflows like:

* intake
* pricing
* estimation
* decision-making
* output generation

All through a **single configurable engine**.

---

## 🧠 Core Idea

Instead of:

> AI → output

Inversiq does:

> Input → Rules + AI signals → Decision → Actions → Output

This ensures decisions are:

* explainable
* auditable
* controllable

---

## 🏗️ Layer Architecture

Inversiq is built as a **3-layer system**:

---

### 🔹 Layer 1 — Core Engine

The foundation of everything.

* intake layer (forms, photos, API input)
* processing (validation, vision, structuring)
* workflow orchestration
* decision engine (rules + AI signals)
* pricing engine
* output generation

👉 **All workflows run on the same engine**

---

### 🔹 Layer 2 — Workflows

Each workflow is a **configuration of the engine**, not a new codebase.

A workflow defines:

* input fields
* pricing logic
* business rules
* output templates

**Examples (current focus):**

* painting
* roofing
* solar
* property renovation

👉 New workflow = ~20–30% work
👉 Never a separate system

---

### 🔹 Layer 3 — Go-to-Market

Everything is sold under one brand:

> **Inversiq**

Workflows are:

* landing pages
* not separate products

Examples:

* Inversiq for painting
* Inversiq for roofing
* Inversiq for solar

---

## 🧩 Example Workflows

Current vertical focus:

* painting
* roofing
* solar
* property workflows

Future expansion:

* insurance claims
* damage assessment
* logistics workflows
* financial decisioning

---

## 🧭 Roadmap

### Phase 1 — Construction & Installation (Now)

* painting
* roofing
* solar
* property

### Phase 2 — Insurance & Logistics

* claims workflows
* damage assessment
* freight pricing

### Phase 3 — Finance & Enterprise

* financial workflows
* compliance
* enterprise decisioning

---

## ⚙️ Architecture Overview

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

## 🛠 Tech Stack

* **Backend:** FastAPI, Python
* **Async:** Celery, Redis
* **AI / Data:** PyTorch, NumPy
* **Infra:** Docker, AWS S3
* **Observability:** Prometheus, Grafana

---

## 📁 Project Structure

```text
app/                # API & services
inversiq/           # core decision engine
verticals/          # workflow configurations
```

---

## 🎯 Design Principles

* Explainability first
* Rules over black-box decisions
* Configurable workflows
* One engine for all verticals
* Production-ready by design

---

## 📌 Positioning

> **One engine. Every workflow. Always Inversiq.**
