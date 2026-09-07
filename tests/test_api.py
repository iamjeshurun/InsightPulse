import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from fastapi.testclient import TestClient

from insightpulse_api.app import create_app


class ApiTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.client = TestClient(create_app(Path(self.temporary.name) / "test.db"))

    def tearDown(self):
        self.client.close()
        self.temporary.cleanup()

    def test_health_and_validation(self):
        self.assertEqual(self.client.get("/health").status_code, 200)
        self.assertEqual(self.client.get("/ready").status_code, 200)
        self.assertIn("insightpulse_http_requests_total", self.client.get("/metrics").text)
        self.assertEqual(self.client.post("/api/v1/analyze", json={"text": "x"}).status_code, 422)

    def test_analysis_persistence_analytics_and_feedback(self):
        response = self.client.post(
            "/api/v1/analyze",
            json={"text": "Excellent support solved my problem fast.", "source": "review", "product": "Support"},
        )
        self.assertEqual(response.status_code, 201)
        analysis = response.json()
        self.assertEqual(analysis["predictions"]["sentiment"]["label"], "positive")
        self.assertIn("aspect", analysis["predictions"])
        self.assertEqual(self.client.get(f"/api/v1/analyses/{analysis['id']}").status_code, 200)
        summary = self.client.get("/api/v1/analytics/summary").json()
        self.assertEqual(summary["total"], 1)
        feedback = self.client.post(
            "/api/v1/feedback",
            json={"analysis_id": analysis["id"], "task": "sentiment", "corrected_label": "neutral"},
        )
        self.assertEqual(feedback.status_code, 201)

    def test_batch_and_background_job(self):
        records = {
            "records": [
                {"text": "The export is broken again.", "product": "Exports"},
                {"text": "Please add scheduled reports.", "product": "Reports", "source": "survey"},
            ]
        }
        self.assertEqual(len(self.client.post("/api/v1/analyze/batch", json=records).json()["analyses"]), 2)
        job = self.client.post("/api/v1/jobs", json=records).json()
        current = self.client.get(f"/api/v1/jobs/{job['id']}").json()
        self.assertEqual(current["status"], "completed")
        self.assertEqual(current["completed"], 2)

    def test_rate_limit_is_configurable(self):
        with patch.dict("os.environ", {"INSIGHTPULSE_RATE_LIMIT_PER_MINUTE": "3"}):
            with TestClient(create_app(Path(self.temporary.name) / "rl.db")) as client:
                codes = [client.get("/health").status_code for _ in range(5)]
        self.assertEqual(codes[:3], [200, 200, 200])
        self.assertEqual(codes[-1], 429)

    def test_compiled_dashboard_can_be_served(self):
        frontend = Path(self.temporary.name) / "frontend"
        frontend.mkdir()
        (frontend / "index.html").write_text("<h1>InsightPulse</h1>", encoding="utf-8")
        with patch.dict("os.environ", {"INSIGHTPULSE_FRONTEND_DIST": str(frontend)}):
            with TestClient(create_app(Path(self.temporary.name) / "dashboard.db")) as client:
                response = client.get("/")
        self.assertEqual(response.status_code, 200)
        self.assertIn("InsightPulse", response.text)


if __name__ == "__main__":
    unittest.main()
