# Stage 1: Full Project Architecture & Component Audit Report

**Date of Audit:** October 2026  
**Auditor:** Senior QA Automation Engineer, Ethical Security Auditor & Healthcare Software Safety Reviewer  
**Repository:** `hand_physio_ai`  
**System Title:** AI-Assisted Physiotherapy Exercise Guidance, Movement Analysis and Rehabilitation Tracking Platform  
**Target Domain:** Hand & Wrist Rehabilitation  

---

## 1. Executive Summary

This audit represents an exhaustive, hands-on architectural and code-level inspection of the HandPhysio AI platform. The system operates strictly as an assistive clinical estimation tool for home-based hand and wrist exercise tracking under a clinician-supervised model.

Every module, route, mathematical formula, database table, template, and test was examined for compliance with software engineering best practices, security standards, and healthcare safety boundaries.

---

## 2. Directory Structure & Component Inventory

```
hand_physio_ai/
│
├── backend/
│   └── app.py                      # Flask application factory, REST APIs, session auth, RBAC, MJPEG streaming
│
├── database/
│   ├── schema.sql                  # Relational SQLite schema with foreign keys and strict constraints
│   ├── db.py                       # DB abstraction layer with context manager handling and query functions
│   └── seed.py                     # Realistic clinical seed data (Dr. Sarah Jenkins, John Doe, 3 exercises)
│
├── frontend/
│   ├── templates/
│   │   ├── base.html               # Shared layout, clinical disclaimer banners, responsive CSS
│   │   ├── login.html              # Authentication portal with role-aware demo credential chips
│   │   ├── patient/
│   │   │   ├── dashboard.html      # Patient portal with interactive anatomical SVG hand diagram
│   │   │   └── workout.html        # Real-time workout room with video HUD, telemetry, and completion modal
│   │   └── clinician/
│   │       └── dashboard.html      # Clinician portal with patient directory, prescription form, Chart.js trends
│   └── static/
│       ├── css/style.css           # Premium dark-mode healthcare UI stylesheet
│       └── js/                     # Client-side telemetry handlers and chart visualizers
│
├── models/
│   └── hand_landmarker.task        # Pretrained Google MediaPipe Tasks HandLandmarker asset
│
├── src/
│   ├── pose/
│   │   ├── camera.py               # Robust OpenCV DirectShow camera capture manager with retry logic
│   │   ├── detector.py             # MediaPipe Tasks HandLandmarker wrapper with target hand isolation
│   │   └── drawing.py              # Skeletal wireframe rendering with clinical notice banners
│   ├── features/
│   │   ├── angles.py               # Vector dot product 3D joint angle calculation with arccos clipping
│   │   ├── distances.py            # Person-specific, camera-depth-invariant normalized distance ratios
│   │   └── smoothing.py            # MovingAverageFilter (N=5) noise dampening
│   └── analysis/
│       ├── rep_counter.py          # Dual-threshold hysteresis state machine with time gate (0.4s)
│       └── exercises.py            # Unified tracker registry for Fist Flexion, Thumb Opposition, Wrist Tilt
│
├── tests/                          # 65 automated test suites with 100% pass rate
│   ├── test_angles.py              # Angle calculation unit tests & edge cases
│   ├── test_camera.py              # Camera initialization, failure recovery, live hardware
│   ├── test_database.py            # DB schema, foreign keys, password hashing, Privacy Rule #6
│   ├── test_detector.py            # MediaPipe detector, untracked frames, skeleton drawing
│   ├── test_exercises.py           # 3 exercise features, distance normalization, ROM aggregations
│   ├── test_rep_counter.py         # Smoothing filter, hysteresis transitions, false rep rejection
│   ├── test_backend.py             # Auth, RBAC, patient data isolation, prescription management
│   ├── test_patient_views.py       # Patient dashboard, SVG diagram, workout room HUD
│   ├── test_clinician_views.py     # Clinician directory, prescription creation, Chart.js trends
│   ├── test_safety_privacy_compliance.py # 8 Hard Rules automated compliance verification
│   └── test_full_user_journey.py   # End-to-end integration test of complete clinical workflow
│
├── testing_reports/                # Comprehensive QA & Security Audit Reports
│   ├── PROJECT_AUDIT.md
│   ├── FUNCTIONAL_TEST_RESULTS.md
│   ├── SECURITY_AUDIT.md
│   ├── ML_VALIDATION.md
│   ├── BUG_REPORT.md
│   └── FINAL_READINESS_REPORT.md
│
├── docs/                           # System documentation and manuals
│   ├── architecture.md             # End-to-end data flow and architectural specifications
│   ├── limitations.md              # Technical and clinical boundaries
│   ├── privacy.md                  # Strict data privacy & storage rules
│   └── demo_script.md              # Step-by-step evaluator presentation guide
│
├── requirements.txt                # Pinned production dependencies
├── run.py                          # Unified launcher with preflight verification
└── test_live_angles.py / reps.py   # Interactive developer diagnostic tools
```

