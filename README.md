# Elitze Money Engine

Production-oriented autonomous revenue experimentation platform.

A single, end-to-end pipeline that **discovers**, **qualifies**, **models**,
**budgets**, **executes**, **measures**, **evaluates**, **improves**, **tests**,
**promotes/kills**, and **reinvests** revenue experiments — with real money
movements tracked in a verified, auditable ledger.

> **Real execution only.** No fabricated revenue. Simulated results are
> explicitly labeled and can never be promoted or counted as real earnings.

---

## Quick start

```bash
python -m venv .venv && source .venv/bin/activate
pip install -e .

# 1. Seed the reinvestment pool with verified capital (operator action)
elitze seed 1000

# 2. Run a real experiment (real spend, real budget checks)
elitze run saas --title "Waitlist micro-SaaS" \
    --rollback "Revert landing page and pause ad spend within 1 hour"

# 3. Run a labeled paper (simulation) — never promotable
elitze run lead_generation --title "Paper pilot" --paper

# 4. Inspect state
elitze pool          # reinvestment pool balance
elitze list          # all experiments
elitze show <id>     # full experiment record
```

Run the dashboard + HTTP API:

```bash
elitze serve          # http://localhost:8000
```

---

## Architecture

| Layer           | Technology                                                       |
|-----------------|------------------------------------------------------------------|
| Runtime/agents  | OpenClaw-style persistent agent runtime + durable task queue      |
| Orchestration   | LangGraph state machine (`DISCOVER → … → REINVEST`)              |
| Evaluation      | NeMo-style profiling hooks (verdict, profile, benchmark scores)  |
| Inference       | NVIDIA NIM (chat + embeddings) with deterministic offline fallback |
| Truth store     | PostgreSQL (production) / SQLite (local default) via SQLAlchemy   |
| Semantic memory | Qdrant (server or embedded local)                                |
| Knowledge       | Obsidian-style Markdown vault                                    |

### Core loop

```
DISCOVER → QUALIFY → MODEL → BUDGET → EXECUTE → MEASURE → EVALUATE
   → IMPROVE → TEST → PROMOTE/KILL → REINVEST
```

Real-mode runs execute exactly once (real spend). The recursive
IMPROVE/TEST loop benchmarks candidate versions on paper, so no money is
double-spent; promoted versions are run as their own budgeted experiment.

### Data model

Every experiment records (first-class, queryable columns):

- strategy ID, version, parent strategy
- execution cost, revenue, profit, ROI, conversion rate
- execution time, failures
- policy result, promotion status
- rollback plan

---

## Revenue integrity

Revenue enters the ledger **only** through verified external events:

- **Signed webhooks** — HMAC-SHA256 (`X-Hub-Signature-256`). Rejected (401)
  if unsigned, mis-signed, or when no `ELITZE_WEBHOOK_SECRET` is configured
  (fail-closed).
- **Integrations / manually-verified** sources.

Example webhook:

```bash
SECRET=test-secret-123
BODY='{"event_id":"evt_1","experiment_id":"<id>","amount":"450.00","currency":"USD"}'
SIG="sha256=$(printf '%s' "$BODY" | openssl dgst -sha256 -hmac "$SECRET" | cut -d' ' -f2)"

curl -X POST "http://localhost:8000/revenue/webhook/stripe" \
  -H "Content-Type: application/json" \
  -H "X-Hub-Signature-256: $SIG" \
  -d "$BODY"
```

Ingested revenue automatically reconciles the experiment's revenue/profit/ROI.

---

## Revenue engines

- Lead generation
- B2B services
- Digital products
- Affiliate marketing
- Market intelligence
- Software/SaaS opportunities

---

## Safety boundary

The system is designed for lawful revenue generation and authorized
automation. It does **not** automate fraud, credential theft, malware,
unauthorized access, spam, platform-control evasion, identity theft, market
manipulation, or abusive exploitation. Policy checks run before execution,
budgeting, and promotion; every action is auditable and production changes
require a rollback plan.

---

## Configuration

Copy `.env.example` to `.env`. Every setting is optional with a safe local
default:

| Variable | Default | Purpose |
|---|---|---|
| `ELITZE_DATABASE_URL` | SQLite under `ELITZE_DATA_DIR` | truth store (Postgres for prod) |
| `ELITZE_QDRANT_URL` | embedded local | semantic retrieval server |
| `ELITZE_NIM_API_KEY` | unset | NVIDIA NIM inference |
| `ELITZE_LLM_BACKEND` | `auto` | `auto` / `nim` / `dry` |
| `ELITZE_WEBHOOK_SECRET` | unset | revenue webhook HMAC (required to accept revenue) |
| `ELITZE_MAX_EXPERIMENT_BUDGET` | `5000.00` | per-experiment spend cap |
| `ELITZE_MAX_DAILY_BUDGET` | `10000.00` | daily spend cap |
| `ELITZE_MAX_ITERATIONS` | `3` | paper improve/test iterations |

---

## HTTP API

| Method | Path | Description |
|---|---|---|
| `GET` | `/` | Dashboard |
| `GET` | `/health` | Liveness + active LLM backend |
| `GET` | `/experiments` | List experiments (filter by status/engine) |
| `GET` | `/experiments/{id}` | Full experiment record |
| `POST` | `/experiments/run` | Run an experiment |
| `GET` | `/pool` | Reinvestment pool balance |
| `POST` | `/pool/seed` | Seed verified capital (operator) |
| `POST` | `/revenue/webhook/{provider}` | Verified revenue ingestion |
| `GET` | `/agents` | Registered agents |

---

## Development

```bash
pip install -e ".[dev]"
pytest            # unit + end-to-end loop tests
ruff check src tests
```

Tests run against an isolated SQLite database and never touch real data.

## Status

End-to-end implementation of the core loop, verified ledger, revenue
ingestion, policy guardrails, CLI, HTTP API, and dashboard. NVIDIA NIM,
PostgreSQL, and Qdrant-server integrations are wired via config; the engine
runs fully offline with deterministic fallbacks.
