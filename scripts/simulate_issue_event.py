#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path

import requests


DEMO_ISSUES = {
    1: {
        "title": "Fix focused utility test failure in Superset fork",
        "body": "A focused utility test is failing after a recent change to boolean parsing.",
        "labels": ["bug", "devin:auto-remediate", "devin:ci-failure"],
    },
    2: {
        "title": "Clean up small code quality issue in targeted Superset utility module",
        "body": "There is a small targeted code quality issue in a Superset utility module.",
        "labels": ["devin:auto-remediate", "devin:code-quality"],
    },
    3: {
        "title": "Improve developer guidance for running focused backend tests",
        "body": "The developer documentation should make it easier to run a focused backend test locally.",
        "labels": ["devin:auto-remediate", "devin:docs"],
    },
}


def main() -> None:
    parser = argparse.ArgumentParser(description="Send a fake GitHub issue event to the local app.")
    parser.add_argument("--base-url", default="http://localhost:8000")
    parser.add_argument("--issue-number", type=int)
    args = parser.parse_args()

    payload_path = Path(__file__).resolve().parents[1] / "sample_payloads" / "github_issue_labeled.json"
    payload = json.loads(payload_path.read_text())
    if args.issue_number is not None:
        apply_demo_issue(payload, args.issue_number)

    response = requests.post(f"{args.base_url}/webhooks/github", json=payload, timeout=10)
    response.raise_for_status()
    print(json.dumps(response.json(), indent=2))


def apply_demo_issue(payload: dict, issue_number: int) -> None:
    issue = DEMO_ISSUES.get(issue_number)
    if issue is None:
        raise SystemExit(f"Unknown demo issue {issue_number}. Use one of: 1, 2, 3.")

    payload["issue"]["number"] = issue_number
    payload["issue"]["title"] = issue["title"]
    payload["issue"]["body"] = issue["body"]
    payload["issue"]["html_url"] = f"https://github.com/drinman/superset/issues/{issue_number}"
    payload["issue"]["url"] = f"https://api.github.com/repos/drinman/superset/issues/{issue_number}"
    payload["issue"]["labels"] = [{"name": label} for label in issue["labels"]]


if __name__ == "__main__":
    main()
