# Stage 5: Bug Report, Vulnerability Log & Remediation Record

**Date of Audit:** October 2026  
**Auditor:** Senior QA & Security Reviewer  
**Total Issues Identified:** 5  
**Total Issues Resolved & Verified:** 5 (100% Fixed)  

---

## 1. Issue Tracking Summary

| Bug ID | Component | Severity | Description | Status |
| :---: | :--- | :---: | :--- | :---: |
| **BUG-001** | `backend/app.py` | **HIGH** | Flask `debug=True` hardcoded in `__main__` entry point | **FIXED** |
| **BUG-002** | `src/pose/detector.py` | **MEDIUM** | Insecure URL scheme download in `_ensure_model_exists` | **FIXED** |
| **BUG-003** | `backend/app.py` | **MEDIUM** | Missing numeric bounds validation on `POST /api/prescriptions` | **FIXED** |
| **BUG-004** | `backend/app.py` | **LOW** | Database exception traces leaked to client in `api_create_patient` | **FIXED** |
| **BUG-005** | `database/db.py` | **LOW** | Windows SQLite file locks on temp databases during unit tests | **FIXED** |

---

## 2. In-Depth Bug Profiles & Remediations

### BUG-001: Flask Debug Mode Active in Main Runner
- **Severity:** HIGH (CWE-489: Active Debug Code in Production)
- **Flagged By:** Bandit AST Scanner (`B201:flask_debug_true`)
- **Root Cause:** Line 510 of `backend/app.py` executed `app.run(host="127.0.0.1", port=5000, debug=True)`. In production or public networks, Flask's interactive debugger permits arbitrary remote code execution via PIN authentication.
- **Remediation:** Changed `debug` parameter to read from environment variable with safe default:
  ```python
  debug_mode = os.environ.get("FLASK_DEBUG", "0").lower() in ("1", "true")
  app.run(host="127.0.0.1", port=5000, debug=debug_mode)
  ```
- **Verification:** Verified by re-running Bandit scanner (0 High severity issues).

---

### BUG-002: Insecure URL Scheme Download in Detector
- **Severity:** MEDIUM (CWE-319: Cleartext Transmission of Sensitive Information)
- **Flagged By:** Bandit AST Scanner (`B310:urllib_urlopen`)
- **Root Cause:** `urllib.request.urlretrieve(self.MODEL_URL, self.model_path)` did not validate that `self.MODEL_URL` uses the HTTPS protocol.
- **Remediation:** Added explicit scheme verification before triggering download:
  ```python
  if not self.MODEL_URL.startswith("https://"):
      raise ValueError(f"Insecure or unsupported model download URL scheme: {self.MODEL_URL}")
  ```
- **Verification:** Verified by Bandit scan and `tests/test_detector.py`.

---

### BUG-003: Missing Range Validation on Prescription Parameters
- **Severity:** MEDIUM (CWE-20: Improper Input Validation)
- **Root Cause:** `api_create_prescription` accepted arbitrary `target_sets`, `target_reps`, and `target_rom` without asserting upper/lower bounds. Out-of-range values (e.g. 1000 sets, negative ROM) could be submitted via API.
- **Remediation:** Added strict boundary checks:
  ```python
  if not (1 <= target_sets <= 10):
      return jsonify({"error": "Target sets must be an integer between 1 and 10"}), 400
  if not (1 <= target_reps <= 50):
      return jsonify({"error": "Target reps must be an integer between 1 and 50"}), 400
  if not (0.05 <= target_rom <= 180.0):
      return jsonify({"error": "Target ROM must be between 0.05 and 180.0"}), 400
  ```
- **Verification:** Verified by `tests/test_full_user_journey.py` (bad prescription assertions).

---

### BUG-004: Raw SQLite Exception Leaks in Patient Registration
- **Severity:** LOW (CWE-209: Information Exposure Through an Error Message)
- **Root Cause:** `api_create_patient` caught generic `Exception as e` and returned `jsonify({"error": str(e)}), 400`. For unique constraint collisions, raw SQLite table schemas (`UNIQUE constraint failed: users.username`) were exposed to clients.
- **Remediation:** Sanitized error handling:
  ```python
  err_str = str(e).lower()
  if "unique" in err_str or "already exists" in err_str:
      return jsonify({"error": f"Username '{username}' already exists"}), 400
  return jsonify({"error": "Failed to create patient account. Please check provided details."}), 400
  ```
- **Verification:** Verified in integration tests with duplicate username inputs.

---

### BUG-005: Windows SQLite File Locking During Test Teardown
- **Severity:** LOW (Environment / OS Compatibility)
- **Root Cause:** On Windows, SQLite holds file locks on temporary `.db` files until garbage collection releases all connections. `tearDown` calling `os.remove(self.db_path)` raised `PermissionError: [WinError 32]`.
- **Remediation:** Enforced proper connection closing via context manager and wrapped `tearDown` cleanup in an `OSError / PermissionError` safe handler.
- **Verification:** Full test suite execution across all 65 tests passes cleanly on Windows 11 without file lock failures.
