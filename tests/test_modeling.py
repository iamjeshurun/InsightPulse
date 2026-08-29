import tempfile
import unittest
from pathlib import Path

from insightpulse_modeling.baseline import BaselineConfig, BaselineSuite
from insightpulse_modeling.io import write_jsonl
from insightpulse_modeling.runner import train_and_evaluate


def records(count: int = 36):
    sentiments = ("positive", "neutral", "negative")
    intents = ("praise", "feature_request", "complaint")
    urgencies = ("low", "medium", "high")
    words = ("excellent", "average", "broken")
    return [
        {
            "id": f"r{index:03}",
            "text": f"{words[index % 3]} product experience example {index}",
            "sentiment": sentiments[index % 3],
            "intent": intents[index % 3],
            "urgency": urgencies[index % 3],
        }
        for index in range(count)
    ]


class ModelingTests(unittest.TestCase):
    def test_suite_returns_probabilities_for_every_task(self):
        suite = BaselineSuite(BaselineConfig()).fit(records(30))
        result = suite.predict(["excellent product experience"])[0]
        self.assertEqual(set(result), {"sentiment", "intent", "urgency"})
        for task in result.values():
            self.assertAlmostEqual(sum(task["probabilities"].values()), 1.0)
            self.assertIn(task["label"], task["probabilities"])

    def test_runner_writes_auditable_artifacts(self):
        values = records()
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            data_dir, output_dir = root / "data", root / "model"
            data_dir.mkdir()
            write_jsonl(data_dir / "train.jsonl", values[:24])
            write_jsonl(data_dir / "validation.jsonl", values[24:30])
            write_jsonl(data_dir / "test.jsonl", values[30:])
            report = train_and_evaluate(data_dir, output_dir)
            self.assertEqual(report["tasks"]["sentiment"]["macro_f1"], 1.0)
            for name in (
                "baseline.joblib",
                "evaluation_report.json",
                "model_card.md",
                "run_config.json",
                "test_predictions.jsonl",
            ):
                self.assertTrue((output_dir / name).exists(), name)


if __name__ == "__main__":
    unittest.main()
