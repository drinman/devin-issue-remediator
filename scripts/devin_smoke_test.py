#!/usr/bin/env python3
"""Smoke test for the Devin API: prove auth, create one tiny capped session, poll it.

Prints raw API responses on purpose — confirms the real request/response contract
independently of the app.
"""
from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

import requests

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.config import settings  # noqa: E402


DEVIN_API_BASE_URL = "https://api.devin.ai/v1"
TERMINAL_STATUSES = {"finished", "expired", "blocked"}
DEFAULT_SMOKE_PROMPT = (
    "Reply with a one-sentence confirmation that you received this prompt, then finish "
    "the session. Do not clone any repository and do not make any code changes."
)
WATCH_POLL_SECONDS = 30
WATCH_TIMEOUT_SECONDS = 20 * 60


def main() -> None:
    parser = argparse.ArgumentParser(description="Devin API smoke test and session status poller.")
    action = parser.add_mutually_exclusive_group(required=True)
    action.add_argument("--check-auth", action="store_true", help="List sessions to prove the API key works. Costs no ACUs.")
    action.add_argument("--create", action="store_true", help="Create one tiny ACU-capped session.")
    action.add_argument("--status", metavar="SESSION_ID", help="Fetch one session's status.")
    parser.add_argument("--prompt", default=DEFAULT_SMOKE_PROMPT, help="Prompt for --create.")
    parser.add_argument("--max-acu", type=int, default=1, help="ACU budget cap for --create (default: 1).")
    parser.add_argument("--watch", action="store_true", help="With --status: poll until a terminal state.")
    args = parser.parse_args()

    require_api_key()
    if args.check_auth:
        check_auth()
    elif args.create:
        create_session(prompt=args.prompt, max_acu=args.max_acu)
    else:
        get_status(args.status, watch=args.watch)


def require_api_key() -> None:
    if not settings.devin_api_key:
        raise SystemExit(
            "DEVIN_API_KEY is empty. Copy .env.example to .env and set a personal API key "
            "from app.devin.ai -> Settings -> API Keys."
        )


def check_auth() -> None:
    payload = devin_request("GET", "/sessions")
    sessions = payload.get("sessions", payload)
    count = len(sessions) if isinstance(sessions, list) else "unknown"
    print(f"\nAuth OK. Visible sessions: {count}.")


def create_session(prompt: str, max_acu: int) -> None:
    payload = devin_request(
        "POST",
        "/sessions",
        body={
            "prompt": prompt,
            "title": "API smoke test",
            "tags": ["smoke-test"],
            "max_acu_limit": max_acu,
            "idempotent": True,
        },
    )
    print(f"\nSession created: {payload.get('session_id')}")
    print(f"Watch it live: {payload.get('url')}")
    print(f"New session: {payload.get('is_new_session')} (idempotent=true reuses an identical open session)")
    print(f"Next: python scripts/devin_smoke_test.py --status {payload.get('session_id')} --watch")


def get_status(session_id: str, watch: bool) -> None:
    deadline = time.monotonic() + WATCH_TIMEOUT_SECONDS
    while True:
        payload = devin_request("GET", f"/sessions/{session_id}")
        status = payload.get("status_enum") or payload.get("status")
        pull_request = (payload.get("pull_request") or {}).get("url")
        print(f"\nstatus_enum: {status}")
        print(f"pull_request: {pull_request}")
        if not watch or status in TERMINAL_STATUSES:
            return
        if time.monotonic() > deadline:
            raise SystemExit(f"Gave up after {WATCH_TIMEOUT_SECONDS // 60} minutes; session still {status}.")
        print(f"Polling again in {WATCH_POLL_SECONDS}s (terminal states: {', '.join(sorted(TERMINAL_STATUSES))})...")
        time.sleep(WATCH_POLL_SECONDS)


def devin_request(method: str, path: str, body: dict | None = None) -> dict:
    response = requests.request(
        method,
        f"{DEVIN_API_BASE_URL}{path}",
        headers={"Authorization": f"Bearer {settings.devin_api_key}"},
        json=body,
        timeout=30,
    )
    print(f"{method} {path} -> HTTP {response.status_code}")
    payload = response_payload(response)
    print(json.dumps(payload, indent=2))
    if response.status_code >= 400:
        raise SystemExit(f"Devin API error: HTTP {response.status_code}")
    return payload


def response_payload(response: requests.Response) -> dict:
    try:
        return response.json()
    except ValueError:
        return {"raw_text": response.text}


if __name__ == "__main__":
    main()
