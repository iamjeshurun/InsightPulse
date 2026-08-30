"""SQLite persistence with explicit transactions and JSON boundaries."""

from __future__ import annotations

import json
import sqlite3
import threading
import uuid
from contextlib import contextmanager
from datetime import UTC, datetime
from pathlib import Path
from typing import Any


class Repository:
    def __init__(self, path: Path) -> None:
        self.path = path
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = threading.RLock()
        self._initialize()

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.path, timeout=10, check_same_thread=False)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA journal_mode=WAL")
        connection.execute("PRAGMA foreign_keys=ON")
        return connection

    @contextmanager
    def _connection(self):
        connection = self._connect()
        try:
            with connection:
                yield connection
        finally:
            connection.close()

    def _initialize(self) -> None:
        with self._connection() as connection:
            connection.executescript(
                """
                CREATE TABLE IF NOT EXISTS analyses (
                    id TEXT PRIMARY KEY, text TEXT NOT NULL, source TEXT NOT NULL,
                    product TEXT NOT NULL, created_at TEXT NOT NULL,
                    model_version TEXT NOT NULL, predictions TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS jobs (
                    id TEXT PRIMARY KEY, status TEXT NOT NULL, total INTEGER NOT NULL,
                    completed INTEGER NOT NULL DEFAULT 0, error TEXT, created_at TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS feedback (
                    id TEXT PRIMARY KEY, analysis_id TEXT NOT NULL, task TEXT NOT NULL,
                    corrected_label TEXT NOT NULL, note TEXT, created_at TEXT NOT NULL,
                    FOREIGN KEY (analysis_id) REFERENCES analyses(id)
                );
                CREATE INDEX IF NOT EXISTS idx_analyses_created_at ON analyses(created_at DESC);
                CREATE INDEX IF NOT EXISTS idx_analyses_product ON analyses(product);
                """
            )

    @staticmethod
    def _analysis(row: sqlite3.Row) -> dict[str, Any]:
        value = dict(row)
        value["predictions"] = json.loads(value["predictions"])
        return value

    def save_analysis(self, record: dict[str, Any]) -> dict[str, Any]:
        with self._lock, self._connection() as connection:
            connection.execute(
                "INSERT INTO analyses VALUES (?, ?, ?, ?, ?, ?, ?)",
                (
                    record["id"], record["text"], record["source"], record["product"],
                    record["created_at"], record["model_version"], json.dumps(record["predictions"], sort_keys=True),
                ),
            )
        return record

    def list_analyses(self, limit: int = 100, product: str | None = None) -> list[dict[str, Any]]:
        sql, params = "SELECT * FROM analyses", []
        if product:
            sql, params = f"{sql} WHERE product = ?", [product]
        sql = f"{sql} ORDER BY created_at DESC LIMIT ?"
        params.append(limit)
        with self._connection() as connection:
            return [self._analysis(row) for row in connection.execute(sql, params)]

    def get_analysis(self, analysis_id: str) -> dict[str, Any] | None:
        with self._connection() as connection:
            row = connection.execute("SELECT * FROM analyses WHERE id = ?", (analysis_id,)).fetchone()
        return self._analysis(row) if row else None

    def create_job(self, total: int) -> dict[str, Any]:
        job = {"id": str(uuid.uuid4()), "status": "queued", "total": total, "completed": 0, "error": None}
        with self._connection() as connection:
            connection.execute(
                "INSERT INTO jobs VALUES (?, ?, ?, ?, ?, ?)",
                (job["id"], job["status"], total, 0, None, datetime.now(UTC).isoformat()),
            )
        return job

    def update_job(self, job_id: str, status: str, completed: int, error: str | None = None) -> None:
        with self._connection() as connection:
            connection.execute(
                "UPDATE jobs SET status = ?, completed = ?, error = ? WHERE id = ?",
                (status, completed, error, job_id),
            )

    def get_job(self, job_id: str) -> dict[str, Any] | None:
        with self._connection() as connection:
            row = connection.execute("SELECT id, status, total, completed, error FROM jobs WHERE id = ?", (job_id,)).fetchone()
        return dict(row) if row else None

    def save_feedback(self, analysis_id: str, task: str, corrected_label: str, note: str | None) -> dict[str, str]:
        record = {"id": str(uuid.uuid4()), "created_at": datetime.now(UTC).isoformat()}
        with self._connection() as connection:
            connection.execute(
                "INSERT INTO feedback VALUES (?, ?, ?, ?, ?, ?)",
                (record["id"], analysis_id, task, corrected_label, note, record["created_at"]),
            )
        return record

    def analytics(self) -> dict[str, Any]:
        rows = self.list_analyses(limit=10_000)
        result: dict[str, Any] = {
            "total": len(rows), "average_confidence": 0.0, "sentiment": {}, "intent": {},
            "urgency": {}, "products": {}, "by_day": {}, "low_confidence": 0,
        }
        confidences: list[float] = []
        for row in rows:
            result["products"][row["product"]] = result["products"].get(row["product"], 0) + 1
            day = str(row["created_at"])[:10]
            result["by_day"][day] = result["by_day"].get(day, 0) + 1
            for task in ("sentiment", "intent", "urgency"):
                prediction = row["predictions"][task]
                label = prediction["label"]
                result[task][label] = result[task].get(label, 0) + 1
                confidences.append(float(prediction["confidence"]))
            if min(float(value["confidence"]) for value in row["predictions"].values()) < 0.65:
                result["low_confidence"] += 1
        result["average_confidence"] = sum(confidences) / len(confidences) if confidences else 0.0
        return result
