"""
Unit Tests for the 3 Hand Exercises and Session Range of Motion (ROM) Analysis.
Tests camera-distance normalization, kinematic feature extractors, and summary metrics.
"""

import sys
import os
import unittest
import numpy as np

# Ensure project root in sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from src.pose.detector import (
    WRIST, THUMB_TIP, INDEX_TIP,
    INDEX_MCP, INDEX_PIP, INDEX_DIP,
    MIDDLE_MCP, MIDDLE_PIP, MIDDLE_DIP,
    RING_MCP, RING_PIP, RING_DIP,
    PINKY_MCP, PINKY_PIP, PINKY_DIP
)
from src.features.distances import (
    calculate_euclidean_distance,
    get_hand_scale_reference,
    get_thumb_to_fingertip_distance
)
from src.analysis.exercises import (
    ExerciseTracker,
    calculate_wrist_tilt_approximation,
    WRIST_APPROXIMATION_NOTE,
    EXERCISE_REGISTRY
)


class TestDistanceNormalization(unittest.TestCase):
    """Test person-specific, camera-depth-invariant distance normalization."""

    def test_scale_invariance_when_hand_moves_closer_or_further(self):
        # Scenario A: Hand is far from camera (smaller pixel distances)
        hand_far = np.zeros((21, 3), dtype=np.float64)
        hand_far[WRIST] = [0.5, 0.6, 0.0]
        hand_far[MIDDLE_MCP] = [0.5, 0.5, 0.0]  # scale = 0.10
        hand_far[THUMB_TIP] = [0.45, 0.45, 0.0]
        hand_far[INDEX_TIP] = [0.50, 0.45, 0.0]  # thumb-to-index = 0.05

        norm_far = get_thumb_to_fingertip_distance(hand_far, target_finger="index", normalized=True)

        # Scenario B: Hand moves 2x closer (all pixel coordinates doubled relative to wrist)
        hand_close = np.zeros((21, 3), dtype=np.float64)
        hand_close[WRIST] = [0.5, 0.6, 0.0]
        hand_close[MIDDLE_MCP] = [0.5, 0.4, 0.0]  # scale = 0.20 (2x larger)
        hand_close[THUMB_TIP] = [0.40, 0.30, 0.0]
        hand_close[INDEX_TIP] = [0.50, 0.30, 0.0]  # thumb-to-index = 0.10 (2x larger)

        norm_close = get_thumb_to_fingertip_distance(hand_close, target_finger="index", normalized=True)

        # Invariant ratio should be identical
        self.assertAlmostEqual(norm_far, norm_close, places=4)
        self.assertAlmostEqual(norm_far, 0.5, places=4)


