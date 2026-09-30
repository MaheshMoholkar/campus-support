# Campus Support: design

Date: 2026-09-30
Status: approved in discussion, awaiting review of this document

## 1. Purpose

Campus Support is a service desk for the software development cell of an invented university. Staff from any institute raise requests, a section authority approves them, a lead assigns them and developers resolve them. It is a rebuild of an older ASP.NET WebForms ticket system, with four AI features added.

It has two goals:

1. A complete, working ticket lifecycle (raise, approve, assign, resolve, track).
2. AI features built properly: rules where rules are enough, the LLM only when the input is ambiguous, every prediction logged, and accuracy measured by an eval set that gates CI.

### In scope for v1

- Full lifecycle including the approval step and the clarification loops.
- Five roles: reporter, approver, lead, developer, admin.
- All six "Ticket For" categories and all eight ticket types.
- Timeline thread, attachments, timer-based time tracking, register with filters, "my reports", "my tickets", a basic dashboard.
- Internal tickets (raised by developers or the lead), in minimal form.
- Four AI features: classification, suggested assignee, completeness check, similar/duplicate detection.
- Eval set with thresholds, run in CI, results in the README.

### Deferred

- Daily report generation.
- Suggested estimate time from similar past tickets.
- The link from Campus Helpdesk (a separate RAG assistant) that would create tickets through the API. Section 6.3 keeps the door open; nothing is built.
- Reopening a closed ticket.
- Email or push notifications.
- Public hosting. The demo runs locally against the homelab.

## 2. Roles

Each user has exactly one role.

| Role | Can do | Can see |
|---|---|---|
| reporter | Create tickets, reply in the thread, answer information requests | Own tickets |
| approver | Approve, reject or request information, with a remark | Tickets of their approval section |
| lead | Assign, bulk assign, reassign, set the estimate, confirm or override AI suggestions, request information, create internal tickets | All tickets, register, dashboard |
| developer | Start, pause, resume and close assigned tickets, request information, post messages, create internal tickets | All tickets, "my tickets" |
| admin | Manage users, institutes, approval sections, ERP modules and AI thresholds | Everything |

## 3. Ticket lifecycle

### 3.1 Statuses

Main: Pending For Approval, Waiting in Queue, In Process, Ticket Closed.
Side (waiting on the reporter): Clarification Required, Insufficient Data, Poor Quality Images.
Final: Ticket Closed, Rejected By Authority.

### 3.2 Transitions

| From | Action | Who | To |
|---|---|---|---|
| (new) | submit, source `web` or `api` | reporter | Pending For Approval |
| (new) | submit, source `internal` | developer, lead | Waiting in Queue |
| Pending For Approval | approve, with remark | approver of the section | Waiting in Queue |
| Pending For Approval | reject, with remark | approver of the section | Rejected By Authority |
| Pending For Approval | request information | approver of the section | one of the three side statuses |
| Waiting in Queue | assign or reassign | lead, or the AI above the confidence threshold | Waiting in Queue, assignee set |
| Waiting in Queue | request information | lead, assignee | one of the three side statuses |
| Waiting in Queue | start ticket | assignee | In Process, timer starts |
| In Process | pause, resume | assignee | In Process |
| In Process | request information | assignee | one of the three side statuses |
| In Process | reassign | lead | Waiting in Queue, new assignee set |
| In Process | close, with resolution note | assignee | Ticket Closed |
| any side status | reply | reporter | the status the ticket came from |

Rules:

- A ticket that has been assigned but not started stays in Waiting in Queue, with the assignee shown, as in the old system.
- When a ticket enters a side status it stores the status it came from in `previous_status`; the reporter's reply returns it there.
- The timer stops automatically when a ticket leaves In Process for any reason (side status, reassign, close).
- Anyone who can see a ticket can post a message on it while it is not final.
- A reply may carry attachments, the same way a message can (for example clearer images after Poor Quality Images). No other action takes attachments.
- A ticket in a side status cannot be reassigned; the lead reassigns after the reporter replies.
- All transitions are defined in one table in code, keyed by (current status, action, role). Anything not in the table is rejected. This is the only place status changes happen.

