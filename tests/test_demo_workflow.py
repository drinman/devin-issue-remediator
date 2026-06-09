import json
from pathlib import Path

from fastapi.testclient import TestClient

from app.config import Settings
from app.main import create_app


def build_client(tmp_path: Path) -> TestClient:
    settings = Settings(
        app_mode="demo",
        database_url=f"sqlite:///{tmp_path / 'runs.db'}",
    )
    return TestClient(create_app(settings))


def load_sample_payload() -> dict:
    payload_path = Path(__file__).resolve().parents[1] / "sample_payloads" / "github_issue_labeled.json"
    return json.loads(payload_path.read_text())


def test_github_label_event_creates_mock_devin_run(tmp_path: Path) -> None:
    client = build_client(tmp_path)
    payload = load_sample_payload()

    response = client.post("/webhooks/github", json=payload)

    assert response.status_code == 200
    body = response.json()
    assert body["result"] == "created"
    assert body["run"]["issue_number"] == 1
    assert body["run"]["issue_title"] == "Fix focused utility test failure in Superset fork"
    assert body["run"]["issue_url"] == "https://github.com/drinman/superset/issues/1"
    assert body["run"]["repo_url"] == "https://github.com/drinman/superset"
    assert body["run"]["task_type"] == "ci_failure"
    assert body["run"]["status"] == "working"
    assert body["run"]["outcome"] == "unknown"
    assert body["run"]["requires_human_review"] is True
    assert body["run"]["devin_session_id"].startswith("mock-devin-session-")

    runs = client.get("/runs").json()
    assert len(runs) == 1
    assert runs[0]["run_id"] == body["run"]["run_id"]

    metrics = client.get("/metrics").json()
    assert metrics["eligible_issues_detected"] == 1
    assert metrics["delegated_to_devin"] == 1
    assert metrics["automation_coverage"] == 1.0
    assert metrics["active_sessions"] == 1
    assert metrics["completed_sessions"] == 0


def test_ineligible_issue_event_is_ignored_and_not_stored(tmp_path: Path) -> None:
    client = build_client(tmp_path)
    payload = load_sample_payload()
    payload["issue"]["labels"] = [{"name": "bug"}]
    payload["label"] = {"name": "bug"}

    response = client.post("/webhooks/github", json=payload)

    assert response.status_code == 200
    assert response.json() == {
        "result": "ignored",
        "reason": "missing devin:auto-remediate label",
    }
    assert client.get("/runs").json() == []
    assert client.get("/metrics").json()["eligible_issues_detected"] == 0


def test_refresh_completes_mock_run_and_updates_metrics(tmp_path: Path) -> None:
    client = build_client(tmp_path)
    created = client.post("/webhooks/github", json=load_sample_payload()).json()["run"]

    response = client.post(f"/runs/{created['run_id']}/refresh")

    assert response.status_code == 200
    run = response.json()
    assert run["status"] == "completed"
    assert run["outcome"] == "pr_opened"
    assert run["pr_url"] == "https://github.com/drinman/superset/pull/1"
    assert run["completed_at"] is not None
    assert run["duration_seconds"] >= 0

    metrics = client.get("/metrics").json()
    assert metrics["active_sessions"] == 0
    assert metrics["completed_sessions"] == 1
    assert metrics["prs_opened"] == 1
    assert metrics["human_review_required"] == 1
    assert metrics["estimated_manual_triage_minutes_saved"] == 30


def test_simulate_endpoint_accepts_minimal_issue_payload(tmp_path: Path) -> None:
    client = build_client(tmp_path)

    response = client.post(
        "/simulate",
        json={
            "issue_number": 3,
            "issue_title": "Improve developer guidance for running focused backend tests",
            "issue_url": "https://github.com/drinman/superset/issues/3",
            "issue_body": "Add a concise focused-test example to contributor docs.",
            "labels": ["devin:auto-remediate", "devin:docs"],
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert body["result"] == "created"
    assert body["run"]["issue_number"] == 3
    assert body["run"]["task_type"] == "docs_quality"
    assert body["run"]["repo_url"] == "https://github.com/drinman/superset"


def test_dashboard_returns_html_summary(tmp_path: Path) -> None:
    client = build_client(tmp_path)
    client.post("/webhooks/github", json=load_sample_payload())

    response = client.get("/")

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/html")
    assert "Devin Issue Remediator" in response.text
    assert "Mode: demo" in response.text
    assert "Eligible issues detected" in response.text
    assert "Fix focused utility test failure in Superset fork" in response.text