class TestThreeExercises(unittest.TestCase):
    """Test each of the 3 exercises individually."""

    def setUp(self):
        self.synthetic_hand = np.zeros((21, 3), dtype=np.float64)
        # Establish reference scale and knuckle MCPs
        self.synthetic_hand[WRIST] = [0.5, 0.8, 0.0]
        for mcp in [INDEX_MCP, MIDDLE_MCP, RING_MCP, PINKY_MCP]:
            self.synthetic_hand[mcp] = [0.5, 0.6, 0.0]

    def test_exercise_1_fist_flexion_tracking(self):
        tracker = ExerciseTracker("fist_flexion")
        self.assertEqual(tracker.config.metric_unit, "degrees")

        # Simulate natural video stream (10 frames open -> 12 frames clench -> 12 frames open)
        t = 0.0
        dt = 0.05

        # Phase 1: Open hand (~180 deg)
        for finger_pip in [INDEX_PIP, MIDDLE_PIP, RING_PIP, PINKY_PIP]:
            self.synthetic_hand[finger_pip] = [0.5, 0.4, 0.0]
        for finger_dip in [INDEX_DIP, MIDDLE_DIP, RING_DIP, PINKY_DIP]:
            self.synthetic_hand[finger_dip] = [0.5, 0.2, 0.0]

        for _ in range(8):
            t += dt
            tracker.update(self.synthetic_hand, timestamp=t)

        # Phase 2: Clench fist (bend DIP to 90 deg relative to PIP)
        for finger_dip in [INDEX_DIP, MIDDLE_DIP, RING_DIP, PINKY_DIP]:
            self.synthetic_hand[finger_dip] = [0.7, 0.4, 0.0]

        for _ in range(12):
            t += dt
            tracker.update(self.synthetic_hand, timestamp=t)

        # Phase 3: Open hand again
        for finger_dip in [INDEX_DIP, MIDDLE_DIP, RING_DIP, PINKY_DIP]:
            self.synthetic_hand[finger_dip] = [0.5, 0.2, 0.0]

        status = None
        for _ in range(12):
            t += dt
            status = tracker.update(self.synthetic_hand, timestamp=t)

        self.assertIsNotNone(status)
        self.assertEqual(status["rep_count"], 1)

    def test_exercise_2_thumb_opposition_tracking(self):
        tracker = ExerciseTracker("thumb_opposition")
        self.assertEqual(tracker.config.metric_unit, "normalized ratio")

        t = 0.0
        dt = 0.05

        # Phase 1: Open hand (tips apart)
        self.synthetic_hand[THUMB_TIP] = [0.2, 0.4, 0.0]
        self.synthetic_hand[INDEX_TIP] = [0.6, 0.4, 0.0]
        for _ in range(8):
            t += dt
            tracker.update(self.synthetic_hand, timestamp=t)

        # Phase 2: Touch fingertips together
        self.synthetic_hand[THUMB_TIP] = [0.5, 0.4, 0.0]
        self.synthetic_hand[INDEX_TIP] = [0.5, 0.4, 0.0]
        for _ in range(12):
            t += dt
            tracker.update(self.synthetic_hand, timestamp=t)

        # Phase 3: Separate tips again
        self.synthetic_hand[THUMB_TIP] = [0.2, 0.4, 0.0]
        self.synthetic_hand[INDEX_TIP] = [0.6, 0.4, 0.0]
        status = None
        for _ in range(12):
            t += dt
            status = tracker.update(self.synthetic_hand, timestamp=t)

        self.assertIsNotNone(status)
        self.assertEqual(status["rep_count"], 1)

    def test_exercise_3_wrist_tilt_approximation_and_disclaimer(self):
        tracker = ExerciseTracker("wrist_tilt")
        self.assertIn("APPROXIMATION", tracker.config.clinical_note)
        self.assertIn("forearm", tracker.config.clinical_note)

        # Neutral vertical hand
        self.synthetic_hand[WRIST] = [0.5, 0.8, 0.0]
        self.synthetic_hand[MIDDLE_MCP] = [0.5, 0.4, 0.0]
        tilt_neutral = calculate_wrist_tilt_approximation(self.synthetic_hand)
        self.assertAlmostEqual(tilt_neutral, 0.0, places=1)

        # Tilted hand (45 degrees)
        self.synthetic_hand[MIDDLE_MCP] = [0.9, 0.4, 0.0]
        tilt_tilted = calculate_wrist_tilt_approximation(self.synthetic_hand)
        self.assertAlmostEqual(tilt_tilted, 45.0, places=1)


class TestSessionROMSummary(unittest.TestCase):
    """Test session-level ROM aggregation without unverified scores."""

    def test_session_summary_aggregates_metrics_honestly(self):
        tracker = ExerciseTracker("fist_flexion")
        # Empty session check
        empty_summary = tracker.get_session_summary()
        self.assertEqual(empty_summary["reps_completed"], 0)
        self.assertEqual(empty_summary["mean_rom"], 0.0)

        # Check Hard Rule #7: No invented recovery percentage
        self.assertNotIn("recovery_percentage", empty_summary)
        self.assertNotIn("recovery_score", empty_summary)


if __name__ == "__main__":
    unittest.main()
