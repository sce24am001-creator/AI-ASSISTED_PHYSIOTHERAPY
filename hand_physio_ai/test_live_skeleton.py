"""
Live Skeleton Detection & Verification Script.
Connects CameraManager to HandDetector and draw_skeleton.
Captures 25 live frames, prints detection confidence and reliability state,
and saves an annotated sample frame for visual inspection.
"""

import sys
import os
import time
import cv2

# Ensure project root in sys.path
sys.path.insert(0, os.path.abspath(os.path.dirname(__file__)))

from src.pose.camera import CameraManager
from src.pose.detector import HandDetector
from src.pose.drawing import draw_skeleton


def run_live_test(num_frames: int = 25, save_demo_image: bool = True):
    print("=" * 65)
    print("AI-Assisted Physiotherapy Platform: Live Hand Skeleton Test")
    print("Holding hand in front of camera will track 21 landmarks.")
    print("If hand is absent or low confidence, warning banner is displayed.")
    print("=" * 65)

    cam = CameraManager(camera_index=0, warmup_seconds=1.0, max_consecutive_failures=30)
    detector = HandDetector(min_confidence=0.6)

    if not cam.open():
        print("[ERROR] Could not open camera device 0.")
        return False

    print("\n[INFO] Camera active. Processing live frames...")
    tracked_count = 0
    annotated_sample = None

    try:
        for i in range(1, num_frames + 1):
            success, frame = cam.read_frame()
            if not success or frame is None:
                print(f"  Frame {i:02d}: Camera read retry blip")
                continue

            t0 = time.time()
            detection = detector.detect(frame)
            latency_ms = (time.time() - t0) * 1000

            annotated = draw_skeleton(frame, detection)
            annotated_sample = annotated

            if detection.is_tracked:
                tracked_count += 1
                print(
                    f"  Frame {i:02d}: TRACKED [{detection.handedness} Hand, "
                    f"Conf: {detection.confidence:.1%}, Latency: {latency_ms:.1f}ms]"
                )
            else:
                reason = "No hand visible" if detection.all_hands_count == 0 else "Low confidence"
                print(
                    f"  Frame {i:02d}: UNTRACKED ({reason}) -> Banner: "
                    f"'{detection.reliability_message}'"
                )

            time.sleep(0.04)  # ~25 FPS

        if save_demo_image and annotated_sample is not None:
            demo_path = os.path.join(os.path.dirname(__file__), "live_tracking_sample.jpg")
            cv2.imwrite(demo_path, annotated_sample)
            print(f"\n[OK] Saved annotated live frame to: {demo_path}")

    finally:
        cam.release()
        detector.close()
        print("[OK] Released camera and detector cleanly.")

    print("\n" + "=" * 65)
    print(f"Live Test Completed: {tracked_count}/{num_frames} frames tracked reliably.")
    print("Reliability rules tested: Missing hand, confidence thresholding, disclaimer.")
    print("=" * 65)
    return True


if __name__ == "__main__":
    run_live_test()
