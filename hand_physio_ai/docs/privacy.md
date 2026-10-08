# Privacy & Data Governance Architecture

> **Notice:** Camera-based estimate, not a clinical measurement. Strict adherence to healthcare data privacy standards.

---

## 1. Zero Persistent Media Architecture (Hard Rule #6)

In healthcare technology, patient privacy is paramount. Patients exercising in front of home webcams must never have their personal living spaces or facial likenesses inadvertently recorded or stored.

### 1.1. Transient In-Memory Frame Processing
- Video frames captured by OpenCV reside exclusively in volatile RAM buffers.
- Once MediaPipe computes the 21 coordinate points, the raw pixel buffer is discarded.
- Neither the server filesystem nor the SQLite database contains any video or image files.

### 1.2. Automated Codebase & Database Verification
The project includes an automated compliance test ([test_safety_privacy_compliance.py](file:///c:/Users/Shinto%20Thomas/Desktop/projects/aicw%20project/hand_physio_ai/tests/test_safety_privacy_compliance.py)) that inspects all tables in `schema.sql` and `hand_physio.db`. The test asserts that no table schema defines columns matching `image`, `video`, `frame`, `photo`, or `recording`.

---

## 2. Derived Telemetry Model

The database stores only non-identifying physical therapy measurements:

| Stored Data Field | Clinical Purpose | Privacy Risk |
| :--- | :--- | :--- |
| **`timestamp`** | Tracks when the session took place. | Low |
| **`rep_number`** | Counts physical repetitions completed. | None |
| **`min_angle` / `max_angle`** | Records joint inflection points. | None |
| **`rom`** | Range of Motion ($\text{max} - \text{min}$). | None |
| **`duration_seconds`** | Measures exercise cadence. | None |
| **`reliability_status`** | Notes if tracking was stable or degraded. | None |

---

## 3. Access Control & Role Isolation

- **Role-Based Access Control (RBAC):** Passwords are encrypted using irreversible salted PBKDF2 hashes.
- **Patient Isolation:** A patient logging into the platform is cryptographically restricted by server-side decorators from querying, viewing, or modifying any prescription or workout session other than their own.
