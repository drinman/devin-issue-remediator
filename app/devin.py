from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha1
from typing import Any

import requests


DEVIN_API_BASE_URL = "https://api.devin.ai/v1"
REQUEST_TIMEOUT_SECONDS = 30


@dataclass(frozen=True)
class DevinSession:
    id: str
    url: str
    status: str


@dataclass(frozen=True)
class DevinSessionStatus:
    id: str
    status: str
    outcome: str
    summary: str
    pr_url: str | None


class MockDevinClient:
    def create_session(self, prompt: str) -> DevinSession:
        digest = sha1(prompt.encode("utf-8")).hexdigest()[:10]
        session_id = f"mock-devin-session-{digest}"
        return DevinSession(
            id=session_id,
            url=f"https://app.devin.ai/sessions/{session_id}",
            status="working",
        )

    def get_session(self, session_id: str) -> DevinSessionStatus:
        return DevinSessionStatus(
            id=session_id,
            status="completed",
            outcome="pr_opened",
            summary="Mock Devin completed first-pass remediation and opened a PR.",
            pr_url="https://github.com/drinman/superset/pull/1",
        )


class LiveDevinClient:
    def __init__(self, api_key: str, max_acu_limit: int) -> None:
        self.api_key = api_key
        self.max_acu_limit = max_acu_limit

    def create_session(self, prompt: str) -> DevinSession:
        payload = self.request(
            "POST",
            "/sessions",
            body={
                "prompt": prompt,
                "title": "Devin issue remediation",
                "tags": ["devin-issue-remediator"],
                "max_acu_limit": self.max_acu_limit,
                "idempotent": True,
            },
        )
        return DevinSession(id=payload["session_id"], url=payload["url"], status="working")

    def get_session(self, session_id: str) -> DevinSessionStatus:
        payload = self.request("GET", f"/sessions/{session_id}")
        pr_url = (payload.get("pull_request") or {}).get("url")
        status, outcome = map_status(payload.get("status_enum"), pr_url)
        return DevinSessionStatus(
            id=session_id,
            status=status,
            outcome=outcome,
            summary=session_summary(payload),
            pr_url=pr_url,
        )

    def request(self, method: str, path: str, body: dict[str, Any] | None = None) -> dict[str, Any]:
        response = requests.request(
            method,
            f"{DEVIN_API_BASE_URL}{path}",
            headers={"Authorization": f"Bearer {self.api_key}"},
            json=body,
            timeout=REQUEST_TIMEOUT_SECONDS,
        )
        if response.status_code >= 400:
            raise RuntimeError(f"Devin API error: {method} {path} returned HTTP {response.status_code}")
        return response.json()


def map_status(status_enum: str | None, pr_url: str | None) -> tuple[str, str]:
    # status_enum "blocked" means Devin is idle awaiting instructions, not stuck:
    # with a PR it finished the work; without one a human needs to look.
    if status_enum == "blocked":
        if pr_url:
            return "completed", "pr_opened"
        return "waiting_for_user", "blocked_needs_human"
    if status_enum == "finished":
        return "completed", ("pr_opened" if pr_url else "investigation_completed")
    if status_enum == "expired":
        if pr_url:
            return "completed", "pr_opened"
        return "failed", "failed"
    return "working", "unknown"


def session_summary(payload: dict[str, Any]) -> str:
    messages = payload.get("messages") or []
    devin_messages = [
        message.get("message", "")
        for message in messages
        if message.get("type") == "devin_message"
    ]
    if devin_messages:
        return devin_messages[-1]
    structured_output = payload.get("structured_output")
    return str(structured_output) if structured_output else ""


DevinClient = MockDevinClient | LiveDevinClient