## 4. Data model

| Table | Purpose | Notable columns |
|---|---|---|
| `institutes` | The 20+ institutes | name, short code |
| `approval_sections` | Units whose authority approves tickets | name |
| `users` | Everyone who logs in | name, email, password hash, role, institute, approval section (approvers), extension, contact number |
| `erp_modules` | ERP modules for classification | name, URL prefix |
| `tickets` | One row per ticket | number (`CS-000123`), source (`web`, `internal`, `api`), reporter, institute, approval section (null for internal tickets), ticket_for, ticket_type, erp_module (nullable), page_url, description, contact number, extension, status, previous_status, assignee, estimate_minutes, created/updated/closed timestamps |
| `ticket_events` | Append-only history | ticket, actor, event type (status change, message, assign, reassign, estimate change), from/to values, remark or message body, for assignments: who or what suggested it (`lead`, `ai`) |
| `attachments` | Files on a ticket or message | ticket, event (nullable), storage key, file name, MIME type, size |
| `work_sessions` | Timer segments | ticket, developer, started_at, stopped_at |
| `ai_predictions` (milestone 2) | Every AI output and what the human did with it | ticket, feature, method (`rule`, `llm`, `embedding`), predicted value, confidence, outcome (`accepted`, `overridden`, `ignored`), final value, model id, prompt version |
| embedding column on `tickets` (milestone 4) | pgvector column for similarity search | dimension fixed by the chosen embedding model |

Notes:

- Ticket For (six values) and Ticket Type (eight values) are fixed enums in code, not tables. They do not change at runtime.
- `ticket_events` is the single source for the timeline UI, the audit trail and the reassignment accuracy signal. It exists from milestone 1 so no history has to be backfilled.
- Time spent on a ticket is the sum of its `work_sessions`.
- Schema changes go through Alembic migrations from the first commit.

## 5. Architecture

### 5.1 Repository layout

One repository:

```
backend/     FastAPI app: app/{routers,services,models,schemas,ai,core}, alembic/, tests/
frontend/    Next.js app
evals/       datasets, runner, thresholds
docs/specs/  this document and later specs
lab.yml      homelab services for development
.github/workflows/
```

### 5.2 Backend

- Python, FastAPI, SQLAlchemy 2, Alembic, Pydantic. `uv` for dependency management, ruff for lint and format, pytest for tests.
- Three layers: routers (HTTP only), services (business rules and the transition table), models (SQLAlchemy). Routers never touch the database directly.
- AI code lives in `app/ai/` behind small interfaces (`Classifier`, `AssigneeSuggester`, `CompletenessChecker`, `Embedder`). Services depend on the interfaces; tests use fakes.

### 5.3 Frontend

- Next.js App Router with TypeScript, Tailwind and shadcn/ui, TanStack Query for server state.
- TypeScript API types are generated from FastAPI's OpenAPI document, so the frontend cannot drift from the backend contract.
- Next.js proxies `/api/*` to FastAPI, so the browser only ever talks to one origin.

### 5.4 Authentication

- Own login; no external identity provider.
- FastAPI verifies email and password (argon2 hash) and sets a signed session token in an httpOnly, SameSite=Lax cookie with a 12-hour expiry.
- Role and visibility checks are FastAPI dependencies applied per route.
- No self-registration; the admin creates users. Seed data provides demo accounts for every role.

### 5.5 Infrastructure

- Development: the homelab, through `lab.yml`: Postgres with the `vector` extension and a Garage (S3 API) bucket for attachments. The app reads only environment variables from `.env.lab`, which is never committed.
- CI: GitHub-hosted runners with a pgvector Postgres service container and a fake storage implementation. CI does not depend on the homelab.
- Attachments upload directly to S3 through presigned URLs. Defaults: 10 MB per file, 5 files per ticket or message; images, PDF and common office formats.

