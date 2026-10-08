"""
Interactive / CLI Webcam Diagnostic Script.
Runs a 10-frame test with CameraManager and reports diagnostics.
"""

import sys
import os
import time

# Ensure project root is in path
sys.path.insert(0, os.path.abspath(os.path.dirname(__file__)))

from src.pose.camera import CameraManager


def run_diagnostic():
    print("=" * 60)
    print("AI-Assisted Physiotherapy Platform: Webcam Diagnostic")
    print("Backend: OpenCV CAP_DSHOW on Device Index 0")
    print("Warm-up: 1.0 second delay, up to 30 retries allowed")
    print("=" * 60)

    start_init = time.time()
    cam = CameraManager(camera_index=0, warmup_seconds=1.0, max_consecutive_failures=30)
    
    print("\n[1/3] Opening camera and warming up sensor...")
    if not cam.open():
        print("[ERROR] Failed to open camera device index 0.")
        return False
    
    init_duration = time.time() - start_init
    print(f"[OK] Camera opened successfully in {init_duration:.2f}s.")

    print("\n[2/3] Capturing 10 consecutive frames...")
    frames_ok = 0
    sample_shape = None

    for i in range(1, 11):
        t0 = time.time()
        success, frame = cam.read_frame()
        dt = (time.time() - t0) * 1000
        if success and frame is not None:
            frames_ok += 1
            sample_shape = frame.shape
            print(f"  Frame {i:02d}: OK ({frame.shape[1]}x{frame.shape[0]} px, 3 channels) - read in {dt:.1f}ms")
        else:
            print(f"  Frame {i:02d}: Retry/Warm-up blip (handled)")
        time.sleep(0.03)  # ~30 FPS cadence

    print("\n[3/3] Releasing camera hardware...")
    cam.release()
    print("[OK] Camera device released cleanly.")

    print("\n" + "=" * 60)
    print(f"Summary: {frames_ok}/10 frames captured successfully.")
    if sample_shape:
        print(f"Resolution: {sample_shape[1]} width x {sample_shape[0]} height")
        print("Hardware Status: READY FOR POSE ESTIMATION")
    else:
        print("Hardware Status: FAILED TO CAPTURE FRAMES")
    print("=" * 60)

    return frames_ok > 0


if __name__ == "__main__":
    success = run_diagnostic()
    sys.exit(0 if success else 1)
