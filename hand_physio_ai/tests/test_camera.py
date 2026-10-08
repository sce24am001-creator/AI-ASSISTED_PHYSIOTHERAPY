"""
Tests for CameraManager and Webcam Capture Lifecycle.
Includes both unit tests and hardware verification tests.
"""

import sys
import os
import unittest
from unittest.mock import MagicMock, patch

# Ensure src is in python path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from src.pose.camera import CameraManager
import numpy as np


class TestCameraManagerUnit(unittest.TestCase):
    """Unit tests for CameraManager logic without requiring a physical camera."""

    def test_initialization(self):
        cam = CameraManager(camera_index=0, warmup_seconds=0.5, max_consecutive_failures=30)
        self.assertEqual(cam.camera_index, 0)
        self.assertEqual(cam.warmup_seconds, 0.5)
        self.assertEqual(cam.max_consecutive_failures, 30)
        self.assertFalse(cam.is_opened)
        self.assertIsNone(cam.cap)

    def test_consecutive_failures_stops_after_limit(self):
        cam = CameraManager(camera_index=0, warmup_seconds=0.0, max_consecutive_failures=5)
        
        # Mock VideoCapture to simulate repeated read failures
        mock_cap = MagicMock()
        mock_cap.isOpened.return_value = True
        mock_cap.read.return_value = (False, None)
        cam.cap = mock_cap
        cam.is_opened = True

        for i in range(4):
            success, frame = cam.read_frame()
            self.assertFalse(success)
            self.assertIsNone(frame)
            self.assertEqual(cam.consecutive_failures, i + 1)

        # 5th failure should trigger the limit
        success, frame = cam.read_frame()
        self.assertFalse(success)
        self.assertIsNone(frame)
        self.assertEqual(cam.consecutive_failures, 5)

    def test_successful_read_resets_failures(self):
        cam = CameraManager(camera_index=0, warmup_seconds=0.0, max_consecutive_failures=10)
        cam.is_opened = True
        mock_cap = MagicMock()
        mock_cap.isOpened.return_value = True
        cam.cap = mock_cap

        # First simulate 2 failures
        mock_cap.read.return_value = (False, None)
        cam.read_frame()
        cam.read_frame()
        self.assertEqual(cam.consecutive_failures, 2)

        # Then simulate 1 success
        dummy_frame = np.zeros((480, 640, 3), dtype=np.uint8)
        mock_cap.read.return_value = (True, dummy_frame)
        success, frame = cam.read_frame()
        self.assertTrue(success)
        self.assertIsNotNone(frame)
        self.assertEqual(cam.consecutive_failures, 0)


class TestCameraHardwareLive(unittest.TestCase):
    """Live hardware test verifying real webcam read on Windows."""

    def test_live_webcam_capture(self):
        with CameraManager(camera_index=0, warmup_seconds=1.0, max_consecutive_failures=30) as cam:
            self.assertTrue(cam.is_opened, "Webcam could not be opened with CAP_DSHOW")
            
            successful_frames = 0
            for _ in range(5):
                success, frame = cam.read_frame()
                if success and frame is not None:
                    successful_frames += 1
                    self.assertEqual(len(frame.shape), 3, "Frame must have 3 dimensions (H, W, C)")
                    self.assertGreater(frame.shape[0], 0)
                    self.assertGreater(frame.shape[1], 0)
            
            self.assertGreaterEqual(successful_frames, 1, "Should capture at least 1 valid frame")
        
        self.assertFalse(cam.is_opened, "Camera should be released cleanly after exiting context")


if __name__ == "__main__":
    unittest.main()
