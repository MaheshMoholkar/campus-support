# Campus Support

A service desk for the software cell of an invented university: staff raise requests, a section authority approves them, a lead assigns them and developers resolve them. A rebuild of an older ticket system, with AI features added milestone by milestone and measured by evals.

All data in this repository is invented.

- Design: [docs/specs/2026-09-30-campus-support-design.md](docs/specs/2026-09-30-campus-support-design.md)
- Status: milestone 1 backend (ticket lifecycle API, no AI yet)

## Run the backend

Needs Postgres with pgvector and an S3-compatible bucket. With the homelab:

```bash
lab up                       # writes .env.lab
cd backend
echo "SESSION_SECRET=$(openssl rand -hex 32)" > .env   # once; signs login cookies
uv sync
uv run alembic upgrade head
uv run python -m app.seed    # invented demo data; password: campus-demo
uv run uvicorn app.main:app --reload --port 8000
```

API docs: http://localhost:8000/docs

Demo logins (`@tarangini.example`): `admin`, `lead`, `dev1`–`dev4`, `approver1`–`approver6`, `reporter1`–`reporter22`.

## Checks

```bash
cd backend
uv run ruff check . && uv run ruff format --check . && uv run pyright && uv run pytest -q
```

Tests use a separate `test` schema in the same database and roll back after each test.
