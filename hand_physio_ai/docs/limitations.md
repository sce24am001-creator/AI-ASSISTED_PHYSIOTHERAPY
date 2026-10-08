# Technical and Clinical Limitations

> **Mandatory Disclaimer:** Camera-based estimate, not a clinical measurement. This software does not diagnose, prescribe, or provide medical-grade measurements.

---

## 1. Computer Vision & Sensor Limitations

### 1.1. Monocular 2D Camera vs. Clinical Goniometry
- **Limitation:** Standard laptop webcams capture a single 2D projection of the 3D physical world. While MediaPipe predicts normalized 3D joint coordinates, z-depth coordinates are mathematically inferred from statistical hand proportions rather than measured via true stereoscopy or time-of-flight depth sensors.
- **Clinical Implication:** Webcam measurements represent approximate kinematic estimates, not certified medical-grade goniometry. Goniometric gold standards require physical universal goniometers or specialized multi-camera motion capture laboratories.

### 1.2. Absence of Forearm Landmarks for Wrist Goniometry
- **Limitation:** Google MediaPipe HandLandmarker tracks 21 keypoints spanning the carpal base to the distal phalanges. It **does not track the forearm (radius or ulna bones)**.
- **Clinical Implication:** True anatomical wrist flexion/extension measures the angle between the third metacarpal and the long axis of the forearm. In this system, wrist tilt is computed from the hand vector ($\text{Wrist} \to \text{Middle MCP}$) relative to the camera frame axis. This is labeled explicitly in the code, database, and user interface as an **APPROXIMATION**.

### 1.3. Sensitivity to Lighting, Contrast, and Occlusion
- **Limitation:** Landmark detection confidence degrades under low-light conditions, strong backlighting, or when fingers occlude one another during deep clenches.
- **Safety Mitigation (Hard Rule #5):** The system enforces a strict confidence floor ($0.60$). When lighting drops or a hand is partially obscured, the system pauses rep counter transitions and displays:
  > *"Movement could not be measured reliably. Adjust camera position or lighting."*

---

## 2. Infrastructure & Streaming Limitations

### 2.1. Local MJPEG Webcam Streaming
- **Limitation:** In this university demonstration, live video is captured on the server host machine using OpenCV (`cv2.VideoCapture(0, cv2.CAP_DSHOW)`) and streamed via standard multipart MJPEG HTTP chunks (`/api/video_feed/<id>`).
- **Production Context:** This architecture is designed for local demonstration on the student's laptop. In an enterprise telehealth deployment where the patient and doctor are on separate physical computers, local OpenCV capture would be replaced with browser-native WebRTC peer-to-peer media streams.

---

## 3. Clinical & Regulatory Boundaries

### 3.1. Zero Autonomous Diagnosis or Prescription
- **Boundary:** The software never claims to diagnose pathology, prescribe new exercises, alter dosages, or predict recovery timelines.
- **Human-in-the-Loop:** All exercise targets, sets, reps, and precautions are authored, reviewed, and approved exclusively by licensed physical therapists.

### 3.2. Prohibition of Fabricated Scores
- **Boundary (Hard Rule #7):** The platform never outputs a "recovery percentage" or proprietary composite score. Only verifiable empirical data (session dates, completed reps, mean/max/min Range of Motion, and duration) are stored and graphed.
