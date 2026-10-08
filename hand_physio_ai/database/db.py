"""
Database Operations and Helper Functions.

Standard library sqlite3 with foreign keys enabled, parameterized queries,
proper connection lifecycle management for Windows file locks,
and Werkzeug secure password hashing.
"""

import os
import sqlite3
from contextlib import contextmanager
from typing import Optional, List, Dict, Any, Tuple
from werkzeug.security import generate_password_hash, check_password_hash


DEFAULT_DB_PATH = os.path.join(os.path.dirname(__file__), "hand_physio.db")
SCHEMA_PATH = os.path.join(os.path.dirname(__file__), "schema.sql")


def get_db_connection(db_path: Optional[str] = None) -> sqlite3.Connection:
    """
    Establish SQLite connection with foreign keys enabled and row dictionary access.
    """
    path = db_path or DEFAULT_DB_PATH
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON;")
    return conn


@contextmanager
def db_context(db_path: Optional[str] = None):
    """Context manager that guarantees connection is closed on exit."""
    conn = get_db_connection(db_path)
    try:
        yield conn
    finally:
        conn.close()


def init_db(db_path: Optional[str] = None) -> None:
    """Initialize database tables using schema.sql."""
    with open(SCHEMA_PATH, "r", encoding="utf-8") as f:
        schema_sql = f.read()

    with db_context(db_path) as conn:
        conn.executescript(schema_sql)
        conn.commit()


# --- User & Auth Operations ---

def create_user(
    username: str,
    password: str,
    role: str,
    full_name: str,
    db_path: Optional[str] = None
) -> int:
    """Create a user with a securely hashed password."""
    if role not in ("clinician", "patient"):
        raise ValueError("Role must be 'clinician' or 'patient'")

    pw_hash = generate_password_hash(password)
    with db_context(db_path) as conn:
        cursor = conn.cursor()
        cursor.execute(
            "INSERT INTO users (username, password_hash, role, full_name) VALUES (?, ?, ?, ?)",
            (username.strip(), pw_hash, role, full_name.strip())
        )
        conn.commit()
        return cursor.lastrowid


def verify_user_credentials(
    username: str,
    password: str,
    db_path: Optional[str] = None
) -> Optional[Dict[str, Any]]:
    """Authenticate user credentials and return user dict if valid."""
    with db_context(db_path) as conn:
        row = conn.execute(
            "SELECT * FROM users WHERE username = ?",
            (username.strip(),)
        ).fetchone()

        if row and check_password_hash(row["password_hash"], password):
            return dict(row)
    return None


def get_user_by_id(user_id: int, db_path: Optional[str] = None) -> Optional[Dict[str, Any]]:
    with db_context(db_path) as conn:
        row = conn.execute("SELECT * FROM users WHERE id = ?", (user_id,)).fetchone()
        return dict(row) if row else None


# --- Clinician & Patient Profiles ---

def create_clinician_profile(
    user_id: int,
    license_number: str,
    clinic_name: str,
    db_path: Optional[str] = None
) -> int:
    with db_context(db_path) as conn:
        cursor = conn.cursor()
        cursor.execute(
            "INSERT INTO clinicians (user_id, license_number, clinic_name) VALUES (?, ?, ?)",
            (user_id, license_number, clinic_name)
        )
        conn.commit()
        return cursor.lastrowid


def create_patient_profile(
    user_id: int,
    date_of_birth: str,
    notes: str,
    db_path: Optional[str] = None
) -> int:
    with db_context(db_path) as conn:
        cursor = conn.cursor()
        cursor.execute(
            "INSERT INTO patients (user_id, date_of_birth, notes) VALUES (?, ?, ?)",
            (user_id, date_of_birth, notes)
        )
        conn.commit()
        return cursor.lastrowid


def get_patient_by_user_id(user_id: int, db_path: Optional[str] = None) -> Optional[Dict[str, Any]]:
    with db_context(db_path) as conn:
        row = conn.execute(
            """
            SELECT p.*, u.full_name, u.username
            FROM patients p
            JOIN users u ON p.user_id = u.id
            WHERE p.user_id = ?
            """,
            (user_id,)
        ).fetchone()
        return dict(row) if row else None


