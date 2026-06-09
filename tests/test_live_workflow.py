from pathlib import Path

import pytest

from app.config import Settings
from app.devin import DevinSession, DevinSessionStatus, map_status
from app.storage import RunStorage
from app.workflow import RemediationWorkflow


PR_URL = "https://github.com/drinman/superset/pull/9"


@pytest.mark.parametrize(
    ("status_enum", "pr_url", "expected_status", "expected_outcome"),
    [
        ("working", None, "working", "unknown"),
        ("working", PR_URL, "working", "unknown"),
        ("blocked", PR_URL, "completed", "pr_opened"),
        ("blocked", None, "waiting_for_user", "blocked_needs_human"),
        ("finished", PR_URL, "completed", "pr_opened"),
        ("finished", None, "completed", "investigation_completed"),
        ("expired", PR_URL, "completed", "pr_opened"),
        ("expired", None, "failed", "failed"),
        ("suspend_requested", None, "working", "unknown"),
        ("resumed", None, "working", "unknown"),
        ("some_future_state", None, "working", "unknown"),
        (None, None, "working", "unknown"),
    ],
)
def test_map_status_table(status_enum, pr_url, expected_status, expected_outcome) -> None:
    assert map_status(status_enum, pr_url) == (expected_status, expected_outcome)


class StillWorkingDevinClient:
    def create_session(self, prompt: str) -> DevinSession:
        return DevinSession(
            id="live-session-1",
            url="https://app.devin.ai/sessions/live-session-1",
            status="working",
        )

    def get_session(self, session_id: str) -> DevinSessionStatus:
        return DevinSessionStatus(
            id=session_id,
            status="working",
            outcome="unknown",
            summary="",
            pr_url=None,
        )


def test_refresh_while_working_does_not_stamp_completion(tmp_path: Path) -> None:
    database_url = f"sqlite:///{tmp_path / 'runs.db'}"
    workflow = RemediationWorkflow(
        settings=Settings(app_mode="demo", database_url=database_url),
        storage=RunStorage(database_url),
        devin_client=StillWorkingDevinClient(),
    )
    created = workflow.handle_simulation(
        {"issue_number": 1, "issue_title": "Fix focused utility test failure in Superset fork"}
    )

    run = workflow.refresh_run(created["run"]["run_id"])

    assert run["status"] == "working"
    assert run["completed_at"] is None
    assert run["duration_seconds"] is None
