"""
Unit and Integration Tests for Patient Web Views and UI Templates.
Tests page routing, patient authentication gating, SVG anatomy rendering,
and live workout telemetry endpoints.
"""

import sys
import os
import unittest
import tempfile
import json
import gc

# Ensure project root in sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from backend.app import create_app
from database.seed import seed_database


class TestPatientViews(unittest.TestCase):
    """Test Patient dashboard and live workout views."""

    def setUp(self):
        self.temp_fd, self.temp_db_path = tempfile.mkstemp(suffix=".db")
        os.close(self.temp_fd)
        seed_database(self.temp_db_path)

        self.app = create_app(
            db_path=self.temp_db_path,
            test_config={"TESTING": True, "SECRET_KEY": "test-patient-secret"}
        )
        self.client = self.app.test_client()

    def tearDown(self):
        gc.collect()
        if os.path.exists(self.temp_db_path):
            try:
                os.remove(self.temp_db_path)
            except Exception:
                pass

    def login(self, username, password):
        return self.client.post(
            "/api/login",
            data=json.dumps({"username": username, "password": password}),
            content_type="application/json"
        )

    def test_unauthenticated_patient_redirected_to_login(self):
        resp = self.client.get("/patient")
        self.assertEqual(resp.status_code, 302)
        self.assertIn("/login", resp.headers["Location"])

    def test_clinician_cannot_access_patient_dashboard(self):
        self.login("dr_sarah", "physio123")
        resp = self.client.get("/patient")
        self.assertEqual(resp.status_code, 403)

    def test_patient_dashboard_renders_therapy_and_svg_diagram(self):
        self.login("john_doe", "patient123")
        resp = self.client.get("/patient")
        self.assertEqual(resp.status_code, 200)

        html = resp.get_data(as_text=True)
        # Verify title and therapy
        self.assertIn("Today's Physical Therapy", html)
        self.assertIn("Fist Open / Close", html)
        self.assertIn("Approved by Clinician", html)
        # Verify SVG diagram element
        self.assertIn("<svg", html)
        self.assertIn("anatomySvg", html)
        # Verify Mandatory Disclaimer
        self.assertIn("Camera-based estimate, not a clinical measurement", html)

    def test_patient_workout_room_renders_hud_and_video_feed(self):
        self.login("john_doe", "patient123")
        resp = self.client.get("/patient/workout/1")
        self.assertEqual(resp.status_code, 200)

        html = resp.get_data(as_text=True)
        self.assertIn("Live Therapy Session", html)
        self.assertIn("/api/video_feed/1", html)
        self.assertIn("hudRepsDisplay", html)
        self.assertIn("Finish & Save Session", html)
        self.assertIn("Mandatory Clinical Notice", html)

    def test_patient_accessing_invalid_prescription_returns_404(self):
        self.login("john_doe", "patient123")
        resp = self.client.get("/patient/workout/999")
        self.assertEqual(resp.status_code, 404)

    def test_live_state_endpoint(self):
        self.login("john_doe", "patient123")
        resp = self.client.get("/api/live_state/1")
        self.assertEqual(resp.status_code, 200)
        data = resp.get_json()
        self.assertIn("rep_count", data)
        self.assertIn("active", data)


if __name__ == "__main__":
    unittest.main()
