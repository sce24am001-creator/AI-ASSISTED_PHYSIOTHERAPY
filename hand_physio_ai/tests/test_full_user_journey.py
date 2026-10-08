"""
End-to-End User Journey & Comprehensive Clinical Workflow Test.

Simulates the complete clinical lifecycle:
1. Clinician logs in.
2. Clinician creates a new patient account.
3. Clinician issues an exercise prescription with target ROM & sets/reps.
4. Clinician logs out.
5. Patient logs in and views their assigned prescription.
6. Patient loads the workout room.
7. Patient completes synthetic exercise reps (simulated MediaPipe 3D joint movements).
8. Patient posts completed session & per-rep telemetry.
9. Clinician logs back in and inspects the patient's session history & ROM trend curves.
10. Multi-tenant isolation & IDOR prevention verified (patient cannot access other patient data).
11. Privilege escalation prevention verified (patient cannot create prescriptions).
12. Safety & compliance rules verified (no raw video stored, disclaimer present, range bounds checked).
"""

import os
import json
import tempfile
import unittest
import numpy as np

from database.db import init_db, get_db_connection
from database.seed import seed_database
from backend.app import create_app
from src.analysis.exercises import ExerciseTracker


class TestFullUserJourney(unittest.TestCase):
    def setUp(self):
        self.db_fd, self.db_path = tempfile.mkstemp(suffix=".db")
        init_db(self.db_path)
        seed_database(self.db_path)
        self.app = create_app(db_path=self.db_path, test_config={"TESTING": True})
        self.client = self.app.test_client()

    def tearDown(self):
        try:
            os.close(self.db_fd)
        except OSError:
            pass
        try:
            if os.path.exists(self.db_path):
                os.remove(self.db_path)
        except (PermissionError, OSError):
            pass

    def login(self, username, password):
        return self.client.post(
            "/api/login",
            data=json.dumps({"username": username, "password": password}),
            content_type="application/json"
        )

    def logout(self):
        return self.client.post("/api/logout")

    def _generate_synthetic_fist_landmarks(self, is_closed: bool = False) -> np.ndarray:
        """Helper generating 21 synthetic 3D landmarks for fist flexion testing across all 4 fingers."""
        landmarks = np.zeros((21, 3), dtype=np.float64)
        landmarks[0] = [0.5, 0.8, 0.0]  # Wrist
        # MCP knuckles
        for mcp in [5, 9, 13, 17]:
            landmarks[mcp] = [0.5, 0.6, 0.0]
        # PIP joints
        for pip in [6, 10, 14, 18]:
            landmarks[pip] = [0.5, 0.4, 0.0]
        # DIP joints: open (~180 deg) or clenched (~90 deg)
        for dip in [7, 11, 15, 19]:
            if is_closed:
                landmarks[dip] = [0.7, 0.4, 0.0]  # Clenched
            else:
                landmarks[dip] = [0.5, 0.2, 0.0]  # Open
        return landmarks

    def test_complete_clinical_and_patient_lifecycle(self):
        # -------------------------------------------------------------
        # STEP 1: Clinician Login
        # -------------------------------------------------------------
        resp = self.login("dr_sarah", "physio123")
        self.assertEqual(resp.status_code, 200)
        data = resp.get_json()
        self.assertEqual(data["user"]["role"], "clinician")
        clinician_id = data["user"]["profile_id"]

        # -------------------------------------------------------------
        # STEP 2: Clinician Registers New Patient
        # -------------------------------------------------------------
        create_pat_resp = self.client.post(
            "/api/patients",
            data=json.dumps({
                "username": "alice_w",
                "password": "alicepassword123",
                "full_name": "Alice Wonder",
                "date_of_birth": "1988-04-12",
                "notes": "Post-carpal tunnel release surgery recovery."
            }),
            content_type="application/json"
        )
        self.assertEqual(create_pat_resp.status_code, 201)
        new_patient_id = create_pat_resp.get_json()["patient_id"]
        self.assertIsNotNone(new_patient_id)

        # -------------------------------------------------------------
        # STEP 3: Clinician Prescribes Exercise
        # -------------------------------------------------------------
        presc_resp = self.client.post(
            "/api/prescriptions",
            data=json.dumps({
                "patient_id": new_patient_id,
                "exercise_id": 1,  # Fist Flexion
                "target_sets": 2,
                "target_reps": 3,
                "target_rom": 85.0,
                "instructions": "Form a comfortable fist, hold for 1 second, then release fully.",
                "precautions": "Cease movement if sharp pain occurs.",
                "hand": "right"
            }),
            content_type="application/json"
        )
        self.assertEqual(presc_resp.status_code, 201)
        presc_id = presc_resp.get_json()["prescription_id"]

        # Test validation: Clinician cannot prescribe out-of-range parameters
        bad_presc_resp = self.client.post(
            "/api/prescriptions",
            data=json.dumps({
                "patient_id": new_patient_id,
                "exercise_id": 1,
                "target_sets": 50,  # Max allowed is 10
                "target_reps": 100,  # Max allowed is 50
                "target_rom": 300.0,  # Max allowed is 180.0
                "instructions": "Bad range test",
                "hand": "right"
            }),
            content_type="application/json"
        )
        self.assertEqual(bad_presc_resp.status_code, 400)

        # -------------------------------------------------------------
        # STEP 4: Clinician Logs Out
        # -------------------------------------------------------------
        self.logout()

        # -------------------------------------------------------------
        # STEP 5: Patient Alice Logs In
        # -------------------------------------------------------------
        resp = self.login("alice_w", "alicepassword123")
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.get_json()["user"]["role"], "patient")

        # -------------------------------------------------------------
        # STEP 6: Patient Retrieves Her Prescriptions
        # -------------------------------------------------------------
        prescs_resp = self.client.get("/api/prescriptions")
        self.assertEqual(prescs_resp.status_code, 200)
        prescs = prescs_resp.get_json()["prescriptions"]
        self.assertEqual(len(prescs), 1)
        self.assertEqual(prescs[0]["id"], presc_id)
        self.assertEqual(prescs[0]["exercise_code"], "fist_flexion")

        # -------------------------------------------------------------
        # STEP 7: Patient Accesses Workout UI
        # -------------------------------------------------------------
        workout_page_resp = self.client.get(f"/patient/workout/{presc_id}")
        self.assertEqual(workout_page_resp.status_code, 200)
        page_html = workout_page_resp.get_data(as_text=True)
        self.assertIn("Camera-based estimate, not a clinical measurement", page_html)
        self.assertIn("Fist Open / Close", page_html)

        # -------------------------------------------------------------
        # STEP 8: Simulate 3 Clean Reps using ExerciseTracker
        # -------------------------------------------------------------
        tracker = ExerciseTracker("fist_flexion")
        t = 0.0
        dt = 0.05
        open_lm = self._generate_synthetic_fist_landmarks(is_closed=False)
        closed_lm = self._generate_synthetic_fist_landmarks(is_closed=True)
        # Initial stabilization at rest
        for _ in range(8):
            t += dt
            tracker.update(open_lm, is_reliable=True, timestamp=t)

        # 3 cycles: Closed (~90 deg) -> Open (~180 deg)
        for _ in range(3):
            # Phase 1: Closed fist
            for _ in range(12):
                t += dt
                tracker.update(closed_lm, is_reliable=True, timestamp=t)
            # Phase 2: Open hand again to complete rep
            for _ in range(12):
                t += dt
                tracker.update(open_lm, is_reliable=True, timestamp=t)

        summary = tracker.get_session_summary()
        self.assertEqual(summary["reps_completed"], 3)
        self.assertGreater(summary["mean_rom"], 0.0)

        # -------------------------------------------------------------
        # STEP 9: Patient Records Session Telemetry via API
        # -------------------------------------------------------------
        session_telemetry = {
            "prescription_id": presc_id,
            "start_time": "2026-10-08 10:00:00",
            "end_time": "2026-10-08 10:02:15",
            "reps_completed": summary["reps_completed"],
            "session_rom": summary["mean_rom"],
            "reliability_status": "reliable",
            "measurements": [
                {
                    "rep_number": m["rep_number"],
                    "min_value": m["min_value"],
                    "max_value": m["max_value"],
                    "rom": m["rom"],
                    "duration_seconds": m["duration_seconds"]
                }
                for m in summary["completed_reps"]
            ]
        }
        record_resp = self.client.post(
            "/api/sessions",
            data=json.dumps(session_telemetry),
            content_type="application/json"
        )
        self.assertEqual(record_resp.status_code, 201)
        recorded_session_id = record_resp.get_json()["session_id"]
        self.assertIsNotNone(recorded_session_id)

        # -------------------------------------------------------------
        # STEP 10: Multi-Tenant Isolation & IDOR Check
        # Patient Alice CANNOT access Patient 1's (John Doe) sessions
        # -------------------------------------------------------------
        idor_resp = self.client.get("/api/patients/1/sessions")
        self.assertEqual(idor_resp.status_code, 403)

        # Patient Alice CANNOT create prescriptions
        priv_resp = self.client.post(
            "/api/prescriptions",
            data=json.dumps({
                "patient_id": new_patient_id,
                "exercise_id": 1,
                "target_sets": 1,
                "target_reps": 5,
                "target_rom": 50.0,
                "instructions": "Unauthorized prescription attempt",
                "hand": "right"
            }),
            content_type="application/json"
        )
        self.assertEqual(priv_resp.status_code, 403)

        # Patient Alice CANNOT create patients
        create_pat_unauth = self.client.post(
            "/api/patients",
            data=json.dumps({
                "username": "hacker_pat",
                "password": "pwd",
                "full_name": "Hacker"
            }),
            content_type="application/json"
        )
        self.assertEqual(create_pat_unauth.status_code, 403)

        # Patient logs out
        self.logout()

        # -------------------------------------------------------------
        # STEP 11: Clinician Logs Back In & Inspects Alice's Telemetry
        # -------------------------------------------------------------
        self.login("dr_sarah", "physio123")

        # Clinician gets Alice's trend data
        trends_resp = self.client.get(f"/api/patients/{new_patient_id}/trends")
        self.assertEqual(trends_resp.status_code, 200)
        trend_data = trends_resp.get_json()
        self.assertEqual(trend_data["total_sessions"], 1)
        self.assertEqual(trend_data["reps_trend"][0], 3)
        self.assertAlmostEqual(trend_data["rom_trend"][0], summary["mean_rom"], places=1)

        # Clinician inspects detailed rep breakdown
        details_resp = self.client.get(f"/api/sessions/{recorded_session_id}")
        self.assertEqual(details_resp.status_code, 200)
        session_details = details_resp.get_json()["session"]
        self.assertEqual(len(session_details["measurements"]), 3)

        # -------------------------------------------------------------
        # STEP 12: Verify Privacy Rule 6: Zero Raw Images/Videos in DB
        # -------------------------------------------------------------
        with get_db_connection(self.db_path) as conn:
            columns = [c[1].lower() for c in conn.execute("PRAGMA table_info(sessions)").fetchall()]
            for forbidden in ("video", "image", "raw_frame", "photo", "recording"):
                self.assertNotIn(forbidden, columns)

            rep_columns = [c[1].lower() for c in conn.execute("PRAGMA table_info(session_measurements)").fetchall()]
            for forbidden in ("video", "image", "raw_frame", "photo", "recording"):
                self.assertNotIn(forbidden, rep_columns)


if __name__ == "__main__":
    unittest.main()
