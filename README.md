# Devin Issue Remediator

## Project Summary
Devin Issue Remediator is a planned Dockerized automation that will listen for GitHub issues labeled `devin:auto-remediate`, start Devin sessions through the Devin API, track remediation status, comment back to GitHub, and expose a simple metrics dashboard.

This milestone is only the project foundation. It does not implement GitHub webhooks, Devin API calls, persistence, or dashboard logic yet.

## Problem
Maintainers need a reliable way to turn selected GitHub issues into automated remediation sessions without manually copying issue context, starting sessions, and reporting status by hand.

## Architecture
The future app will run as a FastAPI service in Docker. It will accept GitHub issue events, validate target labels, route work to Devin in live mode, persist status, and expose health and metrics endpoints.

Current scaffold:
- FastAPI app package under `app/`
- Environment-based settings in `app/config.py`
- Docker and Compose setup for local review
- Fake sample GitHub payload for future demo wiring
- Placeholder simulator script

## Design Notes
At each stage, it should be clear:

- What event enters the system.
- What decision the app makes.
- What work Devin owns versus what this app owns.
- What state is stored and why.
- What proof shows the workflow is working.

Before adding new behavior, identify the files that own that behavior and the command that proves it works.

## Quickstart
```bash
cd devin-issue-remediator
cp .env.example .env
docker compose up --build
```

In another terminal:

```bash
curl http://localhost:8000/health
curl http://localhost:8000/
python scripts/simulate_issue_event.py
```

Expected health response:

```json
{"status":"ok"}
```

## Demo Mode
Demo Mode is the default via `APP_MODE=demo`.

Demo Mode will eventually run without real Devin or GitHub credentials. For this scaffold, it only starts the FastAPI app and exposes basic health checks.

## Live Mode
Live Mode is reserved for future milestones. It is expected to require real Devin and GitHub credentials, webhook signature verification, API error handling, status tracking, and safe logging.

Do not assume Live Mode is implemented yet.

## Environment Variables
Copy `.env.example` to `.env` for local runs.

| Variable | Purpose |
| --- | --- |
| `APP_MODE` | Runtime mode. Defaults to `demo`. |
| `DEVIN_API_KEY` | Future Devin API key for live mode. |
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
- Demo Mode should remain credential-free.

## Next Steps
1. Add local/demo issue event ingestion.
2. Validate the `devin:auto-remediate` label.
3. Persist a remediation record.
4. Expose a minimal status endpoint.
5. Keep live Devin and GitHub calls out until the live-mode milestone.
