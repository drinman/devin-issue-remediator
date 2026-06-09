from __future__ import annotations

from datetime import datetime, timezone
from typing import Any
from uuid import uuid4

from app.config import Settings
from app.devin import MockDevinClient
from app.storage import RunStorage


AUTO_REMEDIATE_LABEL = "devin:auto-remediate"
ALLOWED_ACTIONS = {"opened", "labeled", "edited", "reopened"}
DEFAULT_DEMO_REPO_URL = "https://github.com/drinman/superset"


class RemediationWorkflow:
    def __init__(
        self,
        settings: Settings,
        storage: RunStorage,
        devin_client: MockDevinClient,
    ) -> None:
        self.settings = settings
        self.storage = storage
        self.devin_client = devin_client

    def handle_github_event(self, payload: dict[str, Any]) -> dict[str, Any]:
        ignored_reason = ignored_event_reason(payload)
        if ignored_reason:
            return {"result": "ignored", "reason": ignored_reason}

        now = utc_now()
        issue = payload["issue"]
        labels = label_names(issue)
        repo_url = repository_url(payload)
        prompt = build_prompt(
            repo_url=repo_url,
            issue_url=issue["html_url"],
            issue_title=issue["title"],
            issue_body=issue.get("body") or "",
            task_type=task_type_from_labels(labels),
        )
        session = self.devin_client.create_session(prompt)
        run = self.storage.create_run(
            {
                "run_id": str(uuid4()),
                "trigger_type": "github_issue_event",
                "issue_number": int(issue["number"]),
                "issue_title": issue["title"],
                "issue_url": issue["html_url"],
                "issue_body": issue.get("body") or "",
                "labels_json": labels,
                "task_type": task_type_from_labels(labels),
                "repo_url": repo_url,
                "devin_session_id": session.id,
                "devin_session_url": session.url,
                "status": session.status,
                "outcome": "unknown",
                "pr_url": None,
                "requires_human_review": True,
                "triggered_at": now,
                "first_response_at": now,
                "completed_at": None,
                "duration_seconds": None,
                "estimated_manual_triage_minutes": 30,
                "error_message": None,
                "created_at": now,
                "updated_at": now,
            }
        )
        return {"result": "created", "run": run}

    def handle_simulation(self, payload: dict[str, Any]) -> dict[str, Any]:
        return self.handle_github_event(simulated_github_payload(payload))

    def refresh_run(self, run_id: str) -> dict[str, Any] | None:
        run = self.storage.get_run(run_id)
        if run is None:
            return None

        status = self.devin_client.get_session(run["devin_session_id"])
        completed_at = utc_now()
        duration_seconds = seconds_since(run["triggered_at"], completed_at)
        return self.storage.update_run(
            run_id,
            {
                "status": status.status,
                "outcome": status.outcome,
                "pr_url": status.pr_url,
                "completed_at": completed_at,
                "duration_seconds": duration_seconds,
                "updated_at": completed_at,
            },
        )


def ignored_event_reason(payload: dict[str, Any]) -> str | None:
    if payload.get("action") not in ALLOWED_ACTIONS:
        return "unsupported issue action"
    issue = payload.get("issue")
    if not isinstance(issue, dict):
        return "missing issue payload"
    if AUTO_REMEDIATE_LABEL not in label_names(issue):
        return "missing devin:auto-remediate label"
    return None


def label_names(issue: dict[str, Any]) -> list[str]:
    labels = issue.get("labels") or []
    names = []
    for label in labels:
        if isinstance(label, dict) and label.get("name"):
            names.append(label["name"])
        elif isinstance(label, str):
            names.append(label)
    return names


def task_type_from_labels(labels: list[str]) -> str:
    if "devin:ci-failure" in labels:
        return "ci_failure"
    if "devin:docs" in labels:
        return "docs_quality"
    if "devin:code-quality" in labels:
        return "code_quality"
    return "general"


def repository_url(payload: dict[str, Any]) -> str:
    repository = payload.get("repository") or {}
    return repository.get("html_url") or DEFAULT_DEMO_REPO_URL


def simulated_github_payload(payload: dict[str, Any]) -> dict[str, Any]:
    labels = payload.get("labels") or [AUTO_REMEDIATE_LABEL]
    label_objects = [{"name": label} for label in labels]
    issue_number = int(payload["issue_number"])
    issue_url = payload.get("issue_url") or f"{DEFAULT_DEMO_REPO_URL}/issues/{issue_number}"
    return {
        "action": "labeled",
        "label": {"name": AUTO_REMEDIATE_LABEL},
        "issue": {
            "number": issue_number,
            "title": payload["issue_title"],
            "html_url": issue_url,
            "body": payload.get("issue_body") or "",
            "labels": label_objects,
        },
        "repository": {
            "full_name": "drinman/superset",
            "html_url": DEFAULT_DEMO_REPO_URL,
        },
    }


def build_prompt(
    repo_url: str,
    issue_url: str,
    issue_title: str,
    issue_body: str,
    task_type: str,
) -> str:
    return f"""You are Devin, acting as a first-pass autonomous engineering remediator.

Repository:
{repo_url}

GitHub Issue:
{issue_url}

Issue Title:
{issue_title}

Issue Body:
{issue_body}

Task Type:
{task_type}

Goal:
Investigate and remediate the issue with the smallest safe change.

Instructions:
1. Clone or access the repository and inspect the issue context.
2. Identify the likely root cause.
3. Make the smallest safe change that addresses the issue.
4. Add or update focused tests/docs if appropriate.
5. Run the most focused validation command available.
6. Open a pull request against the fork if you can complete the remediation.
7. Summarize root cause, files changed, validation, PR link, and remaining risk.

Constraints:
- Do not perform broad unrelated refactors.
- Do not change unrelated files.
- Do not auto-merge.
- Prefer focused validation over full repo test runs.
- If blocked, stop and explain the blocker clearly.
"""


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def seconds_since(start: str, end: str) -> float:
    return max(0, (datetime.fromisoformat(end) - datetime.fromisoformat(start)).total_seconds())
