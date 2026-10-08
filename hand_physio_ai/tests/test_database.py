"""
Unit and Integration Tests for Database Schema, Helpers, and Seed Data.
Verifies relational constraints, password hashing, and privacy compliance.
"""

import sys
import os
import unittest
import tempfile
import sqlite3
import gc

# Ensure project root in sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from database.db import (
    init_db, db_context,
    create_user, verify_user_credentials,
    create_clinician_profile, create_patient_profile,
    create_prescription, record_session, record_rep_measurement,
    get_patient_prescriptions, get_session_details_with_reps
)
from database.seed import seed_database


class TestDatabaseOperations(unittest.TestCase):
    """Test SQLite operations using an isolated temporary database."""

    def setUp(self):
        self.temp_fd, self.temp_db_path = tempfile.mkstemp(suffix=".db")
        os.close(self.temp_fd)  # Close OS descriptor immediately
        init_db(self.temp_db_path)

    def tearDown(self):
        gc.collect()
        if os.path.exists(self.temp_db_path):
            try:
                os.remove(self.temp_db_path)
            except Exception:
                pass

    def test_user_creation_and_password_hashing(self):
        user_id = create_user("test_user", "secure_pass_123", "patient", "Test User", db_path=self.temp_db_path)
        self.assertIsInstance(user_id, int)

        # Successful authentication
        auth_success = verify_user_credentials("test_user", "secure_pass_123", db_path=self.temp_db_path)
        self.assertIsNotNone(auth_success)
        self.assertEqual(auth_success["username"], "test_user")
        self.assertNotEqual(auth_success["password_hash"], "secure_pass_123")  # Hashed!

        # Failed authentication
        auth_fail = verify_user_credentials("test_user", "wrong_pass", db_path=self.temp_db_path)
        self.assertIsNone(auth_fail)

    def test_invalid_role_raises_value_error(self):
        with self.assertRaises(ValueError):
            create_user("hacker", "pass", "admin_super", "Bad User", db_path=self.temp_db_path)

    def test_foreign_key_constraint_enforcement(self):
        # Attempt to insert a prescription with non-existent foreign keys should fail
        with self.assertRaises(sqlite3.IntegrityError):
            create_prescription(
                clinician_id=999,
                patient_id=999,
                exercise_id=999,
                target_sets=3,
                target_reps=10,
                target_rom=80.0,
                instructions="Test",
                precautions="None",
                hand="left",
                db_path=self.temp_db_path
            )

    def test_seed_database_execution_and_retrieval(self):
        # Run full seeder
        seed_database(self.temp_db_path)

        # Verify clinician login
        clin_auth = verify_user_credentials("dr_sarah", "physio123", db_path=self.temp_db_path)
        self.assertIsNotNone(clin_auth)
        self.assertEqual(clin_auth["role"], "clinician")

        # Verify patient login and prescriptions
        pat_auth = verify_user_credentials("john_doe", "patient123", db_path=self.temp_db_path)
        self.assertIsNotNone(pat_auth)
        self.assertEqual(pat_auth["role"], "patient")

        # Patient prescription check
        prescriptions = get_patient_prescriptions(patient_id=1, db_path=self.temp_db_path)
        self.assertEqual(len(prescriptions), 1)
        self.assertEqual(prescriptions[0]["exercise_code"], "fist_flexion")
        self.assertEqual(prescriptions[0]["target_reps"], 10)

        # Session and measurement details check
        session_details = get_session_details_with_reps(session_id=1, db_path=self.temp_db_path)
        self.assertIsNotNone(session_details)
        self.assertEqual(session_details["reps_completed"], 3)
        self.assertEqual(len(session_details["measurements"]), 3)
        self.assertAlmostEqual(session_details["measurements"][0]["rom"], 86.3, places=1)

    def test_privacy_rule_no_raw_video_or_image_columns(self):
        """Hard Rule #6: Verify schema NEVER defines image or video storage columns."""
        with db_context(self.temp_db_path) as conn:
            tables = conn.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()
            for t in tables:
                table_name = t["name"]
                columns = conn.execute(f"PRAGMA table_info({table_name})").fetchall()
                col_names = [c["name"].lower() for c in columns]
                for forbidden in ["image", "video", "frame", "photo", "raw_media", "recording"]:
                    for col in col_names:
                        self.assertNotIn(forbidden, col, f"Forbidden media column '{col}' found in table '{table_name}'")


if __name__ == "__main__":
    unittest.main()
