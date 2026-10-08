"""
Integration and API Unit Tests for Flask Backend.
Tests authentication, role-based access control (RBAC), patient data isolation,
prescriptions management, and session telemetry recording.
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


class TestFlaskBackend(unittest.TestCase):
    """Test Flask backend REST endpoints using an isolated temporary seeded database."""

    def setUp(self):
        self.temp_fd, self.temp_db_path = tempfile.mkstemp(suffix=".db")
        os.close(self.temp_fd)
        seed_database(self.temp_db_path)

        self.app = create_app(
            db_path=self.temp_db_path,
            test_config={"TESTING": True, "SECRET_KEY": "test-secret-rehab"}
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

    # --- Auth Tests ---

    def test_invalid_login_returns_401(self):
        resp = self.login("dr_sarah", "wrong_password")
        self.assertEqual(resp.status_code, 401)

    def test_clinician_login_and_me_endpoint(self):
        resp = self.login("dr_sarah", "physio123")
        self.assertEqual(resp.status_code, 200)
        data = resp.get_json()
        self.assertEqual(data["user"]["role"], "clinician")
        self.assertEqual(data["user"]["username"], "dr_sarah")

        # Test /api/me
        me_resp = self.client.get("/api/me")
        self.assertEqual(me_resp.status_code, 200)
        self.assertTrue(me_resp.get_json()["authenticated"])

    def test_patient_login(self):
        resp = self.login("john_doe", "patient123")
        self.assertEqual(resp.status_code, 200)
        data = resp.get_json()
        self.assertEqual(data["user"]["role"], "patient")
        self.assertEqual(data["user"]["username"], "john_doe")

    # --- Role-Based Access Control (RBAC) ---

    def test_unauthenticated_access_blocked(self):
        resp = self.client.get("/api/patients")
        self.assertEqual(resp.status_code, 401)

    def test_patient_cannot_view_all_patients_returns_403(self):
        self.login("john_doe", "patient123")
        resp = self.client.get("/api/patients")
        self.assertEqual(resp.status_code, 403)

    def test_patient_cannot_create_prescription_returns_403(self):
        self.login("john_doe", "patient123")
        resp = self.client.post(
            "/api/prescriptions",
            data=json.dumps({
                "patient_id": 1,
                "exercise_id": 1,
                "target_sets": 3,
                "target_reps": 10,
                "target_rom": 90.0,
                "instructions": "Test",
                "precautions": "None",
                "hand": "right"
            }),
            content_type="application/json"
        )
        self.assertEqual(resp.status_code, 403)

    # --- Clinician Capabilities ---

    def test_clinician_can_list_patients_and_create_prescriptions(self):
        self.login("dr_sarah", "physio123")

        # 1. List patients
        p_resp = self.client.get("/api/patients")
        self.assertEqual(p_resp.status_code, 200)
        patients = p_resp.get_json()["patients"]
        self.assertGreaterEqual(len(patients), 1)

        # 2. Update exercise target text
        t_resp = self.client.put(
            "/api/exercises/1/targets",
            data=json.dumps({
                "target_region": "Palmar aspect",
                "target_joints": "MCP & PIP",
                "target_muscles": "Flexor digitorum",
                "clinical_purpose": "Updated purpose text for rehabilitation."
            }),
            content_type="application/json"
        )
        self.assertEqual(t_resp.status_code, 200)

        # 3. Create a new prescription
        new_presc_resp = self.client.post(
            "/api/prescriptions",
            data=json.dumps({
                "patient_id": 1,
                "exercise_id": 2,
                "target_sets": 2,
                "target_reps": 8,
                "target_rom": 0.3,
                "instructions": "Touch thumb to index gently.",
                "precautions": "Avoid strain.",
                "hand": "left"
            }),
            content_type="application/json"
        )
        self.assertEqual(new_presc_resp.status_code, 201)
        self.assertIn("prescription_id", new_presc_resp.get_json())

    # --- Patient Data Isolation & Telemetry ---

    def test_patient_sees_only_own_prescriptions(self):
        self.login("john_doe", "patient123")
        resp = self.client.get("/api/prescriptions")
        self.assertEqual(resp.status_code, 200)
        prescriptions = resp.get_json()["prescriptions"]
        for p in prescriptions:
            self.assertEqual(p["patient_id"], 1)

    def test_patient_records_completed_session(self):
        self.login("john_doe", "patient123")

        session_payload = {
            "prescription_id": 1,
            "start_time": "2026-10-07 10:00:00",
            "end_time": "2026-10-07 10:02:15",
            "reps_completed": 2,
            "session_rom": 92.4,
            "reliability_status": "reliable",
            "measurements": [
                {"rep_number": 1, "min_value": 55.0, "max_value": 145.0, "rom": 90.0, "duration_seconds": 1.1},
                {"rep_number": 2, "min_value": 53.2, "max_value": 148.0, "rom": 94.8, "duration_seconds": 1.2}
            ]
        }

        resp = self.client.post(
            "/api/sessions",
            data=json.dumps(session_payload),
            content_type="application/json"
        )
        self.assertEqual(resp.status_code, 201)
        session_id = resp.get_json()["session_id"]

        # Retrieve session details
        details_resp = self.client.get(f"/api/sessions/{session_id}")
        self.assertEqual(details_resp.status_code, 200)
        s_data = details_resp.get_json()["session"]
        self.assertEqual(s_data["reps_completed"], 2)
        self.assertEqual(len(s_data["measurements"]), 2)

        # Retrieve trends for charts
        trends_resp = self.client.get("/api/patients/1/trends")
        self.assertEqual(trends_resp.status_code, 200)
        t_data = trends_resp.get_json()
        self.assertIn("rom_trend", t_data)
        self.assertIn("reps_trend", t_data)


if __name__ == "__main__":
    unittest.main()
