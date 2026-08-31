import json
import sqlite3
import tempfile
import unittest
from pathlib import Path

from insightpulse_monitoring.continuous_eval import evaluate_feedback
from insightpulse_monitoring.drift import drift_report
from insightpulse_monitoring.metrics import MetricsRegistry


class MonitoringTests(unittest.TestCase):
    def test_drift_report_detects_large_distribution_shift(self):
        reference = [{"text": "short review", "source": "review", "product": "Core"}] * 20
        current = [{"text": "word " * 60, "source": "support_ticket", "product": "Billing"}] * 20
        report = drift_report(reference, current)
        self.assertEqual(report["status"], "drift_detected")
        self.assertTrue(report["features"]["source"]["drifted"])

    def test_metrics_use_prometheus_text_format(self):
        metrics = MetricsRegistry()
        metrics.observe_request("POST", "/api/v1/analyze", 201, 0.02)
        metrics.observe_predictions({"sentiment": {"label": "positive", "confidence": 0.9}})
        rendered = metrics.render()
        self.assertIn("insightpulse_http_requests_total", rendered)
        self.assertIn('label="positive"', rendered)

    def test_continuous_evaluation_joins_human_feedback(self):
        with tempfile.TemporaryDirectory() as temporary:
            database = Path(temporary) / "feedback.db"
            connection = sqlite3.connect(database)
            connection.executescript("CREATE TABLE analyses (id TEXT PRIMARY KEY, predictions TEXT); CREATE TABLE feedback (analysis_id TEXT, task TEXT, corrected_label TEXT);")
            connection.execute("INSERT INTO analyses VALUES (?, ?)", ("a1", json.dumps({"sentiment": {"label": "positive"}})))
            connection.execute("INSERT INTO feedback VALUES (?, ?, ?)", ("a1", "sentiment", "positive"))
            connection.commit()
            connection.close()
            report = evaluate_feedback(database)
            self.assertEqual(report["tasks"]["sentiment"]["agreement"], 1.0)


if __name__ == "__main__":
    unittest.main()
