"""
Unit Tests for Smoothing Filter and Rep Counter State Machine.
Tests state transitions, hysteresis thresholds, time gating, and synthetic waveforms.
No physical webcam or hardware required.
"""

import sys
import os
import unittest
import numpy as np

# Ensure project root in sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from src.features.smoothing import MovingAverageFilter
from src.analysis.rep_counter import RepCounter, RepState


class TestMovingAverageFilter(unittest.TestCase):
    """Test MovingAverageFilter smoothing behavior."""

    def test_constant_input_yields_same_average(self):
        f = MovingAverageFilter(window_size=5)
        for _ in range(5):
            res = f.update(100.0)
        self.assertEqual(res, 100.0)

    def test_dampens_sudden_spike(self):
        f = MovingAverageFilter(window_size=5)
        for _ in range(4):
            f.update(100.0)
        # Spike on 5th frame
        smoothed = f.update(150.0)
        # (100 + 100 + 100 + 100 + 150) / 5 = 110.0
        self.assertEqual(smoothed, 110.0)

    def test_reset_clears_buffer(self):
        f = MovingAverageFilter(window_size=3)
        f.update(50.0)
        f.reset()
        self.assertIsNone(f.current)
        self.assertEqual(f.update(80.0), 80.0)


class TestRepCounterStateMachine(unittest.TestCase):
    """Test RepCounter state machine with synthetic angle time series."""

    def test_three_clean_reps_are_counted_accurately(self):
        counter = RepCounter(
            rest_threshold=150.0,
            active_threshold=90.0,
            direction="decreasing",
            min_duration_seconds=0.5,
            filter_window=1  # window 1 for exact test tracking
        )

        t = 0.0
        dt = 0.05  # 20 Hz frame rate

        # Perform 3 reps: 160 -> 60 -> 160, taking ~1.0 second each
        for rep in range(3):
            # Phase 1: contract from 160 down to 60 deg (0.5s)
            for angle in np.linspace(160.0, 60.0, 10):
                t += dt
                counter.update(angle, timestamp=t, is_reliable=True)

            # Phase 2: extend from 60 back up to 160 deg (0.5s)
            for angle in np.linspace(60.0, 160.0, 10):
                t += dt
                counter.update(angle, timestamp=t, is_reliable=True)

        self.assertEqual(counter.rep_count, 3)
        self.assertEqual(len(counter.completed_reps), 3)

        # Verify ROM and per-rep measurements
        first_rep = counter.completed_reps[0]
        self.assertEqual(first_rep.rep_number, 1)
        self.assertAlmostEqual(first_rep.min_value, 60.0, places=1)
        self.assertAlmostEqual(first_rep.max_value, 160.0, places=1)
        self.assertAlmostEqual(first_rep.rom, 100.0, places=1)
        self.assertGreaterEqual(first_rep.duration_seconds, 0.5)

    def test_incomplete_rep_does_not_count(self):
        counter = RepCounter(
            rest_threshold=150.0,
            active_threshold=90.0,
            direction="decreasing",
            min_duration_seconds=0.5,
            filter_window=1
        )

        t = 0.0
        dt = 0.05

        # Move from 160 down to 110 (never reaches active threshold 90), then back to 160
        for angle in np.linspace(160.0, 110.0, 10):
            t += dt
            counter.update(angle, timestamp=t, is_reliable=True)

        for angle in np.linspace(110.0, 160.0, 10):
            t += dt
            counter.update(angle, timestamp=t, is_reliable=True)

        self.assertEqual(counter.rep_count, 0)
        self.assertEqual(len(counter.completed_reps), 0)
        self.assertEqual(counter.state, RepState.RESTING)

    def test_rapid_twitch_violating_min_duration_is_rejected(self):
        counter = RepCounter(
            rest_threshold=150.0,
            active_threshold=90.0,
            direction="decreasing",
            min_duration_seconds=0.6,
            filter_window=1
        )

        t = 0.0
        # Twitch down to 50 and back in 0.05s
        counter.update(160.0, timestamp=t, is_reliable=True)
        t += 0.02
        counter.update(50.0, timestamp=t, is_reliable=True)
        t += 0.02
        counter.update(160.0, timestamp=t, is_reliable=True)

        # Rejected because duration was 0.04s < 0.6s
        self.assertEqual(counter.rep_count, 0)

    def test_unreliable_tracking_freezes_state_transitions(self):
        counter = RepCounter(
            rest_threshold=150.0,
            active_threshold=90.0,
            direction="decreasing",
            filter_window=1
        )

        # Hand lost in the middle of flexion
        counter.update(160.0, timestamp=0.0, is_reliable=True)
        counter.update(50.0, timestamp=0.5, is_reliable=False)  # Unreliable frame
        self.assertEqual(counter.state, RepState.RESTING)
        self.assertEqual(counter.rep_count, 0)

    def test_increasing_direction_counter(self):
        # Rep counter where value goes up (e.g. wrist extension: 10 -> 80 -> 10)
        counter = RepCounter(
            rest_threshold=20.0,
            active_threshold=70.0,
            direction="increasing",
            min_duration_seconds=0.4,
            filter_window=1
        )

        t = 0.0
        dt = 0.05

        # Perform 1 rep
        for val in np.linspace(20.0, 80.0, 10):
            t += dt
            counter.update(val, timestamp=t, is_reliable=True)

        for val in np.linspace(80.0, 20.0, 10):
            t += dt
            counter.update(val, timestamp=t, is_reliable=True)

        self.assertEqual(counter.rep_count, 1)
        self.assertAlmostEqual(counter.completed_reps[0].rom, 60.0, places=1)


if __name__ == "__main__":
    unittest.main()
