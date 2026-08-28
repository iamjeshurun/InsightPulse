import unittest

from insightpulse_data.models import parse_record


class ParseRecordTests(unittest.TestCase):
    def test_normalizes_valid_record(self):
        record, errors = parse_record(
            {
                "id": " 42 ",
                "text": "Works   very well",
                "source": "REVIEW",
                "product": " Core  App ",
                "created_at": "2026-08-01",
                "sentiment": "POSITIVE",
            }
        )
        self.assertEqual(errors, [])
        self.assertEqual(record.id, "42")
        self.assertEqual(record.text, "Works very well")
        self.assertEqual(record.source, "review")
        self.assertEqual(record.product, "Core App")
        self.assertEqual(record.sentiment, "positive")

    def test_collects_multiple_validation_errors(self):
        record, errors = parse_record(
            {"id": "", "text": "x", "source": "email", "product": "", "created_at": "yesterday"}
        )
        self.assertIsNone(record)
        self.assertGreaterEqual(len(errors), 5)


if __name__ == "__main__":
    unittest.main()
