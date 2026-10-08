"""
Flask Backend Application for AI-Assisted Physiotherapy Platform.

Implements:
- Session-based authentication with Werkzeug password verification.
- Role-based Access Control (Clinician vs Patient isolation).
- Prescription management and clinician-editable exercise targets.
- Session and per-rep measurement telemetry persistence.
- Patient ROM trend and adherence reporting.
- MJPEG camera streaming endpoint with live skeletal overlay.
- Frontend HTML rendering routes for Patient & Clinician portals.
"""

import os
import sys
import json
import time
from functools import wraps
import cv2
from flask import (
    Flask, request, jsonify, session, Response, render_template, redirect, url_for
)

# Ensure project root in sys.path
BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

from database.db import (
    init_db, get_db_connection, verify_user_credentials, create_user,
    create_clinician_profile, create_patient_profile,
    get_patient_by_user_id, get_clinician_by_user_id, get_all_patients,
    get_all_exercises, get_exercise_by_id, update_exercise_target,
    create_prescription, get_patient_prescriptions, get_prescription_by_id,
    record_session, record_rep_measurement,
    get_patient_session_history, get_session_details_with_reps
)
from src.pose.camera import CameraManager
from src.pose.detector import HandDetector
from src.pose.drawing import draw_skeleton
from src.analysis.exercises import ExerciseTracker, EXERCISE_REGISTRY


