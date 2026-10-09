# Campus Support

A service desk for a university's software cell. Staff at any institute raise requests, a section authority approves them, a lead assigns them and developers resolve them, with every step recorded on the ticket's timeline.

The API for that lifecycle is built. The web app comes next, then AI assistance: classification, a completeness check at submit, a suggested assignee and duplicate detection, each measured by an eval set in CI.

[![CI](https://github.com/MaheshMoholkar/campus-support/actions/workflows/ci.yml/badge.svg)](https://github.com/MaheshMoholkar/campus-support/actions/workflows/ci.yml)
![FastAPI](https://img.shields.io/badge/FastAPI-Python_3.14-009688)
![PostgreSQL 17](https://img.shields.io/badge/PostgreSQL-17-336791)

## Features

- **Lifecycle**: Pending For Approval → Waiting in Queue → In Process → Ticket Closed, plus Rejected By Authority and three "waiting on the reporter" statuses (Clarification Required, Insufficient Data, Poor Quality Images) that return the ticket to where it was.
- **Roles**: reporter, approver (per section), lead, developer and admin. Internal tickets raised by developers skip approval.
- **Timeline**: every status change, assignment, estimate change and message in one append-only record.
- **Timer**: developers start, pause and resume; time spent is the sum of the segments.
- **Attachments** on tickets, messages and replies, uploaded by the browser straight to object storage.
- **Register** with filters and bulk assign, a dashboard, and admin pages for institutes, sections, ERP modules and users.
- **Demo data**: 22 institutes, 34 users and 120 tickets with full histories.

## How it works

1. A **reporter** raises a ticket. It waits for the **approver** of its section, unless a developer raised it internally.
2. Every action is one call, `POST /api/v1/tickets/{id}/actions/{action}`, checked against a single **transition table**: each (status, action) pair has a rule saying who may take it. A missing pair is a 409, a failed rule a 403.
3. The **lead** assigns approved tickets; the **developer** works them with a timer, asks the reporter for more information when needed, and closes them.
4. Every change lands on the ticket's **timeline**. The ticket detail tells the client which actions the viewer may take next.
5. **Attachments** go from the browser straight to S3-compatible storage through presigned URLs; the API checks each one before recording it.

| Piece | In development |
|---|---|
| API | FastAPI, run with uvicorn |
| Database | Postgres 17 with pgvector (Docker, or the homelab) |
| Attachments | Garage, MinIO or S3 |

### Design choices

- **One place changes a status.** The transition table (`app/services/transitions.py`) is the only code that does; side statuses remember where to return to.
- **All or nothing.** Routers call one service and commit; services only flush. A failed request rolls back everything it did, attachments included.
- **Safe under concurrency.** Two actions on one ticket are serialised by a row lock, and the database allows only one open timer segment per ticket.
- **Sessions.** Argon2 password hashes and a signed token in an httpOnly cookie. The role is read from the database on every request, so deactivating a user takes effect at once, and login takes the same time whether or not the email exists.
- **Ready for other sources.** Ticket creation takes a `source` (web, internal, later an API) that decides the entry status, so an external client can create tickets through the same path.

## Tech stack

| Area | Tools |
|---|---|
| API | FastAPI, Python 3.14, SQLAlchemy 2, Alembic, Pydantic |
| Data | PostgreSQL 17 + pgvector, S3-compatible object storage |
| Auth | Argon2, signed session cookie |
| Testing | pytest against a real Postgres |
| Quality | ruff, pyright |
| Infrastructure | Docker, GitHub Actions |

## Run it locally

### Requirements

- Python 3.14 with [uv](https://docs.astral.sh/uv/)
- Postgres 17 with pgvector, for example:

  ```bash
  docker run -d --name campus-db -p 5432:5432 -e POSTGRES_USER=campus \
    -e POSTGRES_PASSWORD=campus -e POSTGRES_DB=campus_support pgvector/pgvector:pg17
  ```

- An S3-compatible store (Garage, MinIO or S3) with one bucket and a CORS rule that allows `PUT` from the browser's origin. Only attaching a file needs it.

### 1. Install and configure

```bash
git clone https://github.com/MaheshMoholkar/campus-support.git
cd campus-support/backend
cat > .env <<EOF
DATABASE_URL=postgresql://campus:campus@localhost:5432/campus_support
SESSION_SECRET=$(openssl rand -hex 32)
S3_ENDPOINT=http://localhost:3900
S3_REGION=garage
S3_ACCESS_KEY_ID=...
S3_SECRET_ACCESS_KEY=...
S3_BUCKET_ATTACHMENTS=attachments
EOF
uv sync
```

With the [homelab](https://github.com/MaheshMoholkar/homelab), `lab up` in the repo root writes `.env.lab` with the Postgres and S3 variables, and only `SESSION_SECRET` goes in `backend/.env`.

### 2. Start it

```bash
uv run alembic upgrade head
uv run python -m app.seed        # demo users and tickets
uv run uvicorn app.main:app --reload --port 8000
```

### 3. Try it

Open <http://localhost:8000/docs> and log in (`POST /api/v1/auth/login`) as `lead@tarangini.example`, password `campus-demo`. The other accounts are `admin`, `dev1`–`dev4`, `approver1`–`approver6` and `reporter1`–`reporter22` at the same domain.

## Configuration

Settings come from `backend/.env` and, with the homelab, `.env.lab`.

| Variable | What it controls |
|---|---|
| `DATABASE_URL` | The Postgres database |
| `SESSION_SECRET` | Signs session cookies; required, at least 32 characters |
| `SESSION_HOURS`, `COOKIE_SECURE` | Session length (default 12 hours) and HTTPS-only cookies |
| `S3_ENDPOINT`, `S3_REGION`, `S3_ACCESS_KEY_ID`, `S3_SECRET_ACCESS_KEY`, `S3_BUCKET_ATTACHMENTS` | Attachment storage |

## Tests

```bash
cd backend
uv run pytest -q                                                  # against a real Postgres
uv run ruff check . && uv run ruff format --check . && uv run pyright   # lint, formatting, types
uv run python -m app.seed --reset                                 # wipe the data and seed again
```

Tests apply the migrations to a separate `test` schema and roll back every test, so they never touch the development data. CI runs the same checks on a fresh database ([`.github/workflows/ci.yml`](.github/workflows/ci.yml)).

## Project structure

```
backend/
  app/core       settings, database, enums, auth, dependencies, errors
  app/models     SQLAlchemy models
  app/schemas    request and response models
  app/services   rules: transitions, tickets, timer, attachments, dashboard, admin
  app/routers    HTTP only
  alembic        migrations
  tests          pytest
docs/            design and milestone plans
lab.yml          homelab services for development
```

## Roadmap

| Milestone | |
|---|---|
| 1 | Lifecycle API (done); web app (next) |
| 2 | Classification of ticket for, type and ERP module; suggested assignee with confidence gating; every prediction and the human's decision logged |
| 3 | Completeness check before a ticket is filed |
| 4 | Similar and duplicate tickets with pgvector |
| 5 | Eval set and a CI gate on accuracy |

The demo data is synthetic: Tarangini University and its people do not exist. Not included yet: notifications, reopening a closed ticket, public hosting.
