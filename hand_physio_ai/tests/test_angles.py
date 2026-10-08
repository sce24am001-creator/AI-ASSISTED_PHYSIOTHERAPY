"""
Unit Tests for Angle Calculation and Finger Joint Articulations.
Tests mathematical boundary conditions, geometric angles, and landmark triplets.
"""

import sys
import os
import unittest
import numpy as np

# Ensure project root in sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from src.features.angles import (
    calculate_angle,
    get_finger_joint_angle,
    get_finger_pip_angles,
    get_finger_composite_angles,
    get_average_finger_flexion,
    FINGER_PIP_TRIPLETS
)
from src.pose.detector import INDEX_MCP, INDEX_PIP, INDEX_DIP


class TestCalculateAngle(unittest.TestCase):
    """Test calculate_angle function with exact geometric configurations."""

    def test_right_angle_90_degrees(self):
        a = [0.0, 1.0]
        b = [0.0, 0.0]
        c = [1.0, 0.0]
        angle = calculate_angle(a, b, c)
        self.assertAlmostEqual(angle, 90.0, places=4)

    def test_straight_line_180_degrees(self):
        a = [-1.0, 0.0]
        b = [0.0, 0.0]
        c = [1.0, 0.0]
        angle = calculate_angle(a, b, c)
        self.assertAlmostEqual(angle, 180.0, places=4)

    def test_acute_angle_45_degrees(self):
        a = [1.0, 1.0]
        b = [0.0, 0.0]
        c = [1.0, 0.0]
        angle = calculate_angle(a, b, c)
        self.assertAlmostEqual(angle, 45.0, places=4)

    def test_obtuse_angle_135_degrees(self):
        a = [-1.0, 1.0]
        b = [0.0, 0.0]
        c = [1.0, 0.0]
        angle = calculate_angle(a, b, c)
        self.assertAlmostEqual(angle, 135.0, places=4)

    def test_folded_back_0_degrees(self):
        a = [1.0, 0.0]
        b = [0.0, 0.0]
        c = [1.0, 0.0]
        angle = calculate_angle(a, b, c)
        self.assertAlmostEqual(angle, 0.0, places=4)

    def test_3d_coordinates_right_angle(self):
        a = [0.0, 0.0, 1.0]
        b = [0.0, 0.0, 0.0]
        c = [1.0, 0.0, 0.0]
        angle = calculate_angle(a, b, c)
        self.assertAlmostEqual(angle, 90.0, places=4)

    def test_degenerate_zero_length_vector_returns_zero_safely(self):
        a = [0.0, 0.0]
        b = [0.0, 0.0]
        c = [1.0, 0.0]
        angle = calculate_angle(a, b, c)
        self.assertEqual(angle, 0.0)

        # Both vectors zero
        self.assertEqual(calculate_angle([0, 0], [0, 0], [0, 0]), 0.0)

    def test_clipping_bounds_prevent_domain_errors(self):
        # Slightly perturbation that could exceed 1.0 due to floating point error
        a = [1.0000000000000002, 0.0]
        b = [0.0, 0.0]
        c = [1.0, 0.0]
        angle = calculate_angle(a, b, c)
        self.assertAlmostEqual(angle, 0.0, places=4)


class TestFingerAngleFunctions(unittest.TestCase):
    """Test finger landmark angle extraction with synthetic hand models."""

    def setUp(self):
        # Create a synthetic 21-landmark array
        self.synthetic_hand = np.zeros((21, 3), dtype=np.float64)

        # Set extended index finger: MCP, PIP, DIP in a straight vertical line
        self.synthetic_hand[INDEX_MCP] = [0.5, 0.6, 0.0]
        self.synthetic_hand[INDEX_PIP] = [0.5, 0.4, 0.0]
        self.synthetic_hand[INDEX_DIP] = [0.5, 0.2, 0.0]

    def test_extended_index_finger_is_180_degrees(self):
        triplet = (INDEX_MCP, INDEX_PIP, INDEX_DIP)
        angle = get_finger_joint_angle(self.synthetic_hand, triplet)
        self.assertAlmostEqual(angle, 180.0, places=3)

    def test_bent_index_finger_is_90_degrees(self):
        # Bend DIP horizontally relative to PIP
        self.synthetic_hand[INDEX_DIP] = [0.7, 0.4, 0.0]
        triplet = (INDEX_MCP, INDEX_PIP, INDEX_DIP)
        angle = get_finger_joint_angle(self.synthetic_hand, triplet)
        self.assertAlmostEqual(angle, 90.0, places=3)

    def test_average_finger_flexion(self):
        # Set all 4 fingers extended (180 degrees)
        for finger_name, (mcp, pip, dip) in FINGER_PIP_TRIPLETS.items():
            if finger_name != "thumb":
                self.synthetic_hand[mcp] = [0.5, 0.6, 0.0]
                self.synthetic_hand[pip] = [0.5, 0.4, 0.0]
                self.synthetic_hand[dip] = [0.5, 0.2, 0.0]

        avg_flexion = get_average_finger_flexion(self.synthetic_hand, include_thumb=False)
        self.assertAlmostEqual(avg_flexion, 180.0, places=3)

    def test_empty_or_small_landmark_array_handling(self):
        self.assertEqual(get_average_finger_flexion(None), 0.0)
        self.assertEqual(get_average_finger_flexion(np.zeros((5, 3))), 0.0)


if __name__ == "__main__":
    unittest.main()
