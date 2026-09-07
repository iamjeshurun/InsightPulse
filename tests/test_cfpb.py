import json
import csv
import tempfile
import unittest
from pathlib import Path

from insightpulse_data.cfpb import _search_after, classify_aspect, prepare_cfpb


class CfpbTests(unittest.TestCase):
    def test_aspect_taxonomy_uses_structured_issue_fields(self):
        self.assertEqual(classify_aspect("Incorrect information on your credit report"), "credit_reporting")
        self.assertEqual(classify_aspect("Problem with a lender", "Charged an overdraft fee"), "fees_interest")
        self.assertEqual(classify_aspect("Unauthorized card transaction"), "fraud_security")

    def test_search_after_token_joins_sort_values(self):
        self.assertEqual(_search_after({"sort": [1546300854000, "3113804"]}), "1546300854000_3113804")
        self.assertIsNone(_search_after({}))

    def test_preparation_redacts_deduplicates_and_omits_geography(self):
        rows = [
            {
                "complaint_id": "1",
                "narrative": "Email me at person@example.com about the unauthorized transfer.",
                "date_received": "2024-01-01",
                "product": "Money transfer",
                "issue": "Unauthorized transfer",
                "sub_issue": "",
                "state": "VA",
                "zip_code": "22102",
            },
            {
                "complaint_id": "2",
                "narrative": "Email me at person@example.com about the unauthorized transfer.",
                "date_received": "2024-01-02",
                "product": "Money transfer",
                "issue": "Unauthorized transfer",
                "sub_issue": "",
            },
        ]
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            source = root / "source.jsonl"
            source.write_text("".join(json.dumps(row) + "\n" for row in rows), encoding="utf-8")
            report = prepare_cfpb(source, root / "out", seed=1)
            self.assertEqual(sum(report["split_sizes"].values()), 1)
            combined = "".join((root / "out" / f"{name}.jsonl").read_text() for name in ("train", "validation", "test"))
            self.assertIn("[EMAIL]", combined)
            self.assertNotIn("person@example.com", combined)
            self.assertNotIn('"state"', combined)
            self.assertEqual(report["aspect_distribution"], {"fraud_security": 1})

    def test_preparation_accepts_official_bulk_csv_columns(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            source = root / "complaints.csv"
            with source.open("w", encoding="utf-8", newline="") as handle:
                writer = csv.DictWriter(handle, fieldnames=("Complaint ID", "Consumer complaint narrative", "Date received", "Product", "Sub-product", "Issue", "Sub-issue"))
                writer.writeheader()
                writer.writerow({"Complaint ID": "99", "Consumer complaint narrative": "The mortgage servicing payment was applied incorrectly.", "Date received": "2019-01-01T12:00:00Z", "Product": "Mortgage", "Sub-product": "Home loan", "Issue": "Trouble during payment process", "Sub-issue": "Payment was not applied"})
            report = prepare_cfpb(source, root / "out")
            self.assertEqual(sum(report["split_sizes"].values()), 1)
            self.assertEqual(report["aspect_distribution"], {"payments": 1})


if __name__ == "__main__":
    unittest.main()
