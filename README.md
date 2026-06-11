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

How the event arrives: the webhook receiver (`POST /webhooks/github`) is real; the simulator plays GitHub's part locally by sending the same `issues` event payload GitHub would deliver. Pointing a live GitHub webhook at this endpoint is a repository-settings change, not a code change.

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
- [#7 Improve developer guidance for running focused lint and type checks](https://github.com/drinman/superset/issues/7)

Each issue has `devin:auto-remediate` plus a task-specific Devin label.

## Live Remediation Results
The remediations below were produced by real Devin sessions, created and tracked by this app in Live Mode.

| Issue | Task type | Devin PR | Time to PR |
| --- | --- | --- | --- |
| [#3 Improve developer guidance for focused backend tests](https://github.com/drinman/superset/issues/3) | docs_quality | [PR #4](https://github.com/drinman/superset/pull/4) | ~12 min (incl. an access blocker) |
| [#1 Fix focused utility test failure](https://github.com/drinman/superset/issues/1) | ci_failure | [PR #5](https://github.com/drinman/superset/pull/5) | ~8 min |
| [#2 Clean up small code quality issue](https://github.com/drinman/superset/issues/2) | code_quality | [PR #6](https://github.com/drinman/superset/pull/6) | ~5 min |

Issue [#7](https://github.com/drinman/superset/issues/7) is the open queue item: the same label fires the same workflow whenever the team delegates it.

### Known-baseline validation behind issue #1
Issue #1 exercises the CI-failure path against a known-good answer: a one-line case-sensitivity regression in `parse_boolean_string` (a prior cleanup dropped `.lower()`), failing 3 of 20 parametrized cases. Devin reproduced the failure with the focused pytest command, traced it to the offending commit, restored the behavior while keeping the legitimate cleanup — fixing the function, not the test — and validated 20 of 20 passing before opening PR #5.

The issue #3 run also captured the human-gate lifecycle on the dashboard: the session sat `waiting_for_user` during a GitHub-access blocker, then completed once access was granted.

### Metrics snapshot after the first two live runs
```json
{
    "eligible_issues_detected": 2,
    "delegated_to_devin": 2,
    "automation_coverage": 1.0,
    "active_sessions": 0,
    "completed_sessions": 2,
    "failed_sessions": 0,
    "blocked_sessions": 0,
    "prs_opened": 2,
    "human_review_required": 2,
    "avg_time_to_first_response_seconds": 0,
    "avg_time_to_completion_seconds": 591.1,
    "estimated_manual_triage_minutes_saved": 60
}
```

Time to first response is 0 seconds because delegation happens synchronously in the webhook handler — the trigger and the first response are the same moment.

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

## Limitations
- No live GitHub issue comments; observable outputs are Devin's PRs plus this app's dashboard, run APIs, and metrics.
- No webhook signature verification; the demo trigger is the local simulator.
- Status refresh is on-demand (`POST /runs/<run_id>/refresh`); there is no background polling loop.
- The Superset fork has no CI configured, so PR checks pass trivially (0 checks).

These are deliberate scope choices; see Next Steps.

## Next Steps
1. Add live GitHub issue comments for session started, status refresh, and completion.
2. Add webhook signature verification and register a live GitHub webhook on the fork.
3. Add a background status-polling loop so runs complete without manual refresh.
