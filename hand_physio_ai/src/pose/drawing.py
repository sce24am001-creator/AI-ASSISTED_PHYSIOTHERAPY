"""
Drawing and Visualization Module.

Renders:
- 21-landmark skeletal hand overlay with modern medical aesthetic.
- Prominent clinical disclaimer banner: 'Camera-based estimate, not a clinical measurement.' (Hard Rule #3).
- Tracking reliability warning banner: 'Movement could not be measured reliably. Adjust camera position or lighting.' (Hard Rule #5).
- Clean visual cues for active fingertips and wrist base.
"""

import cv2
import numpy as np
from typing import Optional
from src.pose.detector import (
    HandDetectionResult,
    HAND_CONNECTIONS,
    THUMB_TIP, INDEX_TIP, MIDDLE_TIP, RING_TIP, PINKY_TIP, WRIST,
    RELIABILITY_WARNING, CLINICAL_DISCLAIMER
)

# Color constants in BGR format
COLOR_BONE = (220, 215, 180)            # Soft light blue-grey
COLOR_JOINT = (255, 200, 60)           # Cyan-teal
COLOR_JOINT_BORDER = (160, 100, 20)    # Deep teal
COLOR_FINGERTIP = (80, 220, 120)       # Emerald green
COLOR_WARNING_BG = (20, 30, 45)        # Dark navy/slate
COLOR_WARNING_TEXT = (50, 180, 255)    # Warm warning amber
COLOR_SUCCESS_TEXT = (100, 230, 140)   # Clean medical green
COLOR_DISCLAIMER_BG = (15, 15, 18)     # Near black
COLOR_DISCLAIMER_TEXT = (190, 190, 200) # Soft muted grey


def draw_skeleton(
    frame: np.ndarray,
    detection: HandDetectionResult,
    show_disclaimer: bool = True
) -> np.ndarray:
    """
    Overlay skeletal connections, joint nodes, and status indicators onto a camera frame.

    Args:
        frame: OpenCV BGR image array.
        detection: HandDetectionResult from HandDetector.
        show_disclaimer: Whether to include the mandatory clinical disclaimer banner.

    Returns:
        np.ndarray: Annotated BGR frame copy.
    """
    if frame is None or frame.size == 0:
        return frame

    annotated = frame.copy()
    h, w = annotated.shape[:2]

    # 1. If hand is reliably tracked, draw the skeletal lines and joints
    if detection.is_tracked and detection.pixel_landmarks is not None:
        pts = detection.pixel_landmarks

        # Draw bones (connections)
        for p1_idx, p2_idx in HAND_CONNECTIONS:
            pt1 = tuple(pts[p1_idx])
            pt2 = tuple(pts[p2_idx])
            cv2.line(annotated, pt1, pt2, COLOR_BONE, 2, cv2.LINE_AA)

        # Draw joints
        fingertip_indices = {THUMB_TIP, INDEX_TIP, MIDDLE_TIP, RING_TIP, PINKY_TIP}
        for idx in range(21):
            center = tuple(pts[idx])
            if idx in fingertip_indices:
                # Highlight fingertips
                cv2.circle(annotated, center, 6, COLOR_FINGERTIP, -1, cv2.LINE_AA)
                cv2.circle(annotated, center, 7, (255, 255, 255), 1, cv2.LINE_AA)
            elif idx == WRIST:
                # Highlight wrist origin
                cv2.circle(annotated, center, 5, (255, 120, 80), -1, cv2.LINE_AA)
                cv2.circle(annotated, center, 6, (255, 255, 255), 1, cv2.LINE_AA)
            else:
                # Intermediate knuckles
                cv2.circle(annotated, center, 4, COLOR_JOINT, -1, cv2.LINE_AA)
                cv2.circle(annotated, center, 4, COLOR_JOINT_BORDER, 1, cv2.LINE_AA)

        # Top tracking badge (Reliable)
        status_text = f"TRACKED: {detection.handedness} Hand ({int(detection.confidence * 100)}%)"
        _draw_pill_badge(annotated, status_text, x=16, y=28, text_color=COLOR_SUCCESS_TEXT)

    else:
        # Top Warning Banner (Degraded / Hand Missing - Hard Rule #5)
        warning_msg = detection.reliability_message or RELIABILITY_WARNING
        _draw_banner(
            annotated,
            text=warning_msg,
            y=12,
            height=34,
            bg_color=COLOR_WARNING_BG,
            text_color=COLOR_WARNING_TEXT
        )

    # 2. Bottom Clinical Disclaimer Banner (Mandatory - Hard Rule #3)
    if show_disclaimer:
        _draw_banner(
            annotated,
            text=f"NOTE: {CLINICAL_DISCLAIMER}",
            y=h - 30,
            height=26,
            bg_color=COLOR_DISCLAIMER_BG,
            text_color=COLOR_DISCLAIMER_TEXT,
            font_scale=0.42
        )

    return annotated


def _draw_pill_badge(
    img: np.ndarray,
    text: str,
    x: int,
    y: int,
    text_color: tuple,
    bg_color: tuple = (20, 24, 28)
) -> None:
    """Draw a compact, semi-transparent status pill."""
    font = cv2.FONT_HERSHEY_SIMPLEX
    font_scale = 0.5
    thickness = 1
    (tw, th), baseline = cv2.getTextSize(text, font, font_scale, thickness)

    pad_x, pad_y = 10, 6
    x1, y1 = x, y - th - pad_y
    x2, y2 = x + tw + pad_x * 2, y + baseline + pad_y

    overlay = img.copy()
    cv2.rectangle(overlay, (x1, y1), (x2, y2), bg_color, -1)
    cv2.circle(overlay, (x1 + 12, y - th // 2), 4, text_color, -1)
    cv2.addWeighted(overlay, 0.75, img, 0.25, 0, img)

    cv2.putText(img, text, (x + 22, y), font, font_scale, text_color, thickness, cv2.LINE_AA)


def _draw_banner(
    img: np.ndarray,
    text: str,
    y: int,
    height: int,
    bg_color: tuple,
    text_color: tuple,
    font_scale: float = 0.46
) -> None:
    """Draw a full-width semi-transparent informational banner."""
    h, w = img.shape[:2]
    y1 = max(0, y)
    y2 = min(h, y + height)

    overlay = img.copy()
    cv2.rectangle(overlay, (0, y1), (w, y2), bg_color, -1)
    cv2.addWeighted(overlay, 0.82, img, 0.18, 0, img)

    font = cv2.FONT_HERSHEY_SIMPLEX
    thickness = 1
    (tw, th), _ = cv2.getTextSize(text, font, font_scale, thickness)
    tx = max(10, (w - tw) // 2)
    ty = y1 + (height + th) // 2 - 2

    cv2.putText(img, text, (tx, ty), font, font_scale, text_color, thickness, cv2.LINE_AA)
