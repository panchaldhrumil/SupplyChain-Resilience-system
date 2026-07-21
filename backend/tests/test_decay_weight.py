import unittest
import importlib.util
from pathlib import Path

# Load api.routers.risk_corridors dynamically
MODULE_PATH = Path(__file__).resolve().parents[1] / 'api' / 'routers' / 'risk_corridors.py'
spec = importlib.util.spec_from_file_location('risk_corridors', MODULE_PATH)
risk_corridors = importlib.util.module_from_spec(spec)
spec.loader.exec_module(risk_corridors)

class TestDecayWeight(unittest.TestCase):
    def test_decay_weight_reference_table(self):
        """
        Verify unit tests against the reference table (severity=5, tolerance +/-0.5%).
        """
        severity = 5.0
        
        # Test cases: (hours_elapsed, expected_weight)
        test_cases = [
            (0, 5.0),
            (36, 2.5),
            (72, 1.25),
            (108, 0.625),
            (144, 0.3125),
        ]
        
        for hours, expected in test_cases:
            with self.subTest(hours=hours):
                actual = risk_corridors.decay_weight(severity, float(hours))
                # Tolerance is +/-0.5% of the expected value
                # Using max(expected * 0.005, 1e-9) to handle any floating precision details safely
                tolerance = expected * 0.005
                self.assertAlmostEqual(
                    actual,
                    expected,
                    delta=tolerance,
                    msg=f"At {hours} hours, expected weight {expected} but got {actual} (tolerance is +/- {tolerance})"
                )
                print(f"PASS: {hours} hours -> expected {expected}, got {actual:.6f} (diff: {abs(actual-expected):.6f})")

if __name__ == "__main__":
    unittest.main()
