"""Evaluate predictions against corrections accumulated through the API."""

from __future__ import annotations

import argparse
import json
import sqlite3
from collections import defaultdict
from datetime import UTC, datetime
from pathlib import Path
from typing import Any


def evaluate_feedback(database: Path) -> dict[str, Any]:
    connection = sqlite3.connect(database)
    connection.row_factory = sqlite3.Row
    try:
        rows = connection.execute("SELECT f.task, f.corrected_label, a.predictions FROM feedback f JOIN analyses a ON a.id = f.analysis_id").fetchall()
    finally:
        connection.close()
    by_task: dict[str, list[bool]] = defaultdict(list)
    for row in rows:
        predicted = json.loads(row["predictions"])[row["task"]]["label"]
        by_task[row["task"]].append(predicted == row["corrected_label"])
    return {"created_at": datetime.now(UTC).isoformat(), "examples": len(rows), "tasks": {task: {"examples": len(values), "agreement": sum(values) / len(values)} for task, values in sorted(by_task.items())}}


def main() -> None:
    parser = argparse.ArgumentParser(description="Evaluate predictions against human corrections")
    parser.add_argument("--database", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--minimum-agreement", type=float, default=0.7)
    parser.add_argument("--minimum-examples", type=int, default=30)
    args = parser.parse_args()
    report = evaluate_feedback(args.database)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    failing = [task for task, value in report["tasks"].items() if value["examples"] >= args.minimum_examples and value["agreement"] < args.minimum_agreement]
    print(json.dumps({"examples": report["examples"], "failing_tasks": failing, "output": str(args.output)}))
    if failing:
        raise SystemExit(2)


if __name__ == "__main__":
    main()
