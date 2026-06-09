from __future__ import annotations

import json
import sqlite3
from pathlib import Path
from typing import Any


RUN_COLUMNS = [
    "run_id",
    "trigger_type",
    "issue_number",
    "issue_title",
    "issue_url",
    "issue_body",
    "labels_json",
    "task_type",
    "repo_url",
    "devin_session_id",
    "devin_session_url",
    "status",
    "outcome",
    "pr_url",
    "requires_human_review",
    "triggered_at",
    "first_response_at",
    "completed_at",
    "duration_seconds",
    "estimated_manual_triage_minutes",
    "error_message",
    "created_at",
    "updated_at",
]


class RunStorage:
    def __init__(self, database_url: str) -> None:
        self.database_path = database_path_from_url(database_url)
        self.database_path.parent.mkdir(parents=True, exist_ok=True)
        self.initialize()

    def initialize(self) -> None:
        with self.connect() as connection:
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS runs (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    run_id TEXT NOT NULL UNIQUE,
                    trigger_type TEXT NOT NULL,
                    issue_number INTEGER NOT NULL,
                    issue_title TEXT NOT NULL,
                    issue_url TEXT NOT NULL,
                    issue_body TEXT NOT NULL,
                    labels_json TEXT NOT NULL,
                    task_type TEXT NOT NULL,
                    repo_url TEXT NOT NULL,
                    devin_session_id TEXT,
                    devin_session_url TEXT,
                    status TEXT NOT NULL,
                    outcome TEXT NOT NULL,
                    pr_url TEXT,
                    requires_human_review INTEGER NOT NULL,
                    triggered_at TEXT NOT NULL,
                    first_response_at TEXT,
                    completed_at TEXT,
                    duration_seconds REAL,
                    estimated_manual_triage_minutes INTEGER NOT NULL,
                    error_message TEXT,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                )
                """
            )

    def connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.database_path)
        connection.row_factory = sqlite3.Row
        return connection

    def create_run(self, values: dict[str, Any]) -> dict[str, Any]:
        columns = ", ".join(RUN_COLUMNS)
        placeholders = ", ".join("?" for _ in RUN_COLUMNS)
        row_values = [self.to_database_value(values.get(column)) for column in RUN_COLUMNS]
        with self.connect() as connection:
            connection.execute(
                f"INSERT INTO runs ({columns}) VALUES ({placeholders})",
                row_values,
            )
        run = self.get_run(values["run_id"])
        if run is None:
            raise RuntimeError("Run was not saved")
        return run

    def list_runs(self) -> list[dict[str, Any]]:
        with self.connect() as connection:
            rows = connection.execute("SELECT * FROM runs ORDER BY created_at DESC").fetchall()
        return [public_run(dict(row)) for row in rows]

    def get_run(self, run_id: str) -> dict[str, Any] | None:
        with self.connect() as connection:
            row = connection.execute("SELECT * FROM runs WHERE run_id = ?", (run_id,)).fetchone()
        return public_run(dict(row)) if row else None

    def update_run(self, run_id: str, values: dict[str, Any]) -> dict[str, Any]:
        assignments = ", ".join(f"{column} = ?" for column in values)
        row_values = [self.to_database_value(value) for value in values.values()]
        with self.connect() as connection:
            connection.execute(
                f"UPDATE runs SET {assignments} WHERE run_id = ?",
                [*row_values, run_id],
            )
        run = self.get_run(run_id)
        if run is None:
            raise RuntimeError("Run was not found after update")
        return run

    @staticmethod
    def to_database_value(value: Any) -> Any:
        if isinstance(value, bool):
            return int(value)
        if isinstance(value, list):
            return json.dumps(value)
        return value


def database_path_from_url(database_url: str) -> Path:
    prefix = "sqlite:///"
    if not database_url.startswith(prefix):
        raise ValueError("Only sqlite:/// DATABASE_URL values are supported")
    return Path(database_url.removeprefix(prefix))


def public_run(row: dict[str, Any]) -> dict[str, Any]:
    row["labels"] = json.loads(row.pop("labels_json"))
    row["requires_human_review"] = bool(row["requires_human_review"])
    return row
