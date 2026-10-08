"""
Database Seeding Script.

Initializes database and populates with realistic, clinically structured seed data:
- Demo Clinician: Dr. Sarah Jenkins (dr_sarah / physio123)
- Demo Patient: John Doe (john_doe / patient123)
- 3 Exercises with clinician-approved anatomical targets & guidance
- Active prescription for John Doe
- Past completed session with per-rep measurements for charting
"""

import os
import sys
from typing import Optional

# Ensure project root in path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from database.db import (
    init_db, get_db_connection,
    create_user, create_clinician_profile, create_patient_profile,
    update_exercise_target, create_prescription,
    record_session, record_rep_measurement
)


def seed_database(db_path: Optional[str] = None) -> None:
    """Populate database with demo accounts, exercise catalog, targets, and initial session."""
    init_db(db_path)

    with get_db_connection(db_path) as conn:
        # Check if already seeded
        existing_users = conn.execute("SELECT COUNT(*) as count FROM users").fetchone()["count"]
        if existing_users > 0:
            print("[INFO] Database already contains data. Skipping re-seed.")
            return

        print("[1/5] Creating user accounts...")
        # 1. Clinician User
        clin_user_id = create_user(
            username="dr_sarah",
            password="physio123",
            role="clinician",
            full_name="Dr. Sarah Jenkins, PT",
            db_path=db_path
        )
        clin_id = create_clinician_profile(
            user_id=clin_user_id,
            license_number="PT-98214",
            clinic_name="Metropolitan Hand Clinic",
            db_path=db_path
        )

        # 2. Patient User
        pat_user_id = create_user(
            username="john_doe",
            password="patient123",
            role="patient",
            full_name="John Doe",
            db_path=db_path
        )
        pat_id = create_patient_profile(
            user_id=pat_user_id,
            date_of_birth="1985-04-12",
            notes="Right wrist distal fracture status post-cast removal. Exhibiting finger stiffness.",
            db_path=db_path
        )

        print("[2/5] Inserting exercise catalog...")
        cursor = conn.cursor()
        cursor.execute(
            """
            INSERT INTO exercises (code, name, description, default_hand)
            VALUES
            ('fist_flexion', 'Fist Open / Close', 'Finger flexion and extension across PIP joints.', 'either'),
            ('thumb_opposition', 'Thumb-to-Fingertip Touch', 'Opposition of thumb tip to index fingertip, normalized by hand size.', 'either'),
            ('wrist_tilt', 'Wrist Flexion / Extension (Approx)', 'Approximate hand tilt angle from wrist to middle knuckle from a side view.', 'either')
            """
        )
        conn.commit()

        # Retrieve exercise IDs
        ex_fist_id = conn.execute("SELECT id FROM exercises WHERE code = 'fist_flexion'").fetchone()["id"]
        ex_thumb_id = conn.execute("SELECT id FROM exercises WHERE code = 'thumb_opposition'").fetchone()["id"]
        ex_wrist_id = conn.execute("SELECT id FROM exercises WHERE code = 'wrist_tilt'").fetchone()["id"]

        print("[3/5] Populating clinician-approved anatomical targets...")
        update_exercise_target(
            exercise_id=ex_fist_id,
            target_region="Fingers & Palm",
            target_joints="Metacarpophalangeal (MCP) and Proximal Interphalangeal (PIP) joints",
            target_muscles="Flexor digitorum profundus, Flexor digitorum superficialis, Lumbricals",
            clinical_purpose="Restore active finger flexion range of motion, reduce tendon adhesion, and rebuild grip strength following immobilization.",
            edited_by_clinician_id=clin_id,
            db_path=db_path
        )

        update_exercise_target(
            exercise_id=ex_thumb_id,
            target_region="Thenar Eminence & Thumb Column",
            target_joints="Carpometacarpal (CMC) and Interphalangeal (IP) joints",
            target_muscles="Opponens pollicis, Abductor pollicis brevis, Flexor pollicis brevis",
            clinical_purpose="Improve fine motor coordination, functional pinch grip, and thumb circumduction.",
            edited_by_clinician_id=clin_id,
            db_path=db_path
        )

        update_exercise_target(
            exercise_id=ex_wrist_id,
            target_region="Wrist Complex (Radio-carpal)",
            target_joints="Radiocarpal and midcarpal joint axes (Approximated)",
            target_muscles="Flexor carpi radialis, Extensor carpi radialis longus/brevis",
            clinical_purpose="Recondition sagittal wrist flexion/extension mobility following wrist sprain or distal radius recovery.",
            edited_by_clinician_id=clin_id,
            db_path=db_path
        )

        print("[4/5] Creating active prescription for John Doe...")
        presc_id = create_prescription(
            clinician_id=clin_id,
            patient_id=pat_id,
            exercise_id=ex_fist_id,
            target_sets=3,
            target_reps=10,
            target_rom=90.0,
            instructions="Keep elbow supported on the table. Slowly close hand into a firm fist, hold for 1 second, then stretch fingers fully open.",
            precautions="Do not force past sharp pain. If swelling or numbness occurs, discontinue and contact the clinic immediately.",
            hand="right",
            db_path=db_path
        )

        print("[5/5] Recording sample historical session & rep measurements...")
        session_id = record_session(
            prescription_id=presc_id,
            patient_id=pat_id,
            start_time="2026-10-06 14:00:00",
            end_time="2026-10-06 14:03:30",
            reps_completed=3,
            session_rom=88.5,
            reliability_status="reliable",
            db_path=db_path
        )

        # 3 sample rep measurements
        record_rep_measurement(session_id, 1, min_angle=58.2, max_angle=144.5, rom=86.3, duration_seconds=1.2, db_path=db_path)
        record_rep_measurement(session_id, 2, min_angle=55.0, max_angle=145.0, rom=90.0, duration_seconds=1.3, db_path=db_path)
        record_rep_measurement(session_id, 3, min_angle=56.1, max_angle=145.3, rom=89.2, duration_seconds=1.1, db_path=db_path)

        print("[SUCCESS] Database initialized and seeded successfully!")


if __name__ == "__main__":
    seed_database()
