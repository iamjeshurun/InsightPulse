"""Dependency-free Prometheus exposition for the local-first API."""

from __future__ import annotations

import threading
from collections import Counter
from time import monotonic


def _escape(value: str) -> str:
    return value.replace("\\", "\\\\").replace('"', '\\"').replace("\n", "\\n")


class MetricsRegistry:
    def __init__(self) -> None:
        self.started_at = monotonic()
        self.requests: Counter[tuple[str, str, int]] = Counter()
        self.request_seconds: Counter[tuple[str, str]] = Counter()
        self.predictions: Counter[tuple[str, str]] = Counter()
        self.confidence_sum: Counter[str] = Counter()
        self.shadow_disagreements: Counter[str] = Counter()
        self.shadow_comparisons: Counter[str] = Counter()
        self._lock = threading.Lock()

    def observe_request(self, method: str, route: str, status: int, seconds: float) -> None:
        route = route if route.startswith("/api/") or route in {"/health", "/ready", "/metrics"} else "other"
        with self._lock:
            self.requests[(method, route, status)] += 1
            self.request_seconds[(method, route)] += seconds

    def observe_predictions(self, predictions: dict) -> None:
        with self._lock:
            for task, value in predictions.items():
                self.predictions[(task, str(value["label"]))] += 1
                self.confidence_sum[task] += float(value["confidence"])

    def observe_shadow(self, primary: dict, shadow: dict) -> None:
        with self._lock:
            for task in primary:
                self.shadow_comparisons[task] += 1
                if primary[task]["label"] != shadow[task]["label"]:
                    self.shadow_disagreements[task] += 1

    def render(self) -> str:
        lines = [
            "# HELP insightpulse_uptime_seconds Process uptime.",
            "# TYPE insightpulse_uptime_seconds gauge",
            f"insightpulse_uptime_seconds {monotonic() - self.started_at:.6f}",
            "# HELP insightpulse_http_requests_total HTTP requests by route and status.",
            "# TYPE insightpulse_http_requests_total counter",
        ]
        with self._lock:
            for (method, route, status), count in sorted(self.requests.items()):
                lines.append(f'insightpulse_http_requests_total{{method="{_escape(method)}",route="{_escape(route)}",status="{status}"}} {count}')
            lines.extend(["# HELP insightpulse_http_request_duration_seconds_sum Total request duration.", "# TYPE insightpulse_http_request_duration_seconds_sum counter"])
            for (method, route), seconds in sorted(self.request_seconds.items()):
                lines.append(f'insightpulse_http_request_duration_seconds_sum{{method="{_escape(method)}",route="{_escape(route)}"}} {seconds:.6f}')
            lines.extend(["# HELP insightpulse_predictions_total Predictions by task and label.", "# TYPE insightpulse_predictions_total counter"])
            for (task, label), count in sorted(self.predictions.items()):
                lines.append(f'insightpulse_predictions_total{{task="{_escape(task)}",label="{_escape(label)}"}} {count}')
            lines.extend(["# HELP insightpulse_prediction_confidence_sum Sum of prediction confidence.", "# TYPE insightpulse_prediction_confidence_sum counter"])
            for task, value in sorted(self.confidence_sum.items()):
                lines.append(f'insightpulse_prediction_confidence_sum{{task="{_escape(task)}"}} {value:.6f}')
            lines.extend(["# HELP insightpulse_shadow_disagreements_total Primary and shadow label disagreements.", "# TYPE insightpulse_shadow_disagreements_total counter"])
            for task, value in sorted(self.shadow_disagreements.items()):
                lines.append(f'insightpulse_shadow_disagreements_total{{task="{_escape(task)}"}} {value}')
            lines.extend(["# HELP insightpulse_shadow_comparisons_total Primary and shadow comparisons.", "# TYPE insightpulse_shadow_comparisons_total counter"])
            for task, value in sorted(self.shadow_comparisons.items()):
                lines.append(f'insightpulse_shadow_comparisons_total{{task="{_escape(task)}"}} {value}')
        return "\n".join(lines) + "\n"
