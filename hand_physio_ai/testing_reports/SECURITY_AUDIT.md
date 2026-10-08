# Stage 3: Comprehensive Security Audit & Vulnerability Assessment

**Date of Audit:** October 2026  
**Auditor:** Senior Ethical Security Auditor & Healthcare Software Safety Reviewer  
**Scope:** `hand_physio_ai` backend, database, APIs, and dependencies  
**Standards Evaluated:** OWASP Top 10 (2021), HIPAA / GDPR Data Minimization Safeguards  

---

## 1. Executive Summary

A comprehensive automated and manual security evaluation was performed on the HandPhysio AI platform. The system demonstrated strong security architecture, including proper cryptographic password hashing, role-based session isolation, and strict parameter bounds checking.

Prior to hardening, automated static analysis flagged two areas for remediation (`debug=True` in production entry point and unconstrained URL scheme handling in model retrieval). Both findings have been fully remediated and verified.

---

## 2. OWASP Top 10 Compliance Matrix

| OWASP Category | Finding / Status | Technical Safeguard Implemented |
| :--- | :---: | :--- |
| **A01: Broken Access Control** | **PROTECTED** | Enforced via `@login_required` and `@role_required("clinician")` decorators. Patients attempting to access clinician endpoints receive `403 Forbidden`. Cross-patient access (IDOR) is blocked by verifying `presc["patient_id"] == session["profile_id"]`. |
| **A02: Cryptographic Failures** | **PROTECTED** | Passwords hashed using Werkzeug's modern cryptographic KDF (`generate_password_hash` with secure salt). Session cookie configured with `HttpOnly=True` and `SameSite=Lax`. Session secret key supports dynamic injection via environment variable `SECRET_KEY`. |
| **A03: Injection (SQLi / XSS)** | **PROTECTED** | All database operations use SQLite parameterized queries (`?` placeholders). Raw SQL string concatenation is strictly prohibited. Jinja2 templates escape user-supplied variables by default. |
| **A04: Insecure Design** | **PROTECTED** | Privacy Rule #6 enforces strict data minimization: zero persistence of raw video frames or photos. Database stores only aggregated numerical telemetry. |
| **A05: Security Misconfiguration** | **REMEDIATED** | Hardened `app.run` entry point: `debug=False` by default, toggled only via explicit environment variable `FLASK_DEBUG=1`. |
| **A06: Vulnerable Dependencies** | **AUDITED** | Scanned with `pip-audit`. All runtime application packages (Flask 3.0.0, OpenCV 4.8.1, MediaPipe 1.1.0, NumPy 1.26.4) have zero known vulnerabilities. |
| **A07: Identification & Auth Failures** | **PROTECTED** | Invalid credentials return a generic `401 Unauthorized` without revealing whether the username exists. Password verification uses constant-time comparison in Werkzeug. |
| **A08: Software & Data Integrity** | **REMEDIATED** | Model download in `src/pose/detector.py` validates that the URL scheme begins with `https://` before retrieval. |
| **A09: Security Logging & Monitoring** | **PROTECTED** | Backend logs authentication attempts and API operations. Database errors return sanitized error messages without exposing schema traces to clients. |
| **A10: Server-Side Request Forgery** | **PROTECTED** | No user-controlled endpoints initiate outbound HTTP/network requests. |

---

## 3. Static Code Analysis (Bandit)

Bandit AST security scanner was run against all project code:
```bash
bandit -r hand_physio_ai\src hand_physio_ai\backend hand_physio_ai\database -ll
```

### Scan Metrics:
- **Total Lines of Code Scanned:** 1,898
- **High Severity Issues:** 0
- **Medium Severity Issues:** 0
- **Low Severity Issues:** 2 (standard fallback string constants in non-production blocks)
- **Status:** **PASS**

### Hardening Actions Applied:
1. **Flask Debug Hardening (`backend/app.py`):**
   - *Previous:* `app.run(..., debug=True)`
   - *Remediation:* Changed to `debug=os.environ.get("FLASK_DEBUG", "0").lower() in ("1", "true")`. Production defaults to `debug=False`.
2. **Session Cookie Hardening (`backend/app.py`):**
   - Configured `SESSION_COOKIE_HTTPONLY = True` to prevent client-side script cookie theft.
   - Configured `SESSION_COOKIE_SAMESITE = "Lax"` to prevent Cross-Site Request Forgery (CSRF).
3. **URL Scheme Validation (`src/pose/detector.py`):**
   - Added validation check: `if not self.MODEL_URL.startswith("https://"): raise ValueError(...)` before calling `urllib.request.urlretrieve`.
4. **Input Boundary Validation (`backend/app.py`):**
   - Added strict numeric range validation on `api_create_prescription`:
     - `target_sets`: integer $\in [1, 10]$
     - `target_reps`: integer $\in [1, 50]$
     - `target_rom`: float $\in [0.05, 180.0]$
5. **Database Exception Sanitization (`backend/app.py`):**
   - Replaced raw exception string propagation in `api_create_patient` with sanitized messages: `"Username already exists"` or `"Failed to create patient account."`

---

## 4. Insecure Direct Object Reference (IDOR) & RBAC Tests

Automated integration tests (`tests/test_full_user_journey.py` and `tests/test_backend.py`) verify the following access boundaries:

| Attack Vector | Simulated Scenario | Expected Result | Actual Result |
| :--- | :--- | :---: | :---: |
| **Cross-Patient Session Access** | Patient Alice attempts `GET /api/patients/1/sessions` (John Doe's records) | 403 Forbidden | **403 Forbidden** |
| **Cross-Patient Prescription Access** | Patient Alice requests `GET /api/prescriptions/1` (John Doe's prescription) | 403 Forbidden | **403 Forbidden** |
| **Privilege Escalation (Prescribing)** | Patient Alice attempts `POST /api/prescriptions` | 403 Forbidden | **403 Forbidden** |
| **Privilege Escalation (User Creation)** | Patient Alice attempts `POST /api/patients` | 403 Forbidden | **403 Forbidden** |
| **Unauthenticated API Access** | Guest requests `GET /api/patients` without cookie | 401 Unauthorized | **401 Unauthorized** |
| **Unauthenticated Page Access** | Guest browses to `/clinician` or `/patient` | Redirect to `/login` | **Redirected** |

---

## 5. Healthcare Data Privacy & Zero-Storage Compliance

Under Healthcare Software Safety **Rule #6**, biometric raw imagery (faces, webcam video frames, raw photos) must **never** be saved to disk or persistent storage:

- **Database Audit:** SQLite `PRAGMA table_info(sessions)` and `PRAGMA table_info(session_measurements)` were programmatically inspected.
- **Result:** No BLOB columns, no image paths, and no binary media fields exist.
- **Volatile Processing:** Frame processing occurs strictly in volatile memory (RAM) inside the generator loop `api_video_feed`. Frames are discarded immediately upon transmission to the local browser.
