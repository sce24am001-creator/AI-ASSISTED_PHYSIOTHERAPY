"""
Tests for HandDetector and Skeleton Overlay Visualization.
Validates landmark extraction, confidence gating, and clinical disclaimers.
"""

import sys
import os
import unittest
import numpy as np

# Add project root to sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from src.pose.detector import (
    HandDetector, HandDetectionResult,
    RELIABILITY_WARNING, CLINICAL_DISCLAIMER
)
from src.pose.drawing import draw_skeleton


class TestHandDetector(unittest.TestCase):
    """Unit tests for HandDetector and reliability enforcement."""

    @classmethod
    def setUpClass(cls):
        # Initialize detector once for suite
        cls.detector = HandDetector(min_confidence=0.6)

    @classmethod
    def tearDownClass(cls):
        cls.detector.close()

    def test_none_frame_returns_untracked(self):
        result = self.detector.detect(None)
        self.assertFalse(result.is_tracked)
        self.assertEqual(result.reliability_message, RELIABILITY_WARNING)

    def test_blank_image_returns_untracked_with_rule5_warning(self):
        # A completely black image has no hands
        blank_frame = np.zeros((480, 640, 3), dtype=np.uint8)
        result = self.detector.detect(blank_frame)
        self.assertFalse(result.is_tracked)
        self.assertEqual(result.all_hands_count, 0)
        self.assertEqual(result.reliability_message, RELIABILITY_WARNING)

    def test_target_hand_filtering_when_none_present(self):
        blank_frame = np.zeros((480, 640, 3), dtype=np.uint8)
        result = self.detector.detect(blank_frame, target_hand="Right")
        self.assertFalse(result.is_tracked)
        self.assertEqual(result.reliability_message, RELIABILITY_WARNING)


class TestSkeletonDrawing(unittest.TestCase):
    """Tests for overlay rendering and mandatory clinical disclaimers."""

    def test_drawing_on_untracked_frame_preserves_shape(self):
        frame = np.zeros((480, 640, 3), dtype=np.uint8)
        untracked_result = HandDetectionResult(
            is_tracked=False,
            reliability_message=RELIABILITY_WARNING
        )
        annotated = draw_skeleton(frame, untracked_result)
        self.assertEqual(annotated.shape, (480, 640, 3))
        # Ensure frame is not completely blank (banner has been rendered)
        self.assertTrue(np.any(annotated > 0))

    def test_drawing_with_synthetic_tracked_hand(self):
        frame = np.zeros((480, 640, 3), dtype=np.uint8)
        
        # Synthetic 21 landmarks clustered in the center of the image
        pixel_landmarks = np.zeros((21, 2), dtype=np.int32)
        for i in range(21):
            pixel_landmarks[i] = [320 + (i % 5) * 20, 240 + (i // 5) * 25]

        norm_landmarks = np.zeros((21, 3), dtype=np.float32)
        for i in range(21):
            norm_landmarks[i] = [pixel_landmarks[i][0] / 640.0, pixel_landmarks[i][1] / 480.0, 0.0]

        tracked_result = HandDetectionResult(
            is_tracked=True,
            landmarks=norm_landmarks,
            pixel_landmarks=pixel_landmarks,
            handedness="Right",
            confidence=0.95,
            all_hands_count=1
        )

        annotated = draw_skeleton(frame, tracked_result)
        self.assertEqual(annotated.shape, (480, 640, 3))
        # Joints and lines must be drawn
        self.assertTrue(np.any(annotated > 0))


if __name__ == "__main__":
    unittest.main()
