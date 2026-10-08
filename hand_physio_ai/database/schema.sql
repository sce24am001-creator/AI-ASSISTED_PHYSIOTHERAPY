-- AI-Assisted Physiotherapy Platform Database Schema
-- SQLite3 with Foreign Key constraints enabled
-- PRIVACY COMPLIANT: Stores derived kinematic measurements ONLY. NEVER stores raw video or images.

PRAGMA foreign_keys = ON;

-- Core User Accounts
CREATE TABLE IF NOT EXISTS users (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    username TEXT UNIQUE NOT NULL,
    password_hash TEXT NOT NULL,
    role TEXT NOT NULL CHECK (role IN ('clinician', 'patient')),
    full_name TEXT NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Clinician Extended Profiles
CREATE TABLE IF NOT EXISTS clinicians (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER UNIQUE NOT NULL,
    license_number TEXT NOT NULL,
    clinic_name TEXT NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
);

-- Patient Extended Profiles
CREATE TABLE IF NOT EXISTS patients (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER UNIQUE NOT NULL,
    date_of_birth TEXT,
    notes TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
);

-- Exercise Catalog
CREATE TABLE IF NOT EXISTS exercises (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    code TEXT UNIQUE NOT NULL,
    name TEXT NOT NULL,
    description TEXT NOT NULL,
    default_hand TEXT NOT NULL DEFAULT 'either' CHECK (default_hand IN ('either', 'left', 'right')),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Clinician-Editable Anatomical Targets for Patient Guidance
CREATE TABLE IF NOT EXISTS exercise_targets (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    exercise_id INTEGER UNIQUE NOT NULL,
    target_region TEXT NOT NULL,
    target_joints TEXT NOT NULL,
    target_muscles TEXT NOT NULL,
    clinical_purpose TEXT NOT NULL,
    edited_by_clinician_id INTEGER,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (exercise_id) REFERENCES exercises(id) ON DELETE CASCADE,
    FOREIGN KEY (edited_by_clinician_id) REFERENCES clinicians(id) ON DELETE SET NULL
);

-- Clinical Prescriptions
CREATE TABLE IF NOT EXISTS prescriptions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    clinician_id INTEGER NOT NULL,
    patient_id INTEGER NOT NULL,
    exercise_id INTEGER NOT NULL,
    target_sets INTEGER NOT NULL DEFAULT 3,
    target_reps INTEGER NOT NULL DEFAULT 10,
    target_rom REAL NOT NULL,
    instructions TEXT NOT NULL,
    precautions TEXT NOT NULL,
    hand TEXT NOT NULL CHECK (hand IN ('left', 'right')),
    status TEXT NOT NULL DEFAULT 'active' CHECK (status IN ('active', 'completed', 'paused')),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (clinician_id) REFERENCES clinicians(id) ON DELETE CASCADE,
    FOREIGN KEY (patient_id) REFERENCES patients(id) ON DELETE CASCADE,
    FOREIGN KEY (exercise_id) REFERENCES exercises(id) ON DELETE CASCADE
);

-- Patient Exercise Sessions
CREATE TABLE IF NOT EXISTS sessions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    prescription_id INTEGER NOT NULL,
    patient_id INTEGER NOT NULL,
    start_time TIMESTAMP NOT NULL,
    end_time TIMESTAMP NOT NULL,
    reps_completed INTEGER NOT NULL DEFAULT 0,
    session_rom REAL NOT NULL DEFAULT 0.0,
    reliability_status TEXT NOT NULL DEFAULT 'reliable' CHECK (reliability_status IN ('reliable', 'degraded')),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (prescription_id) REFERENCES prescriptions(id) ON DELETE CASCADE,
    FOREIGN KEY (patient_id) REFERENCES patients(id) ON DELETE CASCADE
);

-- Detailed Per-Rep Kinematic Measurements
CREATE TABLE IF NOT EXISTS session_measurements (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id INTEGER NOT NULL,
    rep_number INTEGER NOT NULL,
    min_angle REAL NOT NULL,
    max_angle REAL NOT NULL,
    rom REAL NOT NULL,
    duration_seconds REAL NOT NULL,
    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (session_id) REFERENCES sessions(id) ON DELETE CASCADE
);

-- Indexes for efficient queries
CREATE INDEX IF NOT EXISTS idx_prescriptions_patient ON prescriptions(patient_id);
CREATE INDEX IF NOT EXISTS idx_prescriptions_clinician ON prescriptions(clinician_id);
CREATE INDEX IF NOT EXISTS idx_sessions_patient ON sessions(patient_id);
CREATE INDEX IF NOT EXISTS idx_sessions_prescription ON sessions(prescription_id);
CREATE INDEX IF NOT EXISTS idx_measurements_session ON session_measurements(session_id);
