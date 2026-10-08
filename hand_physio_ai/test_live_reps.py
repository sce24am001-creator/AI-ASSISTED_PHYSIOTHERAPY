"""
Live Repetition Counter Diagnostic.
Tracks live hand landmarks, smooths angles with MovingAverageFilter,
and counts fist open/close repetitions using RepCounter.
"""

import sys
import os
import time

# Ensure project root in sys.path
sys.path.insert(0, os.path.abspath(os.path.dirname(__file__)))

from src.pose.camera import CameraManager
from src.pose.detector import HandDetector
from src.features.angles import get_average_finger_flexion
from src.analysis.rep_counter import RepCounter


def run_live_rep_counter(num_frames: int = 50):
    print("=" * 65)
    print("AI-Assisted Physiotherapy Platform: Live Fist Rep Counter")
    print("Instructions:")
    print("  1. Hold your hand open in front of the camera (rest: >140 deg).")
    print("  2. Close your hand into a firm fist (target: <90 deg).")
    print("  3. Open your hand again to complete 1 repetition.")
    print("=" * 65)

    cam = CameraManager(camera_index=0, warmup_seconds=1.0, max_consecutive_failures=30)
    detector = HandDetector(min_confidence=0.6)
    counter = RepCounter(
        rest_threshold=140.0,
        active_threshold=95.0,
        direction="decreasing",
        min_duration_seconds=0.4,
        filter_window=5
    )

    if not cam.open():
        print("[ERROR] Could not open camera device 0.")
        return False

    print("\n[INFO] Camera active. Start exercise now!\n")
    try:
        prev_reps = 0
        for i in range(1, num_frames + 1):
            success, frame = cam.read_frame()
            if not success or frame is None:
                continue

            detection = detector.detect(frame)
            if detection.is_tracked and detection.landmarks is not None:
                raw_angle = get_average_finger_flexion(detection.landmarks)
                status = counter.update(raw_angle, is_reliable=True)

                if status["rep_count"] > prev_reps:
                    last_rep = status["last_rep"]
                    print(
                        f"\n>>> [REP COMPLETED #{status['rep_count']}] "
                        f"ROM: {last_rep['rom']} deg | "
                        f"Min: {last_rep['min_value']} deg | "
                        f"Duration: {last_rep['duration_seconds']}s <<<\n"
                    )
                    prev_reps = status["rep_count"]
                else:
                    state_lbl = status["state"]
                    smooth_val = status["smoothed_value"]
                    print(
                        f"Frame {i:02d} -> [{state_lbl:7s}] "
                        f"Angle: {smooth_val:5.1f} deg | "
                        f"Total Reps: {status['rep_count']}",
                        end="\r",
                        flush=True
                    )
            else:
                counter.update(0.0, is_reliable=False)
                print(f"Frame {i:02d} -> [UNTRACKED] {detection.reliability_message}     ", end="\r", flush=True)

            time.sleep(0.04)

    finally:
        cam.release()
        detector.close()
        print("\n\n[OK] Released camera and detector cleanly.")

    print("=" * 65)
    print(f"Session Finished. Total Reps Counted: {counter.rep_count}")
    for rep in counter.completed_reps:
        print(f"  Rep #{rep.rep_number}: ROM {rep.rom:.1f} deg ({rep.duration_seconds:.2f}s)")
    print("=" * 65)
    return True


if __name__ == "__main__":
    run_live_rep_counter()
