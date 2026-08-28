import json
import tempfile
import unittest
from pathlib import Path

from insightpulse_data.pipeline import PipelineConfig, run_pipeline


class PipelineTests(unittest.TestCase):
    def test_pipeline_quarantines_deduplicates_redacts_and_splits(self):
        fixture = Path(__file__).parents[1] / "data" / "sample_feedback.csv"
        config = PipelineConfig("test-data", "1.0.0", seed=7, train_ratio=0.6, validation_ratio=0.2)
        with tempfile.TemporaryDirectory() as first, tempfile.TemporaryDirectory() as second:
            report = run_pipeline(fixture, Path(first), config)
            run_pipeline(fixture, Path(second), config)

            self.assertEqual(report["counts"], {"input": 12, "accepted": 10, "invalid": 1, "duplicates": 1})
            self.assertEqual(report["split_sizes"], {"train": 6, "validation": 2, "test": 2})
            self.assertEqual(report["redactions"]["EMAIL"], 1)

            split_names = ("train.jsonl", "validation.jsonl", "test.jsonl")
            for name in split_names:
                self.assertEqual((Path(first) / name).read_bytes(), (Path(second) / name).read_bytes())

            processed = "".join((Path(first) / name).read_text() for name in split_names)
            self.assertNotIn("alex@example.com", processed)
            self.assertNotIn("555-0199", processed)
            self.assertIn("[EMAIL]", processed)
            quarantine = [json.loads(line) for line in (Path(first) / "quarantine.jsonl").read_text().splitlines()]
            self.assertEqual(quarantine[0]["row"], 13)


if __name__ == "__main__":
    unittest.main()
