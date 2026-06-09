from __future__ import annotations

from datetime import datetime
from statistics import mean
from typing import Any


ACTIVE_STATUSES = {
    "received",
    "eligible",
    "session_created",
    "working",
    "waiting_for_user",
    "waiting_for_approval",
}


def calculate_metrics(runs: list[dict[str, Any]]) -> dict[str, float | int]:
    eligible = len(runs)
    delegated = sum(1 for run in runs if run.get("devin_session_id"))
    completed = sum(1 for run in runs if run.get("status") == "completed")
    failed = sum(1 for run in runs if run.get("status") == "failed")
    blocked = sum(1 for run in runs if run.get("status") == "blocked")
    active = sum(1 for run in runs if run.get("status") in ACTIVE_STATUSES)
    prs_opened = sum(1 for run in runs if run.get("pr_url") or run.get("outcome") == "pr_opened")
    human_review = sum(1 for run in runs if run.get("requires_human_review"))

    first_response_durations = [
        seconds_between(run.get("triggered_at"), run.get("first_response_at"))
        for run in runs
        if run.get("triggered_at") and run.get("first_response_at")
    ]
    completion_durations = [
        seconds_between(run.get("triggered_at"), run.get("completed_at"))
        for run in runs
        if run.get("triggered_at") and run.get("completed_at")
    ]

    return {
        "eligible_issues_detected": eligible,
        "delegated_to_devin": delegated,
        "automation_coverage": round(delegated / eligible, 2) if eligible else 0,
        "active_sessions": active,
        "completed_sessions": completed,
        "failed_sessions": failed,
        "blocked_sessions": blocked,
        "prs_opened": prs_opened,
        "human_review_required": human_review,
        "avg_time_to_first_response_seconds": average_seconds(first_response_durations),
        "avg_time_to_completion_seconds": average_seconds(completion_durations),
        "estimated_manual_triage_minutes_saved": sum(
            int(run.get("estimated_manual_triage_minutes") or 0) for run in runs
        ),
    }


def average_seconds(values: list[float]) -> float:
    if not values:
        return 0
    return round(mean(values), 2)


def seconds_between(start: str | None, end: str | None) -> float:
    if not start or not end:
        return 0
    return max(0, (datetime.fromisoformat(end) - datetime.fromisoformat(start)).total_seconds())
