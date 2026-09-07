import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import joblib

from insightpulse_api.model_service import TASKS, ModelService
from insightpulse_modeling.baseline import BaselineConfig, BaselineSuite

_MODEL_ENV = {f"INSIGHTPULSE_{task.upper()}_MODEL_PATH": "" for task in TASKS}
_MODEL_ENV["INSIGHTPULSE_MODEL_PATH"] = ""


def _sentiment_suite() -> BaselineSuite:
    rows = [
        {"text": f"{word} product number {index}", "sentiment": label}
        for index, (word, label) in enumerate(
            [("excellent", "positive"), ("terrible", "negative"), ("fine", "neutral")] * 8
        )
    ]
    return BaselineSuite(BaselineConfig(tasks=("sentiment",))).fit(rows)


class ModelServiceTests(unittest.TestCase):
    def test_lexicon_only_when_nothing_configured(self):
        with patch.dict(os.environ, _MODEL_ENV):
            service = ModelService()
        self.assertEqual(service.version, "demo-lexicon-2")
        prediction = service.predict(["Support was excellent and fast"])[0]
        self.assertEqual(set(prediction), {"sentiment", "intent", "urgency", "aspect"})

    def test_trained_task_overlays_lexicon_for_the_rest(self):
        with tempfile.TemporaryDirectory() as temporary:
            model_file = Path(temporary) / "sentiment.joblib"
            joblib.dump(_sentiment_suite(), model_file)
            with patch.dict(os.environ, {**_MODEL_ENV, "INSIGHTPULSE_SENTIMENT_MODEL_PATH": str(model_file)}):
                service = ModelService()
            self.assertIn("sentiment:tfidf_logistic_regression", service.version)
            self.assertIn("urgency:lexicon", service.version)
            prediction = service.predict(["excellent product number 999"])[0]
            self.assertEqual(prediction["sentiment"]["label"], "positive")
            self.assertIn("aspect", prediction)


if __name__ == "__main__":
    unittest.main()
