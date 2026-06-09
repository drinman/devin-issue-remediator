# Devin Issue Remediator

## Project Summary
Devin Issue Remediator is a Dockerized FastAPI demo app for event-driven engineering remediation. When a GitHub issue event contains the label `devin:auto-remediate`, the app creates a run, starts a mock Devin session in Demo Mode, persists run state in SQLite, and exposes a small dashboard plus metrics endpoints.

Demo Mode remains the credential-free default. Live Mode (`APP_MODE=live`) creates and polls real Devin sessions through `api.devin.ai`; live GitHub comments and webhook signature verification are not implemented yet.

## Problem
Maintainers need a reliable way to turn selected GitHub issues into automated remediation sessions without manually copying issue context, starting sessions, and reporting status by hand.

## Architecture
```text
GitHub issue event or local simulator
        |
        v
FastAPI webhook receiver
        |
        v
Eligibility check: devin:auto-remediate
        |
        v
Prompt builder + Mock Devin client
        |
        v
SQLite run storage
        |
        v
Dashboard, run APIs, metrics
```

Current implementation:
- `app/main.py` owns FastAPI routes, the HTML dashboard, and mode-based client selection.
- `app/workflow.py` owns event eligibility, prompt building, simulation, and refresh behavior.
- `app/devin.py` owns both Devin clients: the Demo Mode mock and the live API client, plus the status mapping between Devin's `status_enum` and run statuses.
- `app/storage.py` owns SQLite persistence.
- `app/metrics.py` owns aggregate metric calculation.
- `scripts/simulate_issue_event.py` sends a fake GitHub issue event to the local app.

## Quickstart
```bash
cp .env.example .env
docker compose up --build
```

In another terminal:

```bash
curl http://localhost:8000/health
python scripts/simulate_issue_event.py
open http://localhost:8000
```

Expected health response:

```json
{"status":"ok"}
```

## Demo Mode
Demo Mode is the default via `APP_MODE=demo`.

Demo Mode requires no Devin or GitHub credentials. It uses a fake GitHub payload and a mock Devin client so the workflow can be inspected locally.

Useful endpoints:

```bash
curl http://localhost:8000/runs
curl http://localhost:8000/metrics
curl -X POST http://localhost:8000/runs/<run_id>/refresh
```

The refresh endpoint advances a mock run to `completed` with outcome `pr_opened`.

## Local Tests
```bash
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements.txt
.venv/bin/python -m pytest
```

## Superset Fork and Issues
The target repo is a public fork:

- [drinman/superset](https://github.com/drinman/superset)

Tracked issues:

- [#1 Fix focused utility test failure in Superset fork](https://github.com/drinman/superset/issues/1)
- [#2 Clean up small code quality issue in targeted Superset utility module](https://github.com/drinman/superset/issues/2)
- [#3 Improve developer guidance for running focused backend tests](https://github.com/drinman/superset/issues/3)

Each issue has `devin:auto-remediate` plus a task-specific Devin label.

## Live Mode
Live Mode creates and polls real Devin sessions through the same orchestration path as Demo Mode. Set in `.env`:

```bash
APP_MODE=live
DEVIN_API_KEY=apk_user_...
```

Then start the app (`docker compose up --build`). The app fails fast at startup if `APP_MODE=live` and `DEVIN_API_KEY` is missing.

Live behavior:
- `POST /webhooks/github` and `POST /simulate` create real Devin sessions. Sessions are created with `idempotent=true` (webhook redelivery reuses the same session instead of spawning duplicates) and capped by `DEVIN_MAX_ACU_LIMIT` (default 10) as a per-session cost guard.
- `POST /runs/<run_id>/refresh` polls the real session and maps Devin's `status_enum` to run status: `blocked` with a PR means completed (`pr_opened`); `blocked` without a PR means a human should look (`waiting_for_user`); `finished` is completed; `expired` without an artifact is failed. Completion timestamps are written once, on the terminal transition.

Live GitHub issue comments and webhook signature verification are not implemented yet.

### Devin API Smoke Test
Standalone check that proves the API key and the real session lifecycle without touching app code:

```bash
.venv/bin/python scripts/devin_smoke_test.py --check-auth
.venv/bin/python scripts/devin_smoke_test.py --create
.venv/bin/python scripts/devin_smoke_test.py --status <session_id> --watch
```

`--check-auth` lists sessions and costs no ACUs. `--create` starts one tiny session capped at 1 ACU (`--max-acu`) and prints the session URL so you can watch it in the Devin UI. Requires `DEVIN_API_KEY` in `.env`. Demo Mode remains credential-free.

## Environment Variables
Copy `.env.example` to `.env` for local runs.

| Variable | Purpose |
| --- | --- |
| `APP_MODE` | Runtime mode. Defaults to `demo`. |
| `DEVIN_API_KEY` | Devin API key. Required when `APP_MODE=live`. |
| `DEVIN_MAX_ACU_LIMIT` | Per-session ACU cost cap for live sessions. Defaults to `10`. |
| `DEVIN_ORG_ID` | Future Devin organization identifier. |
| `GITHUB_TOKEN` | Future GitHub API token for comments and issue reads. |
| `GITHUB_WEBHOOK_SECRET` | Future GitHub webhook signing secret. |
| `GITHUB_OWNER` | Future GitHub repository owner. |
| `GITHUB_REPO` | Future GitHub repository name. |
| `PUBLIC_BASE_URL` | Future externally reachable base URL for webhooks or callbacks. |
| `DATABASE_URL` | Storage URL. Defaults to `sqlite:///data/app.db`. |

## Security Notes
- Do not commit `.env`.
- Do not commit real API keys, webhook secrets, private URLs, customer data, or internal data.
- Keep sample payloads fake and public-safe.
- Demo Mode must remain credential-free and must not make external network calls.

## Next Steps
1. Add live-mode GitHub webhook signature verification.
2. Add real Devin API session creation behind `APP_MODE=live`.
3. Add live GitHub issue comments for session started, status refresh, and completion.
