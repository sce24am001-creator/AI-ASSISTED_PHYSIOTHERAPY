"""
Exercise Definitions and Session Range of Motion (ROM) Analysis Module.

Implements the 3 MVP Hand Exercises:
1. Fist Open/Close (Finger Flexion) -> Average joint angle across fingers in degrees.
2. Thumb-to-Fingertip Touch (Opposition) -> Normalized Euclidean distance invariant to camera distance.
3. Wrist Flexion/Extension (Side view) -> Approximate hand tilt with explicit anatomical limitation disclaimer.

Hard Rules enforced:
- Rule #1: No diagnoses or clinical claims.
- Rule #3: Display camera-based estimate disclaimer.
- Rule #4: Simple rule-based math, no neural networks for kinematics.
- Rule #7: Never output recovery percentage or unvalidated clinical scores.
"""

from dataclasses import dataclass, field
from typing import Optional, Dict, List, Any
import numpy as np

from src.pose.detector import WRIST, MIDDLE_MCP, CLINICAL_DISCLAIMER
from src.features.angles import get_average_finger_flexion
from src.features.distances import get_thumb_to_fingertip_distance
from src.analysis.rep_counter import RepCounter, RepMetric


WRIST_APPROXIMATION_NOTE = (
    "APPROXIMATION: Hand axis tilt estimate. "
    "MediaPipe hand model detects hand landmarks only and lacks forearm tracking."
)


@dataclass
class ExerciseConfig:
    """Configuration metadata and tracking thresholds for an exercise."""
    code: str
    name: str
    description: str
    metric_unit: str  # "degrees" or "normalized ratio"
    rest_threshold: float
    active_threshold: float
    direction: str    # "decreasing" or "increasing"
    min_duration: float
    filter_window: int
    clinical_note: str = CLINICAL_DISCLAIMER


EXERCISE_REGISTRY: Dict[str, ExerciseConfig] = {
    "fist_flexion": ExerciseConfig(
        code="fist_flexion",
        name="Fist Open / Close",
        description="Finger flexion and extension across PIP joints.",
        metric_unit="degrees",
        rest_threshold=140.0,
        active_threshold=95.0,
        direction="decreasing",
        min_duration=0.4,
        filter_window=5,
        clinical_note=CLINICAL_DISCLAIMER
    ),
    "thumb_opposition": ExerciseConfig(
        code="thumb_opposition",
        name="Thumb-to-Fingertip Touch",
        description="Opposition of thumb tip to index fingertip, normalized by hand size.",
        metric_unit="normalized ratio",
        rest_threshold=0.65,
        active_threshold=0.25,
        direction="decreasing",
        min_duration=0.4,
        filter_window=5,
        clinical_note=CLINICAL_DISCLAIMER
    ),
    "wrist_tilt": ExerciseConfig(
        code="wrist_tilt",
        name="Wrist Flexion / Extension (Approx)",
        description="Approximate hand tilt angle from wrist to middle knuckle from a side view.",
        metric_unit="degrees",
        rest_threshold=15.0,
        active_threshold=42.0,
        direction="increasing",
        min_duration=0.4,
        filter_window=5,
        clinical_note=f"{CLINICAL_DISCLAIMER} | {WRIST_APPROXIMATION_NOTE}"
    )
}


def calculate_wrist_tilt_approximation(landmarks: np.ndarray) -> float:
    """
    Approximate hand tilt angle (degrees) relative to the horizontal plane
    formed by the hand axis vector (Wrist [0] to Middle MCP [9]).

    Notice: MediaPipe Hand tracks only hand landmarks (wrist to fingertips),
    lacking forearm reference. This is strictly labeled an APPROXIMATION.

    Returns:
        float: Tilt angle in degrees [0.0, 90.0].
    """
    if landmarks is None or len(landmarks) < 21:
        return 0.0

    p_wrist = landmarks[WRIST]
    p_mcp = landmarks[MIDDLE_MCP]

    # Vector along hand longitudinal axis
    dx = float(p_mcp[0] - p_wrist[0])
    dy = float(p_mcp[1] - p_wrist[1])

    # Angle relative to vertical neutral axis
    angle_rad = np.arctan2(abs(dx), abs(dy) + 1e-7)
    return float(np.degrees(angle_rad))


