"""
Live Multi-Exercise Diagnostic Tool.
Allows selecting and testing any of the 3 MVP exercises on live webcam:
1. Fist Open / Close (finger flexion in degrees)
2. Thumb-to-Fingertip Touch (distance normalized by hand size)
3. Wrist Flexion / Extension (approximate hand tilt with anatomical disclaimer)
"""

import sys
import os
import time

# Ensure project root in sys.path
sys.path.insert(0, os.path.abspath(os.path.dirname(__file__)))

from src.pose.camera import CameraManager
from src.pose.detector import HandDetector
from src.analysis.exercises import ExerciseTracker, EXERCISE_REGISTRY


def run_exercise_live(exercise_code: str = "fist_flexion", num_frames: int = 50):
    config = EXERCISE_REGISTRY[exercise_code]
    print("=" * 70)
    print(f"AI-Assisted Physiotherapy Platform: Live Exercise Test")
    print(f"Active Exercise: {config.name}")
    print(f"Metric Unit: {config.metric_unit}")
    print(f"Clinical Notice: {config.clinical_note}")
    print("=" * 70)

    cam = CameraManager(camera_index=0, warmup_seconds=1.0, max_consecutive_failures=30)
    detector = HandDetector(min_confidence=0.6)
    tracker = ExerciseTracker(exercise_code)

    if not cam.open():
        print("[ERROR] Could not open camera device 0.")
        return False

    print("\n[INFO] Camera active. Performing exercise...\n")
    try:
        prev_reps = 0
        for i in range(1, num_frames + 1):
            success, frame = cam.read_frame()
            if not success or frame is None:
                continue

            detection = detector.detect(frame)
            status = tracker.update(detection.landmarks, is_reliable=detection.is_tracked)

            if status["rep_count"] > prev_reps:
                last_rep = status["last_rep"]
                print(
                    f"\n>>> [REP #{status['rep_count']} COMPLETED] "
                    f"ROM: {last_rep['rom']} {config.metric_unit} | "
                    f"Duration: {last_rep['duration_seconds']}s <<<\n"
                )
                prev_reps = status["rep_count"]
            else:
                state_lbl = status["state"]
                val = status["smoothed_value"]
                print(
                    f"Frame {i:02d} -> [{state_lbl:7s}] "
                    f"Value: {val:6.2f} {config.metric_unit} | "
                    f"Reps: {status['rep_count']}",
                    end="\r",
                    flush=True
                )

            time.sleep(0.04)

    finally:
        cam.release()
        detector.close()
        print("\n\n[OK] Released camera and detector cleanly.")

    summary = tracker.get_session_summary()
    print("=" * 70)
    print(f"Session Summary for '{config.name}':")
    print(f"  Reps Completed : {summary['reps_completed']}")
    print(f"  Mean ROM       : {summary['mean_rom']} {config.metric_unit}")
    print(f"  Max ROM        : {summary['max_rom']} {config.metric_unit}")
    print(f"  Min ROM        : {summary['min_rom']} {config.metric_unit}")
    print(f"  Mean Duration  : {summary['mean_duration']}s")
    print("=" * 70)
    return True


if __name__ == "__main__":
    choice = "fist_flexion"
    if len(sys.argv) > 1 and sys.argv[1] in EXERCISE_REGISTRY:
        choice = sys.argv[1]
    run_exercise_live(choice)
