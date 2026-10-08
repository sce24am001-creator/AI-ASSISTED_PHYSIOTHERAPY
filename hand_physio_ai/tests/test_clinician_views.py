"""
Unit and Integration Tests for Clinician Web Views and Management Portal.
Tests clinician dashboard rendering, patient directory, Chart.js canvas elements,
prescription creation, and role protection.
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


class TestClinicianViews(unittest.TestCase):
    """Test Clinician dashboard and clinical management portal."""

    def setUp(self):
        self.temp_fd, self.temp_db_path = tempfile.mkstemp(suffix=".db")
        os.close(self.temp_fd)
        seed_database(self.temp_db_path)

        self.app = create_app(
            db_path=self.temp_db_path,
            test_config={"TESTING": True, "SECRET_KEY": "test-clinician-secret"}
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

    def test_unauthenticated_clinician_redirected_to_login(self):
        resp = self.client.get("/clinician")
        self.assertEqual(resp.status_code, 302)
        self.assertIn("/login", resp.headers["Location"])

    def test_patient_cannot_access_clinician_portal(self):
        self.login("john_doe", "patient123")
        resp = self.client.get("/clinician")
        self.assertEqual(resp.status_code, 403)

    def test_clinician_dashboard_renders_directory_and_charts(self):
        self.login("dr_sarah", "physio123")
        resp = self.client.get("/clinician")
        self.assertEqual(resp.status_code, 200)

        html = resp.get_data(as_text=True)
        # Verify title & patient directory
        self.assertIn("Physiotherapy Clinical Management", html)
        self.assertIn("John Doe", html)
        self.assertIn("Patient Directory", html)
        # Verify Prescription form & charts
        self.assertIn("Assign New Prescription", html)
        self.assertIn("romChart", html)
        self.assertIn("adherenceChart", html)
        # Verify Anatomical editor
        self.assertIn("Edit Patient Anatomical Guidance", html)
        # Verify Mandatory Disclaimer
        self.assertIn("The AI platform does not diagnose, prescribe", html)

    def test_clinician_creates_new_patient_and_appears_in_list(self):
        self.login("dr_sarah", "physio123")
        create_resp = self.client.post(
            "/api/patients",
            data=json.dumps({
                "full_name": "Alice Cooper",
                "username": "alice_c",
                "password": "alicepass123",
                "date_of_birth": "1992-08-15",
                "notes": "Carpal tunnel release therapy."
            }),
            content_type="application/json"
        )
        self.assertEqual(create_resp.status_code, 201)

        # Check list
        list_resp = self.client.get("/api/patients")
        self.assertEqual(list_resp.status_code, 200)
        p_names = [p["full_name"] for p in list_resp.get_json()["patients"]]
        self.assertIn("Alice Cooper", p_names)

    def test_clinician_patient_trend_chart_data(self):
        self.login("dr_sarah", "physio123")
        resp = self.client.get("/api/patients/1/trends")
        self.assertEqual(resp.status_code, 200)
        data = resp.get_json()
        self.assertIn("rom_trend", data)
        self.assertIn("reps_trend", data)
        self.assertGreaterEqual(data["total_sessions"], 1)


if __name__ == "__main__":
    unittest.main()