def create_app(db_path: str = None, test_config: dict = None) -> Flask:
    app = Flask(
        __name__,
        template_folder=os.path.join(BASE_DIR, "frontend", "templates"),
        static_folder=os.path.join(BASE_DIR, "frontend", "static")
    )
    app.config["SECRET_KEY"] = os.environ.get("SECRET_KEY", "hand-physio-rehab-local-dev-secret-key-2026")
    app.config["SESSION_COOKIE_HTTPONLY"] = True
    app.config["SESSION_COOKIE_SAMESITE"] = "Lax"
    app.config["DB_PATH"] = db_path or os.path.join(BASE_DIR, "database", "hand_physio.db")

    if test_config:
        app.config.update(test_config)

    # Initialize tables if db does not exist
    if not os.path.exists(app.config["DB_PATH"]):
        init_db(app.config["DB_PATH"])

    # Global active trackers dictionary for live sessions: prescription_id -> ExerciseTracker
    active_trackers = {}

    # --- Auth Decorators ---

    def login_required(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            if "user_id" not in session:
                if request.path.startswith("/api/"):
                    return jsonify({"error": "Authentication required", "authenticated": False}), 401
                return redirect(url_for("page_login"))
            return f(*args, **kwargs)
        return decorated_function

    def role_required(*allowed_roles):
        def decorator(f):
            @wraps(f)
            def decorated_function(*args, **kwargs):
                if "user_id" not in session:
                    if request.path.startswith("/api/"):
                        return jsonify({"error": "Authentication required"}), 401
                    return redirect(url_for("page_login"))
                if session.get("role") not in allowed_roles:
                    if request.path.startswith("/api/"):
                        return jsonify({"error": "Access forbidden: insufficient role permissions"}), 403
                    return "Access Forbidden: Insufficient Permissions", 403
                return f(*args, **kwargs)
            return decorated_function
        return decorator

    # --- Web Page Views ---

    @app.route("/")
    def page_index():
        if "user_id" in session:
            if session.get("role") == "clinician":
                return redirect(url_for("page_clinician_dashboard"))
            return redirect(url_for("page_patient_dashboard"))
        return redirect(url_for("page_login"))

    @app.route("/login")
    def page_login():
        if "user_id" in session:
            return redirect(url_for("page_index"))
        return render_template("login.html")

    @app.route("/patient")
    @login_required
    @role_required("patient")
    def page_patient_dashboard():
        patient_id = session.get("profile_id")
        prescriptions = get_patient_prescriptions(patient_id, active_only=True, db_path=app.config["DB_PATH"])
        sessions = get_patient_session_history(patient_id, db_path=app.config["DB_PATH"])
        return render_template("patient/dashboard.html", prescriptions=prescriptions, sessions=sessions)

    @app.route("/patient/workout/<int:prescription_id>")
    @login_required
    @role_required("patient")
    def page_patient_workout(prescription_id):
        presc = get_prescription_by_id(prescription_id, db_path=app.config["DB_PATH"])
        if not presc or presc["patient_id"] != session.get("profile_id"):
            return "Prescription not found or access denied", 404
        return render_template("patient/workout.html", prescription=presc)

    @app.route("/clinician")
    @login_required
    @role_required("clinician")
    def page_clinician_dashboard():
        # Handled in Stage 9
        patients = get_all_patients(db_path=app.config["DB_PATH"])
        exercises = get_all_exercises(db_path=app.config["DB_PATH"])
        return render_template("clinician/dashboard.html", patients=patients, exercises=exercises)

    # --- Authentication API Endpoints ---

    @app.route("/api/login", methods=["POST"])
    def api_login():
        data = request.get_json() or {}
        username = data.get("username", "").strip()
        password = data.get("password", "")

        user = verify_user_credentials(username, password, db_path=app.config["DB_PATH"])
        if not user:
            return jsonify({"error": "Invalid username or password"}), 401

        session["user_id"] = user["id"]
        session["username"] = user["username"]
        session["role"] = user["role"]
        session["full_name"] = user["full_name"]

        # Cache clinician/patient profile ID into session
        if user["role"] == "clinician":
            c = get_clinician_by_user_id(user["id"], db_path=app.config["DB_PATH"])
            session["profile_id"] = c["id"] if c else None
        else:
            p = get_patient_by_user_id(user["id"], db_path=app.config["DB_PATH"])
            session["profile_id"] = p["id"] if p else None

        return jsonify({
            "success": True,
            "user": {
                "id": user["id"],
                "username": user["username"],
                "role": user["role"],
                "full_name": user["full_name"],
                "profile_id": session.get("profile_id")
            }
        })

    @app.route("/api/logout", methods=["POST"])
    def api_logout():
        session.clear()
        return jsonify({"success": True, "message": "Logged out successfully"})

    @app.route("/api/me", methods=["GET"])
    def api_me():
        if "user_id" not in session:
            return jsonify({"authenticated": False}), 200
        return jsonify({
            "authenticated": True,
            "user": {
                "id": session.get("user_id"),
                "username": session.get("username"),
                "role": session.get("role"),
                "full_name": session.get("full_name"),
                "profile_id": session.get("profile_id")
            }
        })

    # --- Patient Management Endpoints (Clinician Only) ---

    @app.route("/api/patients", methods=["GET"])
    @login_required
    @role_required("clinician")
    def api_get_patients():
        patients = get_all_patients(db_path=app.config["DB_PATH"])
        return jsonify({"patients": patients})

    @app.route("/api/patients", methods=["POST"])
    @login_required
    @role_required("clinician")
    def api_create_patient():
        data = request.get_json() or {}
        username = data.get("username", "").strip()
        password = data.get("password", "").strip()
        full_name = data.get("full_name", "").strip()
        date_of_birth = data.get("date_of_birth", "").strip()
        notes = data.get("notes", "").strip()

        if not username or not password or not full_name:
            return jsonify({"error": "Username, password, and full name are required"}), 400

        try:
            user_id = create_user(username, password, "patient", full_name, db_path=app.config["DB_PATH"])
            patient_id = create_patient_profile(user_id, date_of_birth, notes, db_path=app.config["DB_PATH"])
            return jsonify({"success": True, "patient_id": patient_id, "user_id": user_id}), 201
        except Exception as e:
            err_str = str(e).lower()
            if "unique" in err_str or "already exists" in err_str:
                return jsonify({"error": f"Username '{username}' already exists"}), 400
            return jsonify({"error": "Failed to create patient account. Please check provided details."}), 400

    # --- Exercises & Targets Catalog ---

    @app.route("/api/exercises", methods=["GET"])
    @login_required
    def api_get_exercises():
        exercises = get_all_exercises(db_path=app.config["DB_PATH"])
        return jsonify({"exercises": exercises})

    @app.route("/api/exercises/<int:exercise_id>/targets", methods=["PUT"])
    @login_required
    @role_required("clinician")
    def api_update_exercise_targets(exercise_id):
        data = request.get_json() or {}
        target_region = data.get("target_region", "").strip()
        target_joints = data.get("target_joints", "").strip()
        target_muscles = data.get("target_muscles", "").strip()
        clinical_purpose = data.get("clinical_purpose", "").strip()

        if not target_region or not clinical_purpose:
            return jsonify({"error": "Target region and clinical purpose are required"}), 400

        clin_id = session.get("profile_id")
        update_exercise_target(
            exercise_id=exercise_id,
            target_region=target_region,
            target_joints=target_joints,
            target_muscles=target_muscles,
            clinical_purpose=clinical_purpose,
            edited_by_clinician_id=clin_id,
            db_path=app.config["DB_PATH"]
        )
        return jsonify({"success": True, "message": "Exercise targets updated successfully"})

    # --- Prescription Endpoints ---

    @app.route("/api/prescriptions", methods=["GET"])
    @login_required
    def api_get_prescriptions():
        role = session.get("role")
        patient_id = request.args.get("patient_id", type=int)

        if role == "patient":
            patient_id = session.get("profile_id")
            prescriptions = get_patient_prescriptions(patient_id, active_only=True, db_path=app.config["DB_PATH"])
        else:
            if patient_id:
                prescriptions = get_patient_prescriptions(patient_id, active_only=False, db_path=app.config["DB_PATH"])
            else:
                with get_db_connection(app.config["DB_PATH"]) as conn:
                    rows = conn.execute(
                        """
                        SELECT pr.*, e.name as exercise_name, e.code as exercise_code,
                               u_p.full_name as patient_name
                        FROM prescriptions pr
                        JOIN exercises e ON pr.exercise_id = e.id
                        JOIN patients p ON pr.patient_id = p.id
                        JOIN users u_p ON p.user_id = u_p.id
                        ORDER BY pr.id DESC
                        """
                    ).fetchall()
                    prescriptions = [dict(r) for r in rows]

        return jsonify({"prescriptions": prescriptions})

    @app.route("/api/prescriptions", methods=["POST"])
    @login_required
    @role_required("clinician")
    def api_create_prescription():
        data = request.get_json() or {}
        patient_id = data.get("patient_id")
        exercise_id = data.get("exercise_id")
        target_sets = data.get("target_sets", 3)
        target_reps = data.get("target_reps", 10)
        target_rom = data.get("target_rom", 80.0)
        instructions = data.get("instructions", "").strip()
        precautions = data.get("precautions", "").strip()
        hand = data.get("hand", "right").lower()

        if not patient_id or not exercise_id:
            return jsonify({"error": "Patient and exercise are required"}), 400
        if hand not in ("left", "right"):
            return jsonify({"error": "Hand must be 'left' or 'right'"}), 400

        try:
            target_sets = int(data.get("target_sets", 3))
            target_reps = int(data.get("target_reps", 10))
            target_rom = float(data.get("target_rom", 80.0))
        except (ValueError, TypeError):
            return jsonify({"error": "Target sets, reps, and ROM must be valid numbers"}), 400

        if not (1 <= target_sets <= 10):
            return jsonify({"error": "Target sets must be an integer between 1 and 10"}), 400
        if not (1 <= target_reps <= 50):
            return jsonify({"error": "Target reps must be an integer between 1 and 50"}), 400
        if not (0.05 <= target_rom <= 180.0):
            return jsonify({"error": "Target ROM must be between 0.05 and 180.0"}), 400

        clin_id = session.get("profile_id")
        presc_id = create_prescription(
            clinician_id=clin_id,
            patient_id=patient_id,
            exercise_id=exercise_id,
            target_sets=target_sets,
            target_reps=target_reps,
            target_rom=target_rom,
            instructions=instructions,
            precautions=precautions,
            hand=hand,
            db_path=app.config["DB_PATH"]
        )
        return jsonify({"success": True, "prescription_id": presc_id}), 201

    @app.route("/api/prescriptions/<int:prescription_id>", methods=["GET"])
    @login_required
    def api_get_prescription(prescription_id):
        presc = get_prescription_by_id(prescription_id, db_path=app.config["DB_PATH"])
        if not presc:
            return jsonify({"error": "Prescription not found"}), 404

        if session.get("role") == "patient" and presc["patient_id"] != session.get("profile_id"):
            return jsonify({"error": "Access forbidden"}), 403

        return jsonify({"prescription": presc})

    # --- Session & Measurement Telemetry Endpoints ---

    @app.route("/api/sessions", methods=["POST"])
    @login_required
    def api_record_session():
        data = request.get_json() or {}
        prescription_id = data.get("prescription_id")
        start_time = data.get("start_time")
        end_time = data.get("end_time")
        reps_completed = data.get("reps_completed", 0)
        session_rom = data.get("session_rom", 0.0)
        reliability_status = data.get("reliability_status", "reliable")
        measurements = data.get("measurements", [])

        presc = get_prescription_by_id(prescription_id, db_path=app.config["DB_PATH"])
        if not presc:
            return jsonify({"error": "Prescription not found"}), 404

        if session.get("role") == "patient" and presc["patient_id"] != session.get("profile_id"):
            return jsonify({"error": "Access forbidden"}), 403

        session_id = record_session(
            prescription_id=prescription_id,
            patient_id=presc["patient_id"],
            start_time=start_time,
            end_time=end_time,
            reps_completed=reps_completed,
            session_rom=session_rom,
            reliability_status=reliability_status,
            db_path=app.config["DB_PATH"]
        )

        for m in measurements:
            record_rep_measurement(
                session_id=session_id,
                rep_number=m.get("rep_number", 1),
                min_angle=m.get("min_value", 0.0),
                max_angle=m.get("max_value", 0.0),
                rom=m.get("rom", 0.0),
                duration_seconds=m.get("duration_seconds", 0.0),
                db_path=app.config["DB_PATH"]
            )

        return jsonify({"success": True, "session_id": session_id}), 201

    @app.route("/api/patients/<int:patient_id>/sessions", methods=["GET"])
    @login_required
    def api_get_patient_sessions(patient_id):
        if session.get("role") == "patient" and patient_id != session.get("profile_id"):
            return jsonify({"error": "Access forbidden"}), 403

        sessions = get_patient_session_history(patient_id, db_path=app.config["DB_PATH"])
        return jsonify({"sessions": sessions})

    @app.route("/api/sessions/<int:session_id>", methods=["GET"])
    @login_required
    def api_get_session_details(session_id):
        details = get_session_details_with_reps(session_id, db_path=app.config["DB_PATH"])
        if not details:
            return jsonify({"error": "Session not found"}), 404

        if session.get("role") == "patient" and details["patient_id"] != session.get("profile_id"):
            return jsonify({"error": "Access forbidden"}), 403

        return jsonify({"session": details})

    @app.route("/api/patients/<int:patient_id>/trends", methods=["GET"])
    @login_required
    def api_get_patient_trends(patient_id):
        if session.get("role") == "patient" and patient_id != session.get("profile_id"):
            return jsonify({"error": "Access forbidden"}), 403

        sessions = get_patient_session_history(patient_id, db_path=app.config["DB_PATH"])
        labels = []
        rom_series = []
        reps_series = []

        for s in reversed(sessions):
            dt = s["start_time"][:10]
            labels.append(dt)
            rom_series.append(s["session_rom"])
            reps_series.append(s["reps_completed"])

        return jsonify({
            "labels": labels,
            "rom_trend": rom_series,
            "reps_trend": reps_series,
            "total_sessions": len(sessions)
        })

    # --- Live Stream Telemetry & Video Feed ---

    @app.route("/api/live_state/<int:prescription_id>", methods=["GET"])
    @login_required
    def api_live_state(prescription_id):
        tracker = active_trackers.get(prescription_id)
        if not tracker:
            return jsonify({"active": False, "rep_count": 0, "session_summary": None})

        return jsonify({
            "active": True,
            "rep_count": tracker.counter.rep_count,
            "smoothed_value": tracker.counter.last_smoothed_val,
            "state": tracker.counter.state.value,
            "session_summary": tracker.get_session_summary()
        })

    @app.route("/api/reset_session/<int:prescription_id>", methods=["POST"])
    @login_required
    def api_reset_session(prescription_id):
        if prescription_id in active_trackers:
            active_trackers[prescription_id].counter.reset()
        return jsonify({"success": True})

    @app.route("/api/video_feed/<int:prescription_id>")
    @login_required
    def api_video_feed(prescription_id):
        """
        MJPEG video feed for real-time local webcam streaming.
        Reads frames from camera index 0, runs MediaPipe HandLandmarker,
        updates ExerciseTracker, renders skeletal overlay, and yields multipart JPEG chunks.
        """
        presc = get_prescription_by_id(prescription_id, db_path=app.config["DB_PATH"])
        if not presc:
            return "Prescription not found", 404

        exercise_code = presc["exercise_code"]
        target_hand = presc["hand"]

        # Instantiate or retrieve active tracker for this prescription
        tracker = ExerciseTracker(exercise_code)
        active_trackers[prescription_id] = tracker

        def generate_frames():
            cam = CameraManager(camera_index=0, warmup_seconds=1.0, max_consecutive_failures=30)
            detector = HandDetector(min_confidence=0.6)

            if not cam.open():
                return

            try:
                while True:
                    success, frame = cam.read_frame()
                    if not success or frame is None:
                        time.sleep(0.03)
                        continue

                    # Hand detection with target hand filtering
                    detection = detector.detect(frame, target_hand=target_hand)

                    # Update exercise tracker
                    tracker.update(detection.landmarks, is_reliable=detection.is_tracked)

                    # Annotate frame with skeleton and HUD
                    annotated = draw_skeleton(frame, detection)

                    # Compress frame to JPEG
                    ret, buffer = cv2.imencode(".jpg", annotated, [cv2.IMWRITE_JPEG_QUALITY, 80])
                    if not ret:
                        continue

                    frame_bytes = buffer.tobytes()
                    yield (
                        b"--frame\r\n"
                        b"Content-Type: image/jpeg\r\n\r\n" + frame_bytes + b"\r\n"
                    )
                    time.sleep(0.03)
            finally:
                cam.release()
                detector.close()

        return Response(generate_frames(), mimetype="multipart/x-mixed-replace; boundary=frame")

    return app


# Root dev instance
app = create_app()

if __name__ == "__main__":
    debug_mode = os.environ.get("FLASK_DEBUG", "0").lower() in ("1", "true")
    app.run(host="127.0.0.1", port=5000, debug=debug_mode)
