import csv
import io
import json
import tempfile
import unittest
import zipfile
from pathlib import Path

from insightpulse_data.cfpb import archive_exports_for, classify_aspect, fetch_archived_complaints, prepare_cfpb


class CfpbTests(unittest.TestCase):
    def test_aspect_taxonomy_uses_structured_issue_fields(self):
        self.assertEqual(classify_aspect("Incorrect information on your credit report"), "credit_reporting")
        self.assertEqual(classify_aspect("Problem with a lender", "Charged an overdraft fee"), "fees_interest")
        self.assertEqual(classify_aspect("Unauthorized card transaction"), "fraud_security")

    def test_archive_exports_are_chosen_by_month_received(self):
        self.assertEqual(archive_exports_for("2024-01-01", "2024-02-01"), ["CCDB_Export_5_September_2023_through_March_2024"])
        self.assertEqual(
            archive_exports_for("2024-03-15", "2024-04-15"),
            ["CCDB_Export_5_September_2023_through_March_2024", "CCDB_Export_6_April_2024_through_July_2024"],
        )

    def test_requests_after_the_narrative_cutoff_explain_why(self):
        self.assertEqual(archive_exports_for("2026-08-01", "2026-08-15"), ["CCDB_Export_21_August_2026"])
        with self.assertRaisesRegex(ValueError, "stopped publishing complaint narratives on 2026-08-14"):
            archive_exports_for("2026-08-01", "2026-09-01")

    def test_archive_slice_filters_dates_dedupes_round_robins_and_drops_geography(self):
        columns = ("Date received", "Product", "Sub-product", "Issue", "Sub-issue", "Consumer complaint narrative", "State", "ZIP code", "Complaint ID")
        rows = [
            ("2024-01-02", "Mortgage", "", "Trouble during payment process", "", "Payment misapplied.", "VA", "22102", "3"),
            ("2024-01-01", "Mortgage", "", "Trouble during payment process", "", "Escrow was wrong.", "VA", "22102", "2"),
            ("2024-01-01", "Credit card", "", "Fees or interest", "", "Late fee charged twice.", "VA", "22102", "4"),
            ("2024-01-01", "Credit card", "", "Fees or interest", "", "late fee  CHARGED twice.", "VA", "22102", "5"),
            ("2024-01-03", "Mortgage", "", "Trouble during payment process", "", "", "VA", "22102", "6"),
            ("2024-02-01", "Mortgage", "", "Trouble during payment process", "", "Outside the window.", "VA", "22102", "7"),
        ]
        with tempfile.TemporaryDirectory() as temporary:
            cache = Path(temporary) / "cache"
            cache.mkdir()
            buffer = io.StringIO()
            writer = csv.writer(buffer)
            writer.writerow(columns)
            writer.writerows(rows)
            with zipfile.ZipFile(cache / "CCDB_Export_5_September_2023_through_March_2024.zip", "w") as archive:
                archive.writestr("export.csv", buffer.getvalue())
            output = Path(temporary) / "slice.jsonl"
            report = fetch_archived_complaints(
                output, date_min="2024-01-01", date_max="2024-02-01", limit=10,
                products=("Mortgage", "Credit card"), cache_dir=cache,
            )
            written = [json.loads(line) for line in output.read_text().splitlines()]
        self.assertEqual([row["complaint_id"] for row in written], ["4", "2", "3"])
        self.assertEqual(report["skipped_exact_duplicates"], 1)
        self.assertNotIn("state", written[0])
        self.assertNotIn("zip_code", written[0])

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
