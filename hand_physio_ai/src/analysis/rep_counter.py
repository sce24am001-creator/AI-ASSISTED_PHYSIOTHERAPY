"""
Hysteresis-Based Rep Counter State Machine.

Counts exercise repetitions using dual-threshold hysteresis and a minimum-duration time gate:
- Dual thresholds prevent false triggering from jitter around a single threshold.
- Time gating rejects rapid tremors or video blips.
- Records per-rep metrics: rep_number, min_angle, max_angle, ROM, and duration.
"""

from dataclasses import dataclass, field
from enum import Enum
from typing import Optional, List, Dict, Any
import time
from src.features.smoothing import MovingAverageFilter


class RepState(Enum):
    RESTING = "RESTING"
    IN_REP = "IN_REP"


@dataclass
class RepMetric:
    """Detailed clinical measurement for a single completed repetition."""
    rep_number: int
    min_value: float
    max_value: float
    rom: float
    duration_seconds: float
    start_time: float
    end_time: float

    def to_dict(self) -> Dict[str, Any]:
        return {
            "rep_number": self.rep_number,
            "min_value": round(self.min_value, 2),
            "max_value": round(self.max_value, 2),
            "rom": round(self.rom, 2),
            "duration_seconds": round(self.duration_seconds, 2),
            "start_time": self.start_time,
            "end_time": self.end_time
        }


class RepCounter:
    """
    Robust rep counter state machine with hysteresis dual-thresholds.
    """

    def __init__(
        self,
        rest_threshold: float = 150.0,
        active_threshold: float = 90.0,
        direction: str = "decreasing",
        min_duration_seconds: float = 0.5,
        filter_window: int = 5
    ):
        """
        Initialize RepCounter.

        Args:
            rest_threshold: Value indicating rest position (e.g. 150 deg for open hand).
            active_threshold: Value indicating full contraction/flexion (e.g. 90 deg for fist).
            direction: 'decreasing' (flexion drops value) or 'increasing' (flexion raises value).
            min_duration_seconds: Minimum seconds a rep must take to reject twitches/jitter.
            filter_window: Moving average window size for smoothing input stream.
        """
        self.rest_threshold = float(rest_threshold)
        self.active_threshold = float(active_threshold)
        self.direction = direction.lower()
        if self.direction not in ("decreasing", "increasing"):
            raise ValueError("direction must be 'decreasing' or 'increasing'")

        self.min_duration_seconds = float(min_duration_seconds)
        self.filter = MovingAverageFilter(window_size=filter_window)

        # State machine variables
        self.state = RepState.RESTING
        self.rep_count = 0
        self.completed_reps: List[RepMetric] = []

        # Current rep tracking
        self.current_rep_start_time: Optional[float] = None
        self.current_min: float = float("inf")
        self.current_max: float = float("-inf")
        self.last_smoothed_val: float = rest_threshold

    def reset(self) -> None:
        """Reset counter state and all collected repetitions."""
        self.filter.reset()
        self.state = RepState.RESTING
        self.rep_count = 0
        self.completed_reps.clear()
        self.current_rep_start_time = None
        self.current_min = float("inf")
        self.current_max = float("-inf")

    def update(
        self,
        raw_value: float,
        timestamp: Optional[float] = None,
        is_reliable: bool = True
    ) -> Dict[str, Any]:
        """
        Process a new measurement frame.

        Args:
            raw_value: Raw calculated angle or normalized distance.
            timestamp: Timestamp in seconds (defaults to time.time()).
            is_reliable: False if hand was lost or confidence was degraded (Hard Rule #5).

        Returns:
            Dict[str, Any]: Current rep state, count, smoothed value, and latest rep info.
        """
        now = time.time() if timestamp is None else float(timestamp)

        # If measurement is unreliable, do not advance state transitions
        if not is_reliable:
            self.filter.reset()
            return self._build_status(now)

        smoothed = self.filter.update(raw_value)
        self.last_smoothed_val = smoothed

        if self.direction == "decreasing":
            self._update_decreasing(smoothed, now)
        else:
            self._update_increasing(smoothed, now)

        return self._build_status(now)

    def _update_decreasing(self, val: float, now: float) -> None:
        """State transition logic where contraction drops value (e.g. 170 -> 60 -> 170 deg)."""
        if self.state == RepState.RESTING:
            if val <= self.active_threshold:
                # Started contraction
                self.state = RepState.IN_REP
                self.current_rep_start_time = now
                self.current_min = val
                self.current_max = self.rest_threshold
        elif self.state == RepState.IN_REP:
            self.current_min = min(self.current_min, val)
            self.current_max = max(self.current_max, val)

            # Returned to rest threshold
            if val >= self.rest_threshold:
                duration = now - (self.current_rep_start_time or now)
                if duration >= self.min_duration_seconds:
                    self.rep_count += 1
                    rep = RepMetric(
                        rep_number=self.rep_count,
                        min_value=self.current_min,
                        max_value=self.current_max,
                        rom=self.current_max - self.current_min,
                        duration_seconds=duration,
                        start_time=self.current_rep_start_time or now,
                        end_time=now
                    )
                    self.completed_reps.append(rep)
                # Return to resting regardless of whether time gate passed
                self.state = RepState.RESTING
                self.current_rep_start_time = None

    def _update_increasing(self, val: float, now: float) -> None:
        """State transition logic where contraction increases value (e.g. 10 -> 80 -> 10 deg)."""
        if self.state == RepState.RESTING:
            if val >= self.active_threshold:
                self.state = RepState.IN_REP
                self.current_rep_start_time = now
                self.current_min = self.rest_threshold
                self.current_max = val
        elif self.state == RepState.IN_REP:
            self.current_min = min(self.current_min, val)
            self.current_max = max(self.current_max, val)

            if val <= self.rest_threshold:
                duration = now - (self.current_rep_start_time or now)
                if duration >= self.min_duration_seconds:
                    self.rep_count += 1
                    rep = RepMetric(
                        rep_number=self.rep_count,
                        min_value=self.current_min,
                        max_value=self.current_max,
                        rom=self.current_max - self.current_min,
                        duration_seconds=duration,
                        start_time=self.current_rep_start_time or now,
                        end_time=now
                    )
                    self.completed_reps.append(rep)
                self.state = RepState.RESTING
                self.current_rep_start_time = None

    def _build_status(self, now: float) -> Dict[str, Any]:
        """Construct dictionary summarizing current state."""
        last_rep = self.completed_reps[-1].to_dict() if self.completed_reps else None
        return {
            "state": self.state.value,
            "rep_count": self.rep_count,
            "smoothed_value": round(self.last_smoothed_val, 2),
            "last_rep": last_rep,
            "in_rep_duration": round(now - (self.current_rep_start_time or now), 2) if self.state == RepState.IN_REP else 0.0
        }
