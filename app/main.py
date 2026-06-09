from __future__ import annotations

from html import escape
from typing import Any

from fastapi import Body, FastAPI, HTTPException
from fastapi.responses import HTMLResponse

from app.config import settings
from app.devin import MockDevinClient
from app.metrics import calculate_metrics
from app.storage import RunStorage
from app.workflow import RemediationWorkflow


def create_app(app_settings=settings) -> FastAPI:
    app = FastAPI(title="Devin Issue Remediator")
    storage = RunStorage(app_settings.database_url)
    workflow = RemediationWorkflow(
        settings=app_settings,
        storage=storage,
        devin_client=MockDevinClient(),
    )

    @app.get("/", response_class=HTMLResponse)
    def root() -> str:
        runs = storage.list_runs()
        metrics = calculate_metrics(runs)
        return render_dashboard(mode=app_settings.app_mode, runs=runs, metrics=metrics)

    @app.get("/health")
    def health() -> dict[str, str]:
        return {"status": "ok"}

    @app.post("/webhooks/github")
    def github_webhook(payload: dict[str, Any]) -> dict[str, Any]:
        return workflow.handle_github_event(payload)

    @app.post("/simulate")
    def simulate(payload: dict[str, Any] = Body(...)) -> dict[str, Any]:
        return workflow.handle_simulation(payload)

    @app.get("/runs")
    def list_runs() -> list[dict[str, Any]]:
        return storage.list_runs()

    @app.get("/runs/{run_id}")
    def get_run(run_id: str) -> dict[str, Any]:
        run = storage.get_run(run_id)
        if run is None:
            raise HTTPException(status_code=404, detail="Run not found")
        return run

    @app.post("/runs/{run_id}/refresh")
    def refresh_run(run_id: str) -> dict[str, Any]:
        run = workflow.refresh_run(run_id)
        if run is None:
            raise HTTPException(status_code=404, detail="Run not found")
        return run

    @app.get("/metrics")
    def metrics() -> dict[str, float | int]:
        return calculate_metrics(storage.list_runs())

    return app


def render_dashboard(mode: str, runs: list[dict[str, Any]], metrics: dict[str, float | int]) -> str:
    rows = "\n".join(render_run_row(run) for run in runs)
    if not rows:
        rows = '<tr><td colspan="7">No remediation runs yet.</td></tr>'

    return f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Devin Issue Remediator</title>
  <style>
    body {{ font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif; margin: 32px; color: #1f2937; }}
    header {{ display: flex; justify-content: space-between; align-items: baseline; gap: 16px; }}
    .mode {{ color: #475569; font-weight: 600; }}
    .grid {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(180px, 1fr)); gap: 12px; margin: 24px 0; }}
    .card {{ border: 1px solid #d8dee4; border-radius: 8px; padding: 14px; background: #ffffff; }}
    .label {{ color: #64748b; font-size: 13px; }}
    .value {{ font-size: 28px; font-weight: 700; margin-top: 4px; }}
    table {{ width: 100%; border-collapse: collapse; margin-top: 16px; }}
    th, td {{ border-bottom: 1px solid #e5e7eb; padding: 10px; text-align: left; vertical-align: top; }}
    th {{ background: #f8fafc; font-size: 13px; color: #475569; }}
    a {{ color: #0969da; }}
    .panel {{ border: 1px solid #d8dee4; border-radius: 8px; padding: 16px; margin-top: 24px; background: #f8fafc; }}
  </style>
</head>
<body>
  <header>
    <h1>Devin Issue Remediator</h1>
    <div class="mode">Mode: {escape(mode)}</div>
  </header>

  <section class="grid">
    {metric_card("Eligible issues detected", metrics["eligible_issues_detected"])}
    {metric_card("Delegated to Devin", metrics["delegated_to_devin"])}
    {metric_card("PRs opened", metrics["prs_opened"])}
    {metric_card("Avg first response", f'{metrics["avg_time_to_first_response_seconds"]}s')}
    {metric_card("Estimated triage saved", f'{metrics["estimated_manual_triage_minutes_saved"]}m')}
  </section>

  <h2>Runs</h2>
  <table>
    <thead>
      <tr>
        <th>Issue</th>
        <th>Task type</th>
        <th>Status</th>
        <th>Outcome</th>
        <th>Session</th>
        <th>PR</th>
        <th>Duration</th>
      </tr>
    </thead>
    <tbody>{rows}</tbody>
  </table>

  <section class="panel">
    <h2>How it works</h2>
    <p>A GitHub issue label is the approval gate. This service scopes the issue, starts a Devin session, tracks status, and turns the result into metrics engineering leadership can inspect.</p>
  </section>
</body>
</html>"""


def metric_card(label: str, value: object) -> str:
    return f"""<div class="card">
      <div class="label">{escape(label)}</div>
      <div class="value">{escape(str(value))}</div>
    </div>"""


def render_run_row(run: dict[str, Any]) -> str:
    issue_link = linked_text(run["issue_url"], f'#{run["issue_number"]} {run["issue_title"]}')
    session_link = linked_text(run["devin_session_url"], run["devin_session_id"])
    pr_link = linked_text(run["pr_url"], "PR") if run.get("pr_url") else ""
    duration = "" if run.get("duration_seconds") is None else f'{run["duration_seconds"]:.2f}s'
    return f"""<tr>
      <td>{issue_link}</td>
      <td>{escape(run["task_type"])}</td>
      <td>{escape(run["status"])}</td>
      <td>{escape(run["outcome"])}</td>
      <td>{session_link}</td>
      <td>{pr_link}</td>
      <td>{escape(duration)}</td>
    </tr>"""


def linked_text(url: str | None, text: str | None) -> str:
    if not url or not text:
        return ""
    return f'<a href="{escape(url)}">{escape(text)}</a>'


app = create_app()
