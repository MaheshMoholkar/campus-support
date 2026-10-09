# Campus Support

Service desk for a university's software cell (raise → approve → assign → resolve), with AI assistance added milestone by milestone and measured by evals. Design: `docs/specs/2026-09-30-campus-support-design.md` (the authority). Plans: `docs/plans/`. Overview and commands: `README.md`.

## How Mahesh works

- Discuss before building: propose, then wait for his go. Short, direct replies.
- No multi-agent fan-outs unless asked. One reviewer at the end of a milestone is fine.
- He is a .NET/React developer; Python, FastAPI and Next.js are newer to him. Explain a non-obvious choice in a line (Alembic ≈ EF migrations, Depends ≈ DI, Pydantic ≈ DTO + validation).
- Infrastructure (homelab, lab project names, databases on the mini) is his: propose, do not rename or destroy. Ask before creating anything outside this repo.
- Public text (README, repo description, docs) is written in the product's own terms: what it does and how. No "portfolio", no origin story, no hedging, no bold marketing tagline. `MaheshMoholkar/meet-ai`'s README is the reference layout.

## Conventions

- Backend layers: routers call one service and `db.commit()`; services `flush()`, never commit. A failed request rolls back everything (see `get_db`).
- `app/services/transitions.py` is the only place a status changes: `(status, action) → rule with a guard`. Missing row → 409, failed guard → 403, hidden ticket → 404.
- `ticket_events` is append-only. Enum columns are plain `VARCHAR` holding the enum value.
- TDD: failing test first, watch it fail, then the code. Table-driven tests for the transition table.
- One commit per plan task, directly on `main` (no feature branches or PRs). Commit only when asked; push only when asked.
- All data is synthetic. The screenshots of the old system on the Desktop hold real names, phones and emails: read for layout only, copy nothing.

## Commands (in `backend/`)

```
uv run ruff format . && uv run ruff check . && uv run pyright && uv run pytest -q
uv run alembic upgrade head              # dev database
uv run python -m app.seed [--reset]      # synthetic data; password campus-demo
uv run uvicorn app.main:app --reload --port 8000
```

- Tests need Postgres: they migrate a `test` schema (own Alembic version table) and roll back per test. Against the mini the suite takes 1–4 minutes; each round trip is 10–110 ms, so batch fixture inserts.
- `SESSION_SECRET` is required (32+ chars) and lives in `backend/.env` (git-ignored). Postgres and S3 variables come from `.env.lab`, written by `lab up` (homelab project `campus_support`, bucket `campus-support-attachments`).
- CI (`.github/workflows/ci.yml`) runs the same checks on a fresh pgvector database.

## Status

- Milestone 1 backend: merged (PR #1). Deferred review items: issue #2.
- Next: milestone 1 frontend. Design proposed in chat, not yet approved. Proposed: Next.js App Router + TypeScript strict + Tailwind + shadcn/ui; types from `/openapi.json` via `openapi-typescript` and calls via `openapi-fetch`; TanStack Query; react-hook-form + zod; Next.js rewrite `/api/*` → FastAPI (`API_URL`); `middleware.ts` redirects to `/login` when the `cs_session` cookie is absent, the backend stays the authority; routes `/login`, `/tickets/new`, `/my-reports`, `/approvals`, `/register`, `/my-tickets`, `/tickets/[id]`, `/dashboard`, `/admin/*`; uploads by presign + browser `fetch(PUT)`; timer counts up client-side from `seconds_spent`; one Playwright path reporter → approver → lead → developer → closed on seeded accounts; CI jobs `frontend` (lint, tsc, build) and `e2e`. Not in M1: AI panel, similar tickets, dark mode.
  On his go: write `docs/plans/2026-09-30-m1-frontend.md` with superpowers:writing-plans, then execute natively with one reviewer at the end.
- Homelab side: a `labd` HTTP service on the mini is planned in `MaheshMoholkar/homelab` (issue #1); the prompt for that session was handed to Mahesh. Until it exists, `lab up` from this folder is how services are provisioned.