---

## 3. Technology Stack & Dependencies

| Layer | Technology | Version | Purpose |
| :--- | :--- | :--- | :--- |
| **Runtime** | Python | 3.11.1 (Windows DirectShow) | Base backend platform |
| **Web Framework** | Flask | 3.0.0 | REST API endpoints, session management, MJPEG streaming |
| **Database** | SQLite3 | 3.x (Built-in) | Embedded relational datastore with Foreign Key enforcement |
| **Computer Vision** | OpenCV (`opencv-python`) | 4.8.1.78 | DirectShow camera capture (`CAP_DSHOW`), frame encoding |
| **Pose Estimation** | Google MediaPipe | 1.1.0 (`mediapipe.tasks.python.vision`) | Pretrained 21 3D hand landmark extraction |
| **Numerical Engine** | NumPy | 1.26.4 | Vector math, Euclidean distances, dot products, statistics |
| **Password Security**| Werkzeug | 3.0.1 | `generate_password_hash`, `check_password_hash` (scrypt/pbkdf2) |
| **Visualization** | Chart.js | 4.4.1 (CDN) | Clinician ROM trend curves and adherence tracking |
| **UI Design** | Vanilla CSS + HTML5 | Custom Dark Theme | Responsive, accessible interface with zero heavy dependencies |

---

## 4. Compliance with 8 Core System Boundaries

1. **AI Never Diagnoses or Prescribes:** Verified. Only registered clinicians (`dr_sarah`) can prescribe exercises, set target sets/reps, and define target ROM. The AI only counts repetitions and records Range of Motion.
2. **No Invented Clinical Numbers:** Verified. No synthetic clinical claims, unverified accuracy percentages, or artificial efficacy metrics exist in the code.
3. **Mandatory Estimate Disclaimer:** Verified. `"Camera-based estimate, not a clinical measurement."` is prominently displayed on the global base template, workout HUD, video feed, and printed documentation.
4. **Rule-Based Kinematics:** Verified. Angles use vector dot products with arccos clipping; distances use Middle MCP scale normalization; rep counting uses dual-threshold hysteresis. Zero black-box neural networks for repetition counting.
5. **Tracking Fallback:** Verified. When MediaPipe confidence drops or the hand is lost, the system displays `"Movement could not be measured reliably. Adjust camera position or lighting."` and freezes state transitions.
6. **Zero Raw Video or Image Storage:** Verified. The database stores only derived numeric telemetry (`min_value`, `max_value`, `rom`, `duration_seconds`). No BLOB, image file, or video file is ever persisted.
7. **No Unvalidated Recovery Scores:** Verified. The system outputs empirical Range of Motion (`min_rom`, `mean_rom`, `max_rom`, `mean_duration`) and completed repetition counts. Never an unvalidated "percent recovered".
8. **Local Webcam DirectShow Operation:** Verified. OpenCV uses `cv2.CAP_DSHOW` with a 1.0s warm-up delay and 30-frame retry threshold, fully compatible with Windows DirectShow architecture.
