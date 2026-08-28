import unittest

from insightpulse_data.privacy import redact_pii


class PrivacyTests(unittest.TestCase):
    def test_redacts_supported_identifiers(self):
        text, counts = redact_pii(
            "Email me@example.com, call +1 (212) 555-0199, and check order ORD-12345."
        )
        self.assertNotIn("me@example.com", text)
        self.assertNotIn("555-0199", text)
        self.assertNotIn("ORD-12345", text)
        self.assertEqual(counts, {"EMAIL": 1, "PHONE": 1, "CUSTOMER_ID": 1})


if __name__ == "__main__":
    unittest.main()