def get_clinician_by_user_id(user_id: int, db_path: Optional[str] = None) -> Optional[Dict[str, Any]]:
    with db_context(db_path) as conn:
        row = conn.execute(
            """
            SELECT c.*, u.full_name, u.username
            FROM clinicians c
            JOIN users u ON c.user_id = u.id
            WHERE c.user_id = ?
            """,
            (user_id,)
        ).fetchone()
        return dict(row) if row else None


def get_all_patients(db_path: Optional[str] = None) -> List[Dict[str, Any]]:
    with db_context(db_path) as conn:
        rows = conn.execute(
            """
            SELECT p.id as patient_id, p.date_of_birth, p.notes, u.id as user_id, u.full_name, u.username, u.created_at
            FROM patients p
            JOIN users u ON p.user_id = u.id
            ORDER BY u.full_name ASC
            """
        ).fetchall()
        return [dict(r) for r in rows]


# --- Exercises & Targets ---

def get_all_exercises(db_path: Optional[str] = None) -> List[Dict[str, Any]]:
    with db_context(db_path) as conn:
        rows = conn.execute(
            """
            SELECT e.*, t.target_region, t.target_joints, t.target_muscles, t.clinical_purpose
            FROM exercises e
            LEFT JOIN exercise_targets t ON e.id = t.exercise_id
            ORDER BY e.id ASC
            """
        ).fetchall()
        return [dict(r) for r in rows]


def get_exercise_by_id(exercise_id: int, db_path: Optional[str] = None) -> Optional[Dict[str, Any]]:
    with db_context(db_path) as conn:
        row = conn.execute(
            """
            SELECT e.*, t.target_region, t.target_joints, t.target_muscles, t.clinical_purpose, t.updated_at as target_updated_at
            FROM exercises e
            LEFT JOIN exercise_targets t ON e.id = t.exercise_id
            WHERE e.id = ?
            """,
            (exercise_id,)
        ).fetchone()
        return dict(row) if row else None


def update_exercise_target(
    exercise_id: int,
    target_region: str,
    target_joints: str,
    target_muscles: str,
    clinical_purpose: str,
    edited_by_clinician_id: Optional[int] = None,
    db_path: Optional[str] = None
) -> None:
    """Clinician edits patient-facing anatomical and purpose text."""
    with db_context(db_path) as conn:
        conn.execute(
            """
            INSERT INTO exercise_targets (exercise_id, target_region, target_joints, target_muscles, clinical_purpose, edited_by_clinician_id, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
            ON CONFLICT(exercise_id) DO UPDATE SET
                target_region = excluded.target_region,
                target_joints = excluded.target_joints,
                target_muscles = excluded.target_muscles,
                clinical_purpose = excluded.clinical_purpose,
                edited_by_clinician_id = excluded.edited_by_clinician_id,
                updated_at = CURRENT_TIMESTAMP
            """,
            (exercise_id, target_region, target_joints, target_muscles, clinical_purpose, edited_by_clinician_id)
        )
        conn.commit()


# --- Prescriptions ---

def create_prescription(
    clinician_id: int,
    patient_id: int,
    exercise_id: int,
    target_sets: int,
    target_reps: int,
    target_rom: float,
    instructions: str,
    precautions: str,
    hand: str,
    db_path: Optional[str] = None
) -> int:
    with db_context(db_path) as conn:
        cursor = conn.cursor()
        cursor.execute(
            """
            INSERT INTO prescriptions (
                clinician_id, patient_id, exercise_id, target_sets, target_reps, target_rom,
                instructions, precautions, hand, status
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 'active')
            """,
            (clinician_id, patient_id, exercise_id, target_sets, target_reps, target_rom,
             instructions, precautions, hand)
        )
        conn.commit()
        return cursor.lastrowid


