from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha1


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
