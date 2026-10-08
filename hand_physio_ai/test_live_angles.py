"""
Interactive Live Finger Joint Angle Diagnostic Script.
Tracks live hand landmarks and prints real-time angles for index, middle, ring, pinky, and thumb.
"""

import sys
import os
import time

# Ensure project root in path
sys.path.insert(0, os.path.abspath(os.path.dirname(__file__)))

from src.pose.camera import CameraManager
from src.pose.detector import HandDetector
from src.features.angles import get_finger_pip_angles, get_average_finger_flexion


def run_angle_diagnostic(num_frames: int = 25):
    print("=" * 65)
    print("AI-Assisted Physiotherapy Platform: Live Finger Angle Diagnostic")
    print("Try opening and closing your hand in front of the camera.")
    print("Open hand = ~160-180 deg | Closed fist = ~50-80 deg")
    print("=" * 65)

    cam = CameraManager(camera_index=0, warmup_seconds=1.0, max_consecutive_failures=30)
    detector = HandDetector(min_confidence=0.6)

    if not cam.open():
        print("[ERROR] Could not open camera device 0.")
        return False

    print("\n[INFO] Camera active. Measuring joint angles...\n")
    try:
        for i in range(1, num_frames + 1):
            success, frame = cam.read_frame()
            if not success or frame is None:
                continue

            detection = detector.detect(frame)
            if detection.is_tracked and detection.landmarks is not None:
                pip_angles = get_finger_pip_angles(detection.landmarks)
                avg_flex = get_average_finger_flexion(detection.landmarks)
                
                print(
                    f"Frame {i:02d} [{detection.handedness} Hand] -> "
                    f"Avg: {avg_flex:5.1f} deg | "
                    f"Idx: {pip_angles['index']:5.1f} | "
                    f"Mid: {pip_angles['middle']:5.1f} | "
                    f"Rng: {pip_angles['ring']:5.1f} | "
                    f"Pnk: {pip_angles['pinky']:5.1f}"
                )
            else:
                print(f"Frame {i:02d} -> [UNTRACKED] {detection.reliability_message}")

            time.sleep(0.04)

    finally:
        cam.release()
        detector.close()
        print("\n[OK] Released camera and detector cleanly.")

    print("=" * 65)
    print("Angle diagnostic complete.")
    print("=" * 65)
    return True


if __name__ == "__main__":
    run_angle_diagnostic()