def get_patient_prescriptions(
    patient_id: int,
    active_only: bool = True,
    db_path: Optional[str] = None
) -> List[Dict[str, Any]]:
    query = """
        SELECT pr.*, e.name as exercise_name, e.code as exercise_code, e.description as exercise_description,
               t.target_region, t.target_joints, t.target_muscles, t.clinical_purpose,
               u_clin.full_name as clinician_name
        FROM prescriptions pr
        JOIN exercises e ON pr.exercise_id = e.id
        LEFT JOIN exercise_targets t ON e.id = t.exercise_id
        JOIN clinicians c ON pr.clinician_id = c.id
        JOIN users u_clin ON c.user_id = u_clin.id
        WHERE pr.patient_id = ?
    """
    if active_only:
        query += " AND pr.status = 'active'"
    query += " ORDER BY pr.id DESC"

    with db_context(db_path) as conn:
        rows = conn.execute(query, (patient_id,)).fetchall()
        return [dict(r) for r in rows]


def get_prescription_by_id(prescription_id: int, db_path: Optional[str] = None) -> Optional[Dict[str, Any]]:
    with db_context(db_path) as conn:
        row = conn.execute(
            """
            SELECT pr.*, e.name as exercise_name, e.code as exercise_code,
                   t.target_region, t.target_joints, t.target_muscles, t.clinical_purpose,
                   u_p.full_name as patient_name
            FROM prescriptions pr
            JOIN exercises e ON pr.exercise_id = e.id
            LEFT JOIN exercise_targets t ON e.id = t.exercise_id
            JOIN patients p ON pr.patient_id = p.id
            JOIN users u_p ON p.user_id = u_p.id
            WHERE pr.id = ?
            """,
            (prescription_id,)
        ).fetchone()
        return dict(row) if row else None


# --- Sessions & Measurements ---

def record_session(
    prescription_id: int,
    patient_id: int,
    start_time: str,
    end_time: str,
    reps_completed: int,
    session_rom: float,
    reliability_status: str = "reliable",
    db_path: Optional[str] = None
) -> int:
    with db_context(db_path) as conn:
        cursor = conn.cursor()
        cursor.execute(
            """
            INSERT INTO sessions (
                prescription_id, patient_id, start_time, end_time, reps_completed, session_rom, reliability_status
            ) VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (prescription_id, patient_id, start_time, end_time, reps_completed, session_rom, reliability_status)
        )
        conn.commit()
        return cursor.lastrowid


def record_rep_measurement(
    session_id: int,
    rep_number: int,
    min_angle: float,
    max_angle: float,
    rom: float,
    duration_seconds: float,
    db_path: Optional[str] = None
) -> int:
    with db_context(db_path) as conn:
        cursor = conn.cursor()
        cursor.execute(
            """
            INSERT INTO session_measurements (
                session_id, rep_number, min_angle, max_angle, rom, duration_seconds
            ) VALUES (?, ?, ?, ?, ?, ?)
            """,
            (session_id, rep_number, min_angle, max_angle, rom, duration_seconds)
        )
        conn.commit()
        return cursor.lastrowid


def get_patient_session_history(
    patient_id: int,
    db_path: Optional[str] = None
) -> List[Dict[str, Any]]:
    with db_context(db_path) as conn:
        rows = conn.execute(
            """
            SELECT s.*, e.name as exercise_name, e.code as exercise_code, pr.target_reps, pr.target_rom
            FROM sessions s
            JOIN prescriptions pr ON s.prescription_id = pr.id
            JOIN exercises e ON pr.exercise_id = e.id
            WHERE s.patient_id = ?
            ORDER BY s.id DESC
            """,
            (patient_id,)
        ).fetchall()
        return [dict(r) for r in rows]


def get_session_details_with_reps(
    session_id: int,
    db_path: Optional[str] = None
) -> Optional[Dict[str, Any]]:
    with db_context(db_path) as conn:
        s_row = conn.execute(
            """
            SELECT s.*, e.name as exercise_name, e.code as exercise_code,
                   pr.target_reps, pr.target_rom, pr.instructions, pr.precautions, pr.hand
            FROM sessions s
            JOIN prescriptions pr ON s.prescription_id = pr.id
            JOIN exercises e ON pr.exercise_id = e.id
            WHERE s.id = ?
            """,
            (session_id,)
        ).fetchone()
        if not s_row:
            return None

        rep_rows = conn.execute(
            """
            SELECT * FROM session_measurements
            WHERE session_id = ?
            ORDER BY rep_number ASC
            """,
            (session_id,)
        ).fetchall()

        session_dict = dict(s_row)
        session_dict["measurements"] = [dict(r) for r in rep_rows]
        return session_dict
