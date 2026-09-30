# Campus Support

Service desk for a university's software cell: staff at any institute raise
requests, a section authority approves them, a lead assigns them and
developers resolve them. Milestone 1 is the API for that lifecycle. The web
app and the AI assistance (classification, a completeness check at submit,
suggested assignee, duplicate detection, each measured by an eval set in CI)
follow milestone by milestone.

| Part | What |
|---|---|
| `backend/` | FastAPI (Python 3.14), SQLAlchemy 2, Alembic, Pydantic |
| Postgres 17 + pgvector | data; vector search from milestone 4 |
| S3-compatible store | attachments through presigned URLs (Garage in development) |
| `frontend/` | Next.js; next up |

## Features

- **Lifecycle**: Pending For Approval → Waiting in Queue → In Process →
  Ticket Closed, plus Rejected By Authority and three "waiting on the
  reporter" statuses (Clarification Required, Insufficient Data, Poor Quality
  Images) that return the ticket to where it was.
- **Roles**: reporter, approver (per section), lead, developer, admin.
  Internal tickets raised by developers skip approval.
- **Timeline**: every status change, assignment, estimate change and message
  in one append-only table.
- **Timer**: developers start, pause and resume; time spent is the sum of the
  segments.
- **Attachments** on tickets, messages and replies, uploaded by the browser
  straight to object storage.
- **Register** with filters, bulk assign, a dashboard, and admin pages for
  institutes, sections, ERP modules and users.
- **Seed**: 22 institutes, 34 users and 120 tickets with full histories.

## Requirements

- Python 3.14 with [uv](https://docs.astral.sh/uv/)
- Postgres 17 with pgvector, for example:

  ```bash
  docker run -d --name campus-db -p 5432:5432 -e POSTGRES_USER=campus \
    -e POSTGRES_PASSWORD=campus -e POSTGRES_DB=campus_support pgvector/pgvector:pg17
  ```

- An S3-compatible store for attachments (Garage, MinIO or S3) with one
  bucket and a CORS rule that allows `PUT` from the browser's origin. Only
  attaching a file needs it.

## Getting started

```bash
cd backend
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
uv run alembic upgrade head
uv run python -m app.seed        # demo users and tickets; password: campus-demo
uv run uvicorn app.main:app --reload --port 8000
```

Open http://localhost:8000/docs and log in (`POST /api/v1/auth/login`) as
`lead@tarangini.example` / `campus-demo`. The other accounts are `admin`,
`dev1`–`dev4`, `approver1`–`approver6` and `reporter1`–`reporter22` at the same
domain.

With the [homelab](https://github.com/MaheshMoholkar/homelab): `lab up` in the
repo root writes `.env.lab` with the Postgres and S3 variables, and only
`SESSION_SECRET` goes in `backend/.env`.

| Command | |
|---|---|
| `uv run pytest -q` | tests against a real Postgres (a `test` schema in the same database, rolled back per test) |
| `uv run ruff check . && uv run ruff format --check . && uv run pyright` | lint, formatting, types |
| `uv run alembic revision --autogenerate -m "..."` | a new migration from the models |
| `uv run python -m app.seed --reset` | wipe the data and seed again |

## How it works

### Lifecycle

- One transition table (`app/services/transitions.py`), keyed by (status,
  action), with a guard per row: "the approver of this section", "the
  assignee", "the lead". A missing row is a 409, a failed guard a 403. It is
  the only code that changes a status, and the ticket detail uses it to tell
  the client which actions the viewer may take.
- A side status remembers `previous_status`; the reporter's reply returns the
  ticket there. Leaving In Process for any reason stops the timer, and it does
  not restart on its own.
- Two actions on one ticket at the same time are serialised by a row lock;
  a partial unique index allows one open timer segment per ticket.

### Requests

- Routers call a service and commit; services flush. A failed request rolls
  back everything it did, attachments included.
- Every transition is `POST /api/v1/tickets/{id}/actions/{action}` with one
  body shape (remark, side status, assignee, estimate, attachment keys).
- Ticket creation is one function taking a `source` (web, internal, later
  api) that decides the entry status, so an external client can create
  tickets through the same path later.

### Auth

- Own accounts: argon2 password hashes, a signed token in an httpOnly
  SameSite=Lax cookie (12 hours). The role is read from the database on every
  request, so deactivating a user takes effect at once. Login takes the same
  time whether or not the email exists.

### Attachments

- The API issues a presigned `PUT` URL under `uploads/<user>/<uuid>/`; the
  browser uploads; the ticket, message or reply then names the keys. Before
  recording one, the API checks the key's shape, that the object exists, its
  size (10 MB) and type, and that it is not already attached. Downloads
  redirect to a presigned `GET` after a visibility check.

### Tests

- pytest against Postgres: the migrations are applied to a `test` schema with
  its own Alembic version table, every test runs inside a transaction that is
  rolled back, and the API is exercised through FastAPI's test client on the
  same session. A test that reaches a database route without that fixture
  fails instead of touching the development tables.

## Project layout

```
backend/app/core       settings, database, enums, auth, dependencies, errors
backend/app/models     SQLAlchemy models
backend/app/schemas    request and response models
backend/app/services   rules: transitions, tickets, timer, attachments, dashboard, admin
backend/app/routers    HTTP only
backend/alembic        migrations
backend/tests          pytest
docs/specs, docs/plans design and milestone plans
lab.yml                homelab services for development
```

## Roadmap

| Milestone | |
|---|---|
| 1 | Lifecycle API (done); web app (next) |
| 2 | Classification of ticket for, type and ERP module; suggested assignee with confidence gating; every prediction and the human's decision logged |
| 3 | Completeness check before a ticket is filed |
| 4 | Similar and duplicate tickets with pgvector |
| 5 | Eval set and a CI gate on accuracy |

## Notes

- The demo data is synthetic: Tarangini University and its people do not
  exist.
- Not included yet: notifications, reopening a closed ticket, public hosting.
