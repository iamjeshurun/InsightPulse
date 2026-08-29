import unittest

from insightpulse_modeling.evaluation import behavior_slice, expected_calibration_error


class EvaluationTests(unittest.TestCase):
    def test_calibration_error_is_zero_for_perfect_confidence(self):
        self.assertEqual(expected_calibration_error([1.0, 1.0], [True, True]), 0.0)

    def test_behavior_slices(self):
        self.assertEqual(behavior_slice("This is not working"), "negation")
        self.assertEqual(behavior_slice("Can you help?"), "question")
        self.assertEqual(behavior_slice("Excellent support"), "short")


if __name__ == "__main__":
    unittest.main()