### 5.6 LLM and embeddings

- LLM: Claude through the official `anthropic` Python SDK, using structured outputs parsed into Pydantic models. Default model `claude-opus-5-5` at low effort. The model id and effort are configuration, so the eval set can compare models and the choice can be made on measured results.
- Embeddings: an in-process ONNX model through `fastembed`, behind the `Embedder` interface. The same model runs in development and in CI. The specific model and its vector dimension are chosen at milestone 4 by comparing candidates on the duplicate-detection eval.
- AI calls run in-process: classification and the completeness check inside the draft-check request; embedding and the assignee suggestion when a ticket enters Waiting in Queue. There is no queue or worker in v1.
- Failure handling: if the Claude call fails, times out or is refused, the form still works; the AI panel shows that suggestions are unavailable and the ticket is filed without them. AI never blocks a submit.
- Prompts are files under `app/ai/prompts/`, each with a version string that is recorded in `ai_predictions`.

## 6. API

All routes are under `/api/v1`.

### 6.1 Routes

| Area | Routes |
|---|---|
| Auth | `POST auth/login`, `POST auth/logout`, `GET auth/me` |
| Tickets | `POST tickets`, `GET tickets` (filters: institute, ticket_for, type, status, assignee, mine), `GET tickets/{id}` |
| Actions | `POST tickets/{id}/actions/{action}`: every transition in section 3.2 uses this one shape, with a body for remark, assignee, estimate or reason, and attachment keys on a reply |
| Thread | `POST tickets/{id}/messages` |
| Attachments | `POST attachments/presign`, then attach by key on ticket or message creation |
| Bulk | `POST tickets/bulk-assign` |
| Draft check | `POST tickets/draft/check`: returns classification (milestone 2), missing information (milestone 3) and similar tickets (milestone 4) for an unsaved draft |
| Dashboard | `GET dashboard` |
| Admin | CRUD under `admin/` for users, institutes, sections, modules, thresholds |

### 6.2 Dashboard contents

Counts by status, by institute and by Ticket For; open tickets per developer; average time from approval to close. From milestone 2: acceptance rate of AI classifications and assignee suggestions.

### 6.3 Ticket creation and the later Helpdesk link

Ticket creation is one service function that takes a `source`. The source decides the entry status (`internal` skips approval). A future API client such as Campus Helpdesk would call the same function with `source=api` through a service credential. Neither the credential mechanism nor the client is built in v1.

## 7. Screens

| Screen | Roles | Content |
|---|---|---|
| Login | all | Email and password |
| New ticket | reporter; developer and lead for internal | Form (section, Ticket For, type, page URL, description, contact, extension, attachments) with an AI assist panel |
| My reports | reporter | Own tickets with status |
| Approvals inbox | approver | Pending tickets of the section; approve, reject, request information |
| Register | lead, developer, admin | All tickets; filters by institute, Ticket For, type, status; columns include estimate and assigned developer; bulk assign for the lead |
| My tickets | developer | Assigned tickets; start, pause, close |
| Ticket detail | anyone who can see the ticket | Fields, timeline thread, actions allowed for the viewer, timer, similar tickets (milestone 4) |
| Dashboard | lead, admin | Section 6.2 |
| Admin | admin | Master data and thresholds |

The screenshots of the old system are used as a layout and flow reference when the register and ticket detail screens are built.

## 8. AI features

All four follow the same pattern: rules first, the LLM only when rules are not decisive, a confidence gate, a human confirmation step, and a row in `ai_predictions` recording what was predicted and what the human finally chose.

### 8.1 Classification (milestone 2)

- Input: description and page URL of the draft.
- Rules: a URL prefix identifies the ERP module and implies Ticket For = CampusERP; keyword rules cover clear cases.
- LLM: when rules do not decide, Claude returns Ticket For, Ticket Type and ERP module as enum fields with a confidence.
- Human step: the form is pre-filled and the reporter confirms or changes it. A change is logged as an override.

