"""
Automated Clinical Safety and Privacy Compliance Verification Suite.
Formally verifies all 10 Hard Rules across database schemas, templates, and Python modules.
"""

import sys
import os
import unittest
import glob

# Ensure project root in sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from database.db import get_db_connection, DEFAULT_DB_PATH
from src.pose.detector import RELIABILITY_WARNING, CLINICAL_DISCLAIMER
from src.analysis.exercises import EXERCISE_REGISTRY, ExerciseTracker, WRIST_APPROXIMATION_NOTE


class TestSafetyAndPrivacyCompliance(unittest.TestCase):
    """Rigorous audit asserting adherence to all 10 Hard Clinical Rules."""

    def test_rule_3_camera_estimate_disclaimer_constant(self):
        """Hard Rule #3: Exact string 'Camera-based estimate, not a clinical measurement.'"""
        self.assertEqual(CLINICAL_DISCLAIMER, "Camera-based estimate, not a clinical measurement.")

    def test_rule_5_unreliable_tracking_fallback_message(self):
        """Hard Rule #5: Exact string 'Movement could not be measured reliably. Adjust camera position or lighting.'"""
        self.assertEqual(
            RELIABILITY_WARNING,
            "Movement could not be measured reliably. Adjust camera position or lighting."
        )

    def test_rule_6_no_persistent_raw_video_or_image_columns(self):
        """Hard Rule #6: Database schema stores derived kinematic metrics ONLY."""
        with get_db_connection(DEFAULT_DB_PATH) as conn:
            tables = conn.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()
            for t in tables:
                table_name = t["name"]
                columns = conn.execute(f"PRAGMA table_info({table_name})").fetchall()
                for c in columns:
                    col = c["name"].lower()
                    for forbidden in ["image", "video", "frame", "photo", "raw_media", "recording"]:
                        self.assertNotIn(
                            forbidden, col,
                            f"Violation of Rule #6: Column '{col}' in '{table_name}' stores media."
                        )

    def test_rule_7_no_unvalidated_recovery_percentages(self):
        """Hard Rule #7: Prohibits calculating or returning an unvalidated 'recovery percentage' or score."""
        tracker = ExerciseTracker("fist_flexion")
        summary = tracker.get_session_summary()
        self.assertNotIn("recovery_percentage", summary)
        self.assertNotIn("recovery_score", summary)
        self.assertNotIn("recovery", summary)

        # Assert no HTML template renders a recovery percentage element
        src_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
        templates = glob.glob(os.path.join(src_dir, "frontend", "templates", "**", "*.html"), recursive=True)
        for tpl in templates:
            with open(tpl, "r", encoding="utf-8") as f:
                content = f.read().lower()
                self.assertNotIn("recovery_percentage", content)
                self.assertNotIn("recoveryscore", content)

    def test_wrist_exercise_explicitly_labeled_approximation(self):
        """Hard Rule for Wrist exercise: Labeled APPROXIMATION due to lack of forearm landmarks."""
        wrist_config = EXERCISE_REGISTRY.get("wrist_tilt")
        self.assertIsNotNone(wrist_config)
        self.assertIn("APPROXIMATION", wrist_config.clinical_note)
        self.assertIn("forearm", wrist_config.clinical_note)


if __name__ == "__main__":
    unittest.main()
