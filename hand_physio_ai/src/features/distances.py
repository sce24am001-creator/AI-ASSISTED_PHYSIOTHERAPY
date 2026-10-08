"""
Distance and Normalization Module.

Calculates Euclidean distances normalized by hand anatomical scale (Wrist to Middle MCP),
enabling camera-distance-invariant measurements for thumb-to-fingertip opposition.
"""

from typing import Union, Optional, Tuple, Dict
import numpy as np
from src.pose.detector import (
    WRIST, THUMB_TIP, INDEX_TIP, MIDDLE_TIP, RING_TIP, PINKY_TIP, MIDDLE_MCP
)


FINGERTIP_MAP: Dict[str, int] = {
    "index": INDEX_TIP,
    "middle": MIDDLE_TIP,
    "ring": RING_TIP,
    "pinky": PINKY_TIP
}


def calculate_euclidean_distance(
    p1: Union[np.ndarray, list, tuple],
    p2: Union[np.ndarray, list, tuple]
) -> float:
    """
    Calculate Euclidean distance between two points in 2D or 3D space.
    """
    v1 = np.asarray(p1, dtype=np.float64)
    v2 = np.asarray(p2, dtype=np.float64)
    dim = min(len(v1), len(v2))
    return float(np.linalg.norm(v1[:dim] - v2[:dim]))


def get_hand_scale_reference(landmarks: np.ndarray) -> float:
    """
    Compute reference anatomical scale distance: Wrist (0) to Middle-finger MCP (9).
    This serves as a person-specific, depth-invariant normalization factor.

    Returns:
        float: Scale distance, or 1.0 if invalid landmarks.
    """
    if landmarks is None or len(landmarks) < 21:
        return 1.0

    dist = calculate_euclidean_distance(landmarks[WRIST], landmarks[MIDDLE_MCP])
    return dist if dist > 1e-6 else 1.0


def get_thumb_to_fingertip_distance(
    landmarks: np.ndarray,
    target_finger: str = "index",
    normalized: bool = True
) -> float:
    """
    Measure distance between thumb tip (4) and a target fingertip.

    Args:
        landmarks: (21, 3) or (21, 2) array of coordinates.
        target_finger: 'index', 'middle', 'ring', or 'pinky'.
        normalized: If True, divides by Wrist-to-Middle MCP distance for depth invariance.

    Returns:
        float: Normalized ratio (or raw distance if normalized=False).
    """
    if landmarks is None or len(landmarks) < 21:
        return 0.0

    tip_idx = FINGERTIP_MAP.get(target_finger.lower(), INDEX_TIP)
    raw_dist = calculate_euclidean_distance(landmarks[THUMB_TIP], landmarks[tip_idx])

    if not normalized:
        return raw_dist

    scale = get_hand_scale_reference(landmarks)
    return float(raw_dist / scale)


def get_minimum_thumb_opposition_distance(
    landmarks: np.ndarray,
    normalized: bool = True
) -> Tuple[float, str]:
    """
    Find the closest fingertip to the thumb tip across all 4 fingers.

    Returns:
        Tuple[float, str]: (minimum distance, name of closest finger)
    """
    if landmarks is None or len(landmarks) < 21:
        return 0.0, "unknown"

    min_dist = float("inf")
    closest_finger = "index"

    for finger, idx in FINGERTIP_MAP.items():
        dist = calculate_euclidean_distance(landmarks[THUMB_TIP], landmarks[idx])
        if dist < min_dist:
            min_dist = dist
            closest_finger = finger

    if normalized:
        scale = get_hand_scale_reference(landmarks)
        min_dist = float(min_dist / scale)

    return min_dist, closest_finger