### 8.2 Suggested assignee (milestone 2)

- Runs when a ticket enters Waiting in Queue.
- Score per developer from: past tickets resolved in the same Ticket For and module, resolvers of similar past tickets (by category until milestone 4 adds embeddings), and current open workload.
- No LLM at first; it is added only if the eval shows the score is not good enough.
- Above the confidence threshold the ticket is auto-assigned; below it the lead sees the ranked suggestion and confirms or picks someone else.
- A later reassignment by the lead is logged and counts against the suggestion's accuracy.

### 8.3 Completeness check (milestone 3)

- Runs in the draft check, before the ticket is filed.
- Rules: a checklist per Ticket For and type (for example, a bug report needs a page URL and the steps; a graphics request needs dimensions).
- LLM: Claude reads the draft and any image attachments and returns the missing items as questions for the reporter.
- Human step: the reporter answers the questions or chooses to submit anyway; both are logged.
- Goal: fewer tickets entering Clarification Required, Insufficient Data and Poor Quality Images.

### 8.4 Similar and duplicate detection (milestone 4)

- Each ticket's description is embedded and stored in pgvector.
- The draft check returns the nearest tickets by cosine similarity. Above a high threshold the reporter sees a "possible duplicate" warning; the lead sees similar tickets on the detail screen.
- No LLM.

### 8.5 Thresholds

Confidence thresholds are configuration, editable by the admin, and tuned on the eval set.

## 9. Evals

- Datasets are JSONL files under `evals/`: invented tickets labelled with the expected Ticket For, type and module, the expected missing information, known duplicate pairs and the expected assignee.
- The eval set is written separately from the seed data and hand-reviewed, and deliberately includes ambiguous and adversarial cases. Seed tickets are never reused as eval cases.
- Metrics: accuracy per classification field; precision and recall for the completeness check; recall at k for duplicates; top-1 and top-3 accuracy for the assignee.
- Thresholds are set from the first measured baseline and stored in the repository. They are only ever raised. CI fails if a metric falls below its threshold.
- Rule-based and embedding evals are free and run on every pull request. LLM evals cost API money: they run only when `backend/app/ai/**` or a prompt changes, and on manual trigger. The per-run budget is agreed at milestone 5 before the job is enabled.
- The README shows the latest results table.

## 10. Testing and CI

- Backend tests run with pytest against a real Postgres (the CI service container).
- The transition table is tested table-driven: every allowed transition, and a sample of forbidden ones per role.
- AI modules are tested with fake LLM and embedder implementations; real model calls happen only in evals.
- One Playwright happy-path test per milestone.
- GitHub Actions: ruff, type check, pytest; frontend lint, `tsc` and build; the eval job from milestone 5.

## 11. Milestones

Each milestone ends in a demo. Each gets its own implementation plan.

| # | Content | Demo |
|---|---|---|
| 1 | Lifecycle end to end, no AI: auth, roles, tickets, transition table, events and timeline, attachments, timer, register, my reports, my tickets, internal tickets, dashboard, seed data | A ticket goes from submit to closed across all five roles, including one clarification loop; an internal ticket skips approval |
| 2 | Classification and suggested assignee with confidence gating, `ai_predictions` | The form pre-fills; a high-confidence ticket is auto-assigned; a reassignment shows in the accuracy figures |
| 3 | Completeness check | A vague draft gets questions before it is filed |
| 4 | Similar and duplicate detection | A near-copy of an existing ticket is flagged at submit |
| 5 | Eval set, CI gate, README results | A pull request that lowers accuracy fails CI |

## 12. Data rules

- The university, institutes, people and tickets are all invented. Seed emails use the reserved `.example` domain and phone numbers are obviously fake.
- The screenshots of the old system contain real staff names, phone numbers and emails. They are read only as a layout and flow reference. Nothing from them is copied into code, seed data, eval data, tests or documentation.
- Secrets (`.env`, `.env.lab`, API keys) are never committed. The Claude API key is a GitHub Actions secret.