class ExerciseTracker:
    """
    Session exercise engine managing feature extraction, rep counting,
    and session-wide Range of Motion (ROM) summarization.
    """

    def __init__(self, exercise_code: str = "fist_flexion"):
        if exercise_code not in EXERCISE_REGISTRY:
            raise ValueError(f"Unknown exercise code: {exercise_code}. Available: {list(EXERCISE_REGISTRY.keys())}")

        self.config = EXERCISE_REGISTRY[exercise_code]
        self.counter = RepCounter(
            rest_threshold=self.config.rest_threshold,
            active_threshold=self.config.active_threshold,
            direction=self.config.direction,
            min_duration_seconds=self.config.min_duration,
            filter_window=self.config.filter_window
        )
        self.last_metric_value: float = self.config.rest_threshold

    def extract_feature(self, landmarks: np.ndarray) -> float:
        """Extract the specific kinematic metric for this exercise."""
        if landmarks is None or len(landmarks) < 21:
            return self.config.rest_threshold

        if self.config.code == "fist_flexion":
            return get_average_finger_flexion(landmarks)
        elif self.config.code == "thumb_opposition":
            return get_thumb_to_fingertip_distance(landmarks, target_finger="index", normalized=True)
        elif self.config.code == "wrist_tilt":
            return calculate_wrist_tilt_approximation(landmarks)
        else:
            return 0.0

    def update(
        self,
        landmarks: Optional[np.ndarray],
        is_reliable: bool = True,
        timestamp: Optional[float] = None
    ) -> Dict[str, Any]:
        """
        Process a single video frame.

        Returns:
            Dict[str, Any]: Live telemetry (rep count, smoothed value, state, rep metrics).
        """
        if is_reliable and landmarks is not None and len(landmarks) >= 21:
            raw_metric = self.extract_feature(landmarks)
            self.last_metric_value = raw_metric
            status = self.counter.update(raw_metric, timestamp=timestamp, is_reliable=True)
        else:
            status = self.counter.update(self.last_metric_value, timestamp=timestamp, is_reliable=False)

        status["exercise_code"] = self.config.code
        status["exercise_name"] = self.config.name
        status["metric_unit"] = self.config.metric_unit
        status["clinical_note"] = self.config.clinical_note
        return status

    def get_session_summary(self) -> Dict[str, Any]:
        """
        Compute summary Range of Motion (ROM) metrics across all completed reps.
        (Hard Rule #7: strictly empirical metrics, no invented recovery scores).

        Returns:
            Dict[str, Any]: Reps completed, ROM stats (mean, max, min), rep logs.
        """
        reps = self.counter.completed_reps
        if not reps:
            return {
                "exercise_code": self.config.code,
                "reps_completed": 0,
                "mean_rom": 0.0,
                "max_rom": 0.0,
                "min_rom": 0.0,
                "mean_duration": 0.0,
                "metric_unit": self.config.metric_unit,
                "completed_reps": []
            }

        rom_values = [r.rom for r in reps]
        durations = [r.duration_seconds for r in reps]

        return {
            "exercise_code": self.config.code,
            "reps_completed": len(reps),
            "mean_rom": round(float(np.mean(rom_values)), 2),
            "max_rom": round(float(np.max(rom_values)), 2),
            "min_rom": round(float(np.min(rom_values)), 2),
            "mean_duration": round(float(np.mean(durations)), 2),
            "metric_unit": self.config.metric_unit,
            "completed_reps": [r.to_dict() for r in reps]
        }
