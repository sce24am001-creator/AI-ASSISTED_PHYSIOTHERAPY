"""
Signal Smoothing Module.

Applies a moving average filter over a sliding temporal window of joint angles
to dampen camera landmark jitter and micro-tremors before feeding into rep counters.
"""

from collections import deque
from typing import Optional, List, Union


class MovingAverageFilter:
    """
    Sliding window moving average filter.
    Handles variable buffer sizes during initialization and resets on tracking loss.
    """

    def __init__(self, window_size: int = 5):
        """
        Initialize moving average filter.

        Args:
            window_size: Number of past frames to average over (default 5).
        """
        if window_size < 1:
            raise ValueError("window_size must be at least 1")
        self.window_size = window_size
        self.buffer = deque(maxlen=window_size)

    def update(self, value: float) -> float:
        """
        Add a new sample and return the current smoothed average.

        Args:
            value: Raw incoming joint angle or metric value.

        Returns:
            float: Smoothed moving average.
        """
        self.buffer.append(float(value))
        return float(sum(self.buffer) / len(self.buffer))

    def reset(self) -> None:
        """Clear all historical buffer values (e.g. when hand tracking drops)."""
        self.buffer.clear()

    @property
    def current(self) -> Optional[float]:
        """Return latest average without adding a new sample, or None if empty."""
        if not self.buffer:
            return None
        return float(sum(self.buffer) / len(self.buffer))

    def filter_sequence(self, sequence: List[float]) -> List[float]:
        """Utility method to process an entire batch of values."""
        self.reset()
        smoothed = []
        for val in sequence:
            smoothed.append(self.update(val))
        return smoothed
