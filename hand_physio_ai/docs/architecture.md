# System Architecture: AI-Assisted Physiotherapy Platform

> **Clinical Notice:** Camera-based estimate, not a clinical measurement. The AI never diagnoses, prescribes, or claims to treat or cure. All clinical decisions remain strictly with the physiotherapist.

---

## 1. High-Level System Architecture

The platform architecture follows a modular, layered structure connecting hardware camera access, MediaPipe pose estimation, rule-based mathematical analysis, SQLite relational persistence, and Flask web interfaces:

```mermaid
graph TD
    subgraph Presentation_Layer ["Presentation Layer (HTML5 / Vanilla CSS / Chart.js)"]
        UI_Login["Portal Login (Dr. Sarah / John Doe)"]
        UI_Patient["Patient Dashboard & SVG Anatomy Map"]
        UI_Workout["Live Workout Room & HUD"]
        UI_Clinician["Clinician Management & Telemetry Charts"]
    end

    subgraph Backend_Layer ["Backend & API Layer (Flask)"]
        App["Flask Web App (app.py)"]
        Auth["Session Auth & RBAC Guards"]
        Stream["MJPEG Video Streamer"]
        API_Presc["Prescription & Target APIs"]
        API_Sessions["Session Telemetry APIs"]
    end

    subgraph Computer_Vision_Layer ["Computer Vision & Analysis Engine"]
        Cam["CameraManager (OpenCV DirectShow, 1s Warmup)"]
        Detector["HandDetector (MediaPipe Tasks 21 Landmarks)"]
        Drawing["draw_skeleton (Aesthetic Overlay & Disclaimers)"]
        Features["Feature Extraction (Dot Product Angles & Normalized Distance)"]
        Smoothing["MovingAverageFilter (Sliding Window N=5)"]
        RepCounter["RepCounter State Machine (Dual Hysteresis Thresholds)"]
    end

    subgraph Data_Layer ["Data Persistence Layer (SQLite3)"]
        DB[(hand_physio.db)]
        T_Users["users & clinicians / patients"]
        T_Catalog["exercises & exercise_targets"]
        T_Presc["prescriptions"]
        T_Sessions["sessions & session_measurements"]
    end

    Presentation_Layer --> Backend_Layer
    Backend_Layer --> Computer_Vision_Layer
    Backend_Layer --> Data_Layer
    Computer_Vision_Layer -.->|"Derived Telemetry Only (No Video Saved)"| Backend_Layer
```

---

## 2. End-to-End Clinical Flow

```mermaid
sequenceDiagram
    autonumber
    actor Clinician as Physiotherapist (Dr. Sarah)
    participant Portal as Web Application
    participant DB as SQLite Relational Database
    actor Patient as Patient (John Doe)
    participant Engine as CV Kinematics Engine

    Clinician->>Portal: 1. Logs in and selects John Doe
    Clinician->>Portal: 2. Customizes anatomical guidance & prescribes Fist Flexion (3x10 reps, 90° target)
    Portal->>DB: 3. Inserts prescription record into DB
    Patient->>Portal: 4. Logs into patient portal and views Today's Therapy
    Patient->>Portal: 5. Inspects glowing SVG anatomical diagram & clinician precautions
    Patient->>Portal: 6. Launches Live Camera Session
    Portal->>Engine: 7. Initiates CameraManager & HandDetector for prescribed hand
    loop Every Video Frame (25 FPS)
        Engine->>Engine: Extracts 21 landmarks, verifies confidence (>=0.6)
        Engine->>Engine: Calculates smoothed joint angles, updates rep state machine
        Engine-->>Portal: Streams annotated MJPEG frame with rep HUD overlay
    end
    Patient->>Portal: 8. Clicks 'Finish & Save Session'
    Portal->>DB: 9. Saves session summary & per-rep measurements (min/max angle, ROM, duration)
    Clinician->>Portal: 10. Reviews John's ROM trend line graph and adherence bar chart
```

---

## 3. Core Mathematical Models (Strictly Rule-Based)

### 3.1. Vector Angle Formula
For joint vertex $B$ with adjacent landmarks $A$ and $C$:
$$\vec{u} = A - B, \quad \vec{v} = C - B$$
$$\cos(\theta) = \frac{\vec{u} \cdot \vec{v}}{\|\vec{u}\| \|\vec{v}\|}$$
$$\theta = \arccos\left(\operatorname{clip}\left(\cos(\theta), -1.0, 1.0\right)\right) \times \frac{180^\circ}{\pi}$$

### 3.2. Camera-Distance Invariant Normalization
For thumb-to-fingertip opposition:
$$d_{\text{norm}} = \frac{\|\text{Thumb Tip [4]} - \text{Index Tip [8]}\|}{\|\text{Wrist [0]} - \text{Middle MCP [9]}\|}$$
This normalizes physical camera depth, making measurements independent of whether the patient sits close or far from the laptop.

### 3.3. Hysteresis State Machine
- **Flexion Phase:** Angle drops below active threshold ($\theta \le 95^\circ$).
- **Extension Phase:** Angle returns above rest threshold ($\theta \ge 140^\circ$).
- **Time Gate:** Requires duration $\ge 0.4\text{s}$ to reject tremors or camera blips.
