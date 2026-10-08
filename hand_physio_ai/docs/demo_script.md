# University Presentation & Examination Demo Script

A step-by-step walkthrough script for presenting this platform to university examiners and professors.

---

## 1. Introduction (1 Minute)
> *"Good morning professors. My project is an **AI-Assisted Physiotherapy Platform for Hand and Wrist Rehabilitation**.*
> 
> *The clinical challenge: Patients recovering from hand fractures or tendon surgery often do home exercises incorrectly and abandon their routines without feedback. Meanwhile, physiotherapists have no objective data on whether the patient's Range of Motion is improving.*
> 
> *Our solution connects the clinician and patient in a closed 4-step loop:*
> *1. The physiotherapist prescribes personalized exercises.*
> *2. The patient performs them in front of a standard laptop webcam.*
> *3. The computer-vision pipeline measures joint kinematics in real time.*
> *4. The physiotherapist reviews objective Range of Motion trends to adjust care."*

---

## 2. Live Clinician Demonstration (2 Minutes)
1. **Launch the application:**
   ```powershell
   python run.py
   ```
2. Open `http://127.0.0.1:5000` in the browser.
3. Click **🩺 Clinician (Dr. Sarah)**.
4. **Key points to highlight to the examiner:**
   - Point out the **Patient Directory** on the left showing **John Doe**.
   - Point out the **Rehabilitation Telemetry Trends** on the right:
     - **ROM Trend Line Graph:** Shows John's Range of Motion across past workout sessions.
     - **Adherence Bar Chart:** Displays completed repetitions per session.
   - Mention **Clinical Safety (Hard Rule #1):** *"Notice that the AI never diagnoses or dictates treatments. All exercise targets and precautions are configured by the licensed physiotherapist."*
   - Mention **Hard Rule #7:** *"We do not invent arbitrary 'recovery percentages.' The charts display only empirical, measured joint degrees."*

---

## 3. Live Patient Portal & Anatomical Guidance (2 Minutes)
1. Log out and click **👤 Patient (John)**.
2. **Key points to highlight:**
   - **Today's Therapy:** Shows the active prescription (*Fist Open / Close, 3 Sets $\times$ 10 Reps, Right Hand*).
   - **Interactive Anatomical Hand Diagram (SVG):**
     - Show the custom vector hand highlighting the knuckles and fingers.
     - Highlight the clinician-approved text: *Target Region, Target Joints, Target Muscles, Clinical Purpose*.
     - Point out the label: *"✓ Approved by Clinician"*.

---

## 4. Live Computer-Vision Workout Session (2 Minutes)
1. Click **"Start Camera Exercise Session →"**.
2. Hold your hand in front of the webcam.
3. **Key points to highlight:**
   - **Live 21-Joint Skeletal Overlay:** Show the smooth tracking of finger joints and fingertips.
   - **Safety Gating (Hard Rule #5):** Move your hand out of the camera frame. Show that the system immediately displays:
     > *"Movement could not be measured reliably. Adjust camera position or lighting."*
     Explain that the system will **never award phantom repetitions** during tracking drops.
   - **Rep Counter Biofeedback (Stage 4 & 5):**
     - Open your hand flat: HUD shows angle $\approx 170^\circ$, State: `RESTING`.
     - Clench a firm fist: Angle drops to $\approx 60^\circ$, State switches to `IN_REP`.
     - Open your hand again: Rep count increments to `1`, HUD progress bar animates.
   - Click **"✓ Finish & Save Session"**:
     - The modal appears summarizing **Reps Completed**, **Mean ROM**, **Max ROM**, and **Duration**.
     - Click **"Save Session"**: It saves the derived numbers to SQLite and redirects to the dashboard.

---

## 5. Technical Rigor & Architecture Highlights (1 Minute)
- **59 Passing Automated Tests:** Mention that all components (camera lifecycle, landmark detection, angle formulas, hysteresis rep counters, database tables, and Flask routes) have 100% automated test coverage.
- **Explainable Rule-Based Kinematics:** Explain why dot-product trigonometry is used instead of black-box neural networks: it is computationally lightweight, transparent, and auditable by clinicians.
- **Privacy Compliance (Hard Rule #6):** Explicitly emphasize that **no webcam footage or photos are ever saved to disk or database**—only derived numerical angles and repetition timestamps.

---

## 6. Anticipated Examiner Questions & Answers

**Q1: Why didn't you use a deep learning model to count the repetitions?**
> *"In healthcare, black-box deep learning models can produce unpredictable hallucinations or false counts that a clinician cannot explain. By using deterministic vector dot products with a hysteresis dual-threshold state machine, every single angle and counted repetition is mathematically transparent and clinically verifiable."*

**Q2: How does the system handle patients sitting at different distances from the camera?**
> *"For exercises like thumb-to-fingertip opposition, raw pixel distance changes as you move closer or further. We solve this by normalizing the fingertip distance against the patient's own anatomical scale (the distance between their Wrist and Middle Knuckle). This creates a scale-invariant ratio that works at any camera depth."*

**Q3: Can your system measure wrist angles with the same accuracy as a doctor's goniometer?**
> *"No, and we explicitly disclose this in the UI. A true clinical wrist measurement requires measuring against the forearm bones. Because monocular MediaPipe Hand models only track hand landmarks from the wrist onward, our wrist measurement is labeled as a camera-based approximation, not medical-grade goniometry."*
