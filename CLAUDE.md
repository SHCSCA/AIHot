# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

情报引擎 (Intelligence Engine) is a production-grade AI + Amazon seller intelligence platform that transforms public information sources into retrievable, explainable, distributable, and back-testable Chinese intelligence assets.

**Channels**: `ai` (AI models, products, Agent tools, papers, industry dynamics) and `amazon` (Amazon seller operations, account health, FBA/logistics, ads/PPC, Listing/SEO, fees, compliance).

## Quick Start

```powershell
# Install
python -m venv .venv
.\.venv\Scripts\python -m pip install -e ".[dev]"

# Run tests
.\.venv\Scripts\python -m pytest -v

# Start API (port 8000)
.\.venv\Scripts\python -m uvicorn intel_engine.main:app --host 127.0.0.1 --port 8000

# Start frontend (port 5173)
cd web
npm install
npm run dev

# Frontend verification
cd web
npm test -- --run
npm run build

# Start pipeline worker
.\.venv\Scripts\intel-engine pipeline-once

# Seed sources
.\.venv\Scripts\intel-engine seed-sources

# Run a single test
.\.venv\Scripts\python -m pytest tests/test_scoring.py -v
```

## Architecture

### Pipeline Flow
```
Source Registry → Scheduler → Fetch Workers → Raw Documents
→ Normalizer → PreScreener → LLM Score/Translation
→ Rank Policy → Event Cluster → Web/RSS/API/Skill/Daily Digest
```

### Core Modules (`src/intel_engine/`)
- `main.py`, `routes.py` - FastAPI app and all API endpoints
- `pipeline.py` - Orchestrates the complete ETL pipeline (fetch, normalize, screen, score, rank, cluster)
- `scheduler.py`, `jobs.py` - Job queue management with `FOR UPDATE SKIP LOCKED`
- `fetchers/` - Fetch adapter registry (RSS, HTTP, GitHub, API, Playwright)
- `llm.py` - LLM provider adapter (fake, deepseek); all output validated via Pydantic
- `prescreen.py`, `review.py` - Pre-filtering and auto-review decision logic
- `scoring.py`, `rank_policy.py` - Multi-dimensional scoring and deterministic ranking
- `clustering.py` - Event clustering with embedding support
- `normalizer.py` - URL canonicalization and content hashing
- `daily.py` - Daily digest generation
- `models.py` - SQLAlchemy 2 models (20+ tables with constraints, indexes)
- `db.py` - Database engine/session management

### Web Frontend (`web/src/`)
- React 19 + TypeScript + Vite
- Reader / Ops / Lab shell in `App.tsx`
- Public Reader routes: `/`, `/selected`, `/all`, `/daily`, `/rss`, `/sources`, `/feedback`
- Protected admin routes under `/admin/...`
- Ops views: Dashboard, Sources, Jobs, Health, Quality, Events Review, Daily Digests, Feedback, Admin Access
- Lab views: Strategies, Evaluations
- Global Cmd+K command palette from `PublicFrontPage/CmdKPanel.tsx`
- Liquid Glass design tokens and motion rules live in `web/src/styles.css`

### UI Direction
- Keep the product as a restrained Liquid Intelligence Glass intelligence workstation.
- Use glass for navigation, floating overlays, hero/brief regions, decision panels, login portal, Cmd+K, and light public cards.
- Keep dense tables, long daily text, and forms high-opacity for readability.
- Preserve both light and dark themes. Any motion must degrade under `prefers-reduced-motion`.
- Do not invent frontend fields that are absent from `web/src/types.ts` or API responses.

### Data Model (key tables)
`sources` → `source_states`, `fetch_jobs`, `fetch_runs`, `raw_documents`
→ `normalized_items` → `raw_screening_results`, `prefilter_results`, `model_scores`
→ `ranked_items` → `event_clusters` ← `cluster_members`
→ `daily_digests`, `feedback_events`, `evaluation_runs`

## Key Patterns

### LLM Provider Pattern
```python
# Providers implement: score_item(), prefilter_item(), translate_item()
# Output must pass Pydantic schema validation before DB write
llm_provider = build_scoring_provider(settings)
score = llm_provider.score_item(payload)
```

### Pipeline Worker Pattern
```python
# Workers claim jobs with SKIP LOCKED for concurrent execution
jobs = claim_fetch_jobs(session, worker_id=worker_id, limit=1)
# Each job: fetch → normalize → screen → score → rank → cluster
```

### Rank Policy
LLM does NOT decide `selected` directly. `RankPolicy.evaluate()` uses deterministic formula:
- source_weight, category_weight, freshness_weight, duplicate_penalty, channel_impact_weight
- Final score must exceed threshold; only DeepSeek results can be `selected`

### RBAC System
- Roles: `admin`, `editor`, `viewer`, `ops`, `guest`
- Permissions via `role_permissions` join table
- Sessions stored in `sessions` table with expiration

## Configuration

Environment variables:
- `DATABASE_URL` - PostgreSQL production database
- `ADMIN_USERNAME`, `ADMIN_PASSWORD` - Basic auth for admin API
- `LLM_PROVIDER` - `fake` (default) or `deepseek`
- `LLM_MODEL`, `DEEPSEEK_API_KEY` - Model configuration
- `AIHOT_DEPLOY_KEY` - optional local path to the SSH key used by `scripts/deploy-aihot.ps1`; never commit keys

## Key Files
- `pyproject.toml` - Python package config, dependencies
- `channels/ai.yaml`, `channels/amazon.yaml` - Source registry per channel
- `docs/ARCHITECTURE.md` - Full architecture documentation
- `docs/API.md` - API specification
- `docs/RUNBOOK.md` - Local verification and deployment runbook
- `scripts/deploy-aihot.ps1` - Bundle-based deploy script for the production server
- `alembic.ini` - Database migration config
