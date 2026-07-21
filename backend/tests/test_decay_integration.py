import unittest
import importlib.util
from pathlib import Path
from datetime import datetime, timezone, timedelta
import pandas as pd

# Load api.routers.risk_corridors dynamically
MODULE_PATH = Path(__file__).resolve().parents[1] / 'api' / 'routers' / 'risk_corridors.py'
spec = importlib.util.spec_from_file_location('risk_corridors', MODULE_PATH)
risk_corridors = importlib.util.module_from_spec(spec)
spec.loader.exec_module(risk_corridors)

class TestDecayIntegration(unittest.TestCase):
    def test_decay_read_time_integration(self):
        """
        Verify that decay happens live at read-time and simulates correctly.
        """
        # 1. Prepare mock articles
        # Test corridor: malacca
        severity = 5.0
        now = datetime.now(timezone.utc)
        
        # Reference table values (severity=5, half-life=36h):
        # 0h:   5.0
        # 36h:  2.5
        # 72h:  1.25
        # 108h: 0.625
        # 144h: 0.3125
        # Sum of weights: 5.0 + 2.5 + 1.25 + 0.625 + 0.3125 = 9.6875
        # Score scaled to 100 with RAW_SCORE_CEILING = 25.0:
        # Expected Score: min(9.6875 / 25.0 * 100, 100) = 38.75% -> 38.8 rounded to 1 decimal place.
        
        mock_data = pd.DataFrame([
            {"date": (now - timedelta(hours=0)).isoformat(),   "corridor": "malacca", "severity": severity, "title": "Fresh"},
            {"date": (now - timedelta(hours=36)).isoformat(),  "corridor": "malacca", "severity": severity, "title": "36h"},
            {"date": (now - timedelta(hours=72)).isoformat(),  "corridor": "malacca", "severity": severity, "title": "72h"},
            {"date": (now - timedelta(hours=108)).isoformat(), "corridor": "malacca", "severity": severity, "title": "108h"},
            {"date": (now - timedelta(hours=144)).isoformat(), "corridor": "malacca", "severity": severity, "title": "144h"},
        ])
        
        # Convert date to datetime
        mock_data["_dt"] = pd.to_datetime(mock_data["date"], utc=True)
        
        # Calculate score at t=0 (now)
        raw_sum = 0.0
        for _, row in mock_data.iterrows():
            w = risk_corridors._decay_weight(row["_dt"], now)
            raw_sum += float(row["severity"]) * w
            
        score_t0 = round(min(raw_sum / risk_corridors.RAW_SCORE_CEILING * 100.0, 100.0), 1)
        self.assertAlmostEqual(raw_sum, 9.6875, places=4)
        self.assertEqual(score_t0, 38.8)
        print(f"Integration t=0: Raw Sum = {raw_sum:.4f}, Score = {score_t0}% (Expected: 38.8%)")

        # 2. Simulate time passing: 10 minutes later (without writing/fetching new articles)
        future_now = now + timedelta(minutes=10)
        raw_sum_future = 0.0
        for _, row in mock_data.iterrows():
            w = risk_corridors._decay_weight(row["_dt"], future_now)
            raw_sum_future += float(row["severity"]) * w
            
        score_t10 = round(min(raw_sum_future / risk_corridors.RAW_SCORE_CEILING * 100.0, 100.0), 1)
        
        # Verifies that score decreases as time passes
        self.assertLess(raw_sum_future, raw_sum)
        self.assertLessEqual(score_t10, score_t0)
        print(f"Integration t=10m: Raw Sum = {raw_sum_future:.4f}, Score = {score_t10}% (Score drifted down: {score_t0}% -> {score_t10}%)")

        # 3. Simulate scheduler run adding a fresh high-severity article (0h, severity=5)
        new_article = {"date": future_now.isoformat(), "corridor": "malacca", "severity": severity, "_dt": future_now}
        
        # Re-calculate score with new article at future_now
        raw_sum_new = 0.0
        for _, row in mock_data.iterrows():
            w = risk_corridors._decay_weight(row["_dt"], future_now)
            raw_sum_new += float(row["severity"]) * w
        # Add the new article
        raw_sum_new += float(new_article["severity"]) * risk_corridors._decay_weight(new_article["_dt"], future_now)
        
        score_new = round(min(raw_sum_new / risk_corridors.RAW_SCORE_CEILING * 100.0, 100.0), 1)
        self.assertGreater(raw_sum_new, raw_sum_future)
        self.assertGreater(score_new, score_t10)
        print(f"Integration + fresh: Raw Sum = {raw_sum_new:.4f}, Score = {score_new}% (Score jumped up from {score_t10}%)")

if __name__ == "__main__":
    unittest.main()
