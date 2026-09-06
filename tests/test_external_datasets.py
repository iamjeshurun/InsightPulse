import csv
import json
import tempfile
import unittest
import zipfile
from pathlib import Path

from insightpulse_data.external_datasets import DYNASENT_MEMBERS, prepare_bitext, prepare_dynasent


class ExternalDatasetTests(unittest.TestCase):
    def test_bitext_adapter_is_deterministic_and_preserves_intents(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            source = root / "bitext.csv"
            with source.open("w", encoding="utf-8", newline="") as handle:
                writer = csv.DictWriter(handle, fieldnames=("flags", "instruction", "category", "intent", "response"))
                writer.writeheader()
                for index in range(60):
                    writer.writerow({"flags": "B", "instruction": f"request {index}", "category": "ORDER", "intent": "cancel_order" if index % 2 else "track_order", "response": "ok"})
            first, second = root / "first", root / "second"
            report = prepare_bitext(source, first, seed=7)
            prepare_bitext(source, second, seed=7)
            self.assertEqual(sum(report["split_sizes"].values()), 60)
            self.assertTrue(all(size > 0 for size in report["split_sizes"].values()))
            self.assertEqual((first / "train.jsonl").read_bytes(), (second / "train.jsonl").read_bytes())
            record = json.loads((first / "train.jsonl").read_text().splitlines()[0])
            self.assertIn(record["intent"], {"cancel_order", "track_order"})

    def test_dynasent_adapter_preserves_official_splits(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            archive = root / "dynasent.zip"
            with zipfile.ZipFile(archive, "w") as bundle:
                for index, member in enumerate(DYNASENT_MEMBERS.values()):
                    rows = [
                        {"text_id": f"r{index}-1", "sentence": "A useful product.", "gold_label": "positive"},
                        {"text_id": f"r{index}-2", "sentence": "Ambiguous.", "gold_label": "mixed"},
                    ]
                    bundle.writestr(member, "".join(json.dumps(row) + "\n" for row in rows))
            report = prepare_dynasent(archive, root / "out")
            self.assertEqual(report["split_sizes"], {"train": 1, "validation": 1, "test": 1})


if __name__ == "__main__":
    unittest.main()
