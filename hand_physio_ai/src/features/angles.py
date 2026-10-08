"""
Geometric Angle Calculation Module.

Implements rule-based, deterministic mathematical formulas:
- calculate_angle(a, b, c): Evaluates angle at joint vertex 'b' using vector dot products.
- Clipping to [-1.0, 1.0] avoids domain errors in arccos caused by floating-point rounding.
- Joint triplet extractors for MCP, PIP, and DIP finger articulations.
"""

from typing import Union, Dict, Tuple
import numpy as np
from src.pose.detector import (
    WRIST,
    THUMB_CMC, THUMB_MCP, THUMB_IP, THUMB_TIP,
    INDEX_MCP, INDEX_PIP, INDEX_DIP, INDEX_TIP,
    MIDDLE_MCP, MIDDLE_PIP, MIDDLE_DIP, MIDDLE_TIP,
    RING_MCP, RING_PIP, RING_DIP, RING_TIP,
    PINKY_MCP, PINKY_PIP, PINKY_DIP, PINKY_TIP
)


# Finger anatomical joint triplets: (proximal, vertex_joint, distal)
FINGER_PIP_TRIPLETS: Dict[str, Tuple[int, int, int]] = {
    "index": (INDEX_MCP, INDEX_PIP, INDEX_DIP),
    "middle": (MIDDLE_MCP, MIDDLE_PIP, MIDDLE_DIP),
    "ring": (RING_MCP, RING_PIP, RING_DIP),
    "pinky": (PINKY_MCP, PINKY_PIP, PINKY_DIP),
    "thumb": (THUMB_MCP, THUMB_IP, THUMB_TIP)
}

FINGER_MCP_TRIPLETS: Dict[str, Tuple[int, int, int]] = {
    "index": (WRIST, INDEX_MCP, INDEX_PIP),
    "middle": (WRIST, MIDDLE_MCP, MIDDLE_PIP),
    "ring": (WRIST, RING_MCP, RING_PIP),
    "pinky": (WRIST, PINKY_MCP, PINKY_PIP),
    "thumb": (WRIST, THUMB_CMC, THUMB_MCP)
}

FINGER_DIP_TRIPLETS: Dict[str, Tuple[int, int, int]] = {
    "index": (INDEX_PIP, INDEX_DIP, INDEX_TIP),
    "middle": (MIDDLE_PIP, MIDDLE_DIP, MIDDLE_TIP),
    "ring": (RING_PIP, RING_DIP, RING_TIP),
    "pinky": (PINKY_PIP, PINKY_DIP, PINKY_TIP),
    "thumb": (THUMB_CMC, THUMB_MCP, THUMB_IP)
}


def calculate_angle(
    a: Union[np.ndarray, list, tuple],
    b: Union[np.ndarray, list, tuple],
    c: Union[np.ndarray, list, tuple]
) -> float:
    """
    Calculate the interior angle (in degrees) at vertex point b formed by points a, b, and c.

    Formulas:
        vec_ba = a - b
        vec_bc = c - b
        cos(theta) = (vec_ba . vec_bc) / (||vec_ba|| * ||vec_bc||)
        theta = arccos(clip(cos(theta), -1.0, 1.0)) * (180 / pi)

    Args:
        a: Coordinates of first point (x, y) or (x, y, z).
        b: Coordinates of the vertex point (the joint center).
        c: Coordinates of third point (x, y) or (x, y, z).

    Returns:
        float: Angle in degrees in range [0.0, 180.0]. Returns 0.0 for degenerate zero-length vectors.
    """
    va = np.asarray(a, dtype=np.float64)
    vb = np.asarray(b, dtype=np.float64)
    vc = np.asarray(c, dtype=np.float64)

    # Use first 2 or 3 coordinates consistently
    dim = min(len(va), len(vb), len(vc))
    vec_ba = va[:dim] - vb[:dim]
    vec_bc = vc[:dim] - vb[:dim]

    norm_ba = np.linalg.norm(vec_ba)
    norm_bc = np.linalg.norm(vec_bc)

    # Handle zero-length vectors safely (e.g. overlapping landmarks)
    if norm_ba < 1e-7 or norm_bc < 1e-7:
        return 0.0

    cosine = np.dot(vec_ba, vec_bc) / (norm_ba * norm_bc)
    
    # Clip to avoid floating point domain errors in arccos outside [-1.0, 1.0]
    cosine_clipped = np.clip(cosine, -1.0, 1.0)
    angle_rad = np.arccos(cosine_clipped)
    
    return float(np.degrees(angle_rad))


def get_finger_joint_angle(
    landmarks: np.ndarray,
    triplet: Tuple[int, int, int]
) -> float:
    """
    Extract angle for a specific landmark index triplet (a_idx, b_idx, c_idx).

    Args:
        landmarks: (21, 2) or (21, 3) landmark array.
        triplet: (proximal_idx, vertex_idx, distal_idx).

    Returns:
        float: Joint angle in degrees.
    """
    if landmarks is None or len(landmarks) < 21:
        return 0.0

    p_a, p_b, p_c = triplet
    return calculate_angle(landmarks[p_a], landmarks[p_b], landmarks[p_c])


def get_finger_pip_angles(landmarks: np.ndarray) -> Dict[str, float]:
    """
    Compute Proximal Interphalangeal (PIP) joint angles for all 5 digits.

    Returns:
        Dict[str, float]: Mapping from finger name ('thumb', 'index', etc.) to angle in degrees.
    """
    angles = {}
    for finger_name, triplet in FINGER_PIP_TRIPLETS.items():
        angles[finger_name] = get_finger_joint_angle(landmarks, triplet)
    return angles


def get_finger_composite_angles(landmarks: np.ndarray) -> Dict[str, float]:
    """
    Compute composite flexion angle per finger by averaging MCP and PIP joint angles.
    For fully extended fingers, this angle is ~170-180 degrees.
    When a fist is clenched, this angle drops to ~40-70 degrees.

    Returns:
        Dict[str, float]: Finger name to composite angle in degrees.
    """
    composite = {}
    for finger in ["index", "middle", "ring", "pinky"]:
        mcp_angle = get_finger_joint_angle(landmarks, FINGER_MCP_TRIPLETS[finger])
        pip_angle = get_finger_joint_angle(landmarks, FINGER_PIP_TRIPLETS[finger])
        composite[finger] = (mcp_angle + pip_angle) / 2.0
    
    # Thumb composite (CMC + IP)
    thumb_mcp = get_finger_joint_angle(landmarks, FINGER_MCP_TRIPLETS["thumb"])
    thumb_ip = get_finger_joint_angle(landmarks, FINGER_PIP_TRIPLETS["thumb"])
    composite["thumb"] = (thumb_mcp + thumb_ip) / 2.0

    return composite


def get_average_finger_flexion(
    landmarks: np.ndarray,
    include_thumb: bool = False
) -> float:
    """
    Calculate the average flexion angle across fingers for fist open/close evaluation.

    Args:
        landmarks: (21, 3) or (21, 2) landmark coordinate array.
        include_thumb: If False, averages the 4 primary fingers (index, middle, ring, pinky).

    Returns:
        float: Average angle in degrees across the selected fingers.
    """
    if landmarks is None or len(landmarks) < 21:
        return 0.0

    fingers = ["index", "middle", "ring", "pinky"]
    if include_thumb:
        fingers.append("thumb")

    pip_angles = [get_finger_joint_angle(landmarks, FINGER_PIP_TRIPLETS[f]) for f in fingers]
    return float(np.mean(pip_angles))
