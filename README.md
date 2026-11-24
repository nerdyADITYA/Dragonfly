# Dragonfly

> The dragonfly is nature's deadliest hunter: it catches about 95% of the prey it chases.
> This one hunts bugs.

AI-assisted QA platform: explores an **authorized** web app, generates structured tests, executes them
deterministically with Playwright, and captures evidence. AI plans; tools execute and verify.

> Status: **Milestones A–F** of the [development plan](TestPilot_AI_Full_Project_Development_Plan.md) —
> discover pages → generate tests (Claude or rule-based) → review/approve → execute with evidence →
> failure becomes a finding (repro steps, screenshots, AI hypothesis) → ticket assigned to a developer →
> fix → automated retest marks it **verified** (or reopens it).

## What you get in the UI

- **Dashboard**: pass rate (formula shown), executions trend, open findings by severity, regressions,
  verified fixes, and tests with mixed recent results. Tiles link to the filtered findings list.
- **Application map**: discovered pages by depth with navigation edges. Red = open findings,
  amber = no tests, green = tested. Search, highlight filters, click a page for its screenshot.
- **Scan report**: a self-contained HTML file (configuration, discovery, results, findings with
  embedded screenshots, limitations). Use *View report* / *Download HTML* on a scan.
- **Test editor**: form-based steps and locators (raw JSON optional), run one test, duplicate,
  AI regenerate with reviewer instructions, and full version history. Any edit returns a test to draft.
- **Live updates**: worker → Redis pub/sub → `/api/v1/ws/projects/{id}` WebSocket. Pages refresh as
  pages are found and tests finish; polling is only a fallback.

## Demo storyline (§65)

1. Discover the demo app, generate tests, approve and run them → `Add user: empty required fields…` fails.
2. Open the finding: expected vs actual, reproduction steps, screenshots, trace, AI analysis (labelled hypothesis).
3. Add a developer on the project page → **Create ticket** assigned to them (TP-1, with a markdown bug report).
4. **Retest now** → still failing → finding is *reopened*.
5. Ship the fix: `$env:DEMO_FIXED=1; docker compose up -d demo-app`
6. **Retest now** → passes → finding is *verified*. Reset with `$env:DEMO_FIXED=0; docker compose up -d demo-app`.

Rules: a finding is created only for assertion/step failures (never for blocked/timeout/infrastructure); the
same test failing at the same step updates one finding (confidence becomes *confirmed* once reproduced);
severity overrides need a reason; only a passing retest of the original test version can set *verified*.

## Architecture

```
web (React/Vite) ──► api (FastAPI) ──► postgres
                         │  enqueue
                         ▼
                       redis ──► worker (Celery + Playwright/Chromium) ──► demo-app / your target
                                     │
                                     └─► artifacts volume (screenshots, traces)
```

| Module | File | Plan § |
|---|---|---|
| Scope + SSRF guard | `backend/app/scope.py` | 29.2–29.3 |
| Explorer (BFS link crawl) | `backend/app/discovery.py` | 8 |
| AI planner (Claude structured output + rule-based fallback) | `backend/app/planner.py` | 9, 20.2 |
| Deterministic validator | `backend/app/validator.py` | 9.6, 20.3 |
| Execution engine (typed action allowlist) | `backend/app/executor.py` | 10, 21 |
| Findings, tickets, retest verification | `backend/app/findings.py` | 14–16 |
| Claude provider (structured output) | `backend/app/ai.py` | 20.7 |
| Browser isolation + event capture | `backend/app/browser.py` | 10.5, 21.4 |
| REST API | `backend/app/routes.py` | 27 |
| Demo target with known defects | `demo-app/app.py` | 64 |

## Run it (Docker)

```powershell
copy .env.example .env      # optionally add ANTHROPIC_API_KEY
docker compose up --build
```

- UI: http://localhost:5173 · API docs: http://localhost:8000/docs · Demo target: http://localhost:8001
- In the UI: create a project → add an environment with base URL **`http://demo-app:8001/`**, tick
  *private network* and *I am authorized* → **Discover** → **Generate tests** → approve → **Run**.
- The worker reaches the demo app by its Compose service name, so use `demo-app`, not `localhost`.

## Run the tests (no Docker needed)

```powershell
cd backend
python -m venv .venv; .\.venv\Scripts\pip install -r requirements.txt; .\.venv\Scripts\playwright install chromium
.\.venv\Scripts\pytest -q
```

`tests/test_vertical_slice.py` runs the whole slice against the demo app in-process (SQLite, inline Celery) and
asserts that known defect D1 is caught with screenshot + trace evidence, that the explorer never follows the
destructive `Delete` link or the external partner link, and that unapproved tests cannot run.

## Safety model

- Scans refuse to start until the environment's **authorization is confirmed**.
- Every browser request is checked against allowed hosts, excluded paths, blocked control-plane hostnames and
  IP classes (metadata/link-local always blocked; private/loopback only with explicit opt-in). Redirects re-checked.
- Discovery follows links only, never submits forms, and skips destructive-looking links (delete, logout, pay…).
- AI output is never executed directly: it must parse into the typed action schema, pass the validator
  (assertions required, in-scope navigation, no destructive clicks), and be **approved by a human**.
- Screenshots mask password fields; evidence URLs drop query strings.
- Infrastructure failures are `inconclusive` (retried once), never `failed`.

## Known limitations (this milestone)

- No authentication/RBAC yet (Phase 1) — run locally only. This includes the live-events WebSocket.
- Discovery is unauthenticated and links-only.
- Artifacts are on a local volume (MinIO/S3 + signed URLs in Phase 6).
- Tests created before version history existed have no recorded versions.
- With *private network* enabled, an IP-literal target inside the Docker network is not blocked by name.
- DNS results are cached per worker process (no rebinding protection yet).
- Tickets are internal only; GitHub Issues sync is not built yet. Assignees are a per-project list, not user accounts.

## Demo target defects

See the docstring in `demo-app/app.py` (D1–D8). `DEMO_FIXED=1` fixes D1–D3 for the upcoming retest demo.
