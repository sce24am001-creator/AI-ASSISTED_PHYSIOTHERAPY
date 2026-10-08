"""
Hand Landmark Detection Module using MediaPipe Tasks HandLandmarker.

Provides:
- 21 3D normalized landmarks per hand.
- Handedness tracking (Left / Right).
- Target hand filtering based on clinical prescription.
- Strict confidence verification & reliability gating (Hard Rule #5).
"""

import os
import urllib.request
from dataclasses import dataclass
from typing import Optional, List, Tuple
import cv2
import numpy as np

import mediapipe as mp
from mediapipe.tasks import python
from mediapipe.tasks.python import vision


# Standard 21 MediaPipe Hand Landmark Indices
WRIST = 0
THUMB_CMC, THUMB_MCP, THUMB_IP, THUMB_TIP = 1, 2, 3, 4
INDEX_MCP, INDEX_PIP, INDEX_DIP, INDEX_TIP = 5, 6, 7, 8
MIDDLE_MCP, MIDDLE_PIP, MIDDLE_DIP, MIDDLE_TIP = 9, 10, 11, 12
RING_MCP, RING_PIP, RING_DIP, RING_TIP = 13, 14, 15, 16
PINKY_MCP, PINKY_PIP, PINKY_DIP, PINKY_TIP = 17, 18, 19, 20

# Skeletal connections (bones) for drawing
HAND_CONNECTIONS = [
    # Thumb
    (WRIST, THUMB_CMC), (THUMB_CMC, THUMB_MCP), (THUMB_MCP, THUMB_IP), (THUMB_IP, THUMB_TIP),
    # Index finger
    (WRIST, INDEX_MCP), (INDEX_MCP, INDEX_PIP), (INDEX_PIP, INDEX_DIP), (INDEX_DIP, INDEX_TIP),
    # Middle finger
    (WRIST, MIDDLE_MCP), (MIDDLE_MCP, MIDDLE_PIP), (MIDDLE_PIP, MIDDLE_DIP), (MIDDLE_DIP, MIDDLE_TIP),
    # Ring finger
    (WRIST, RING_MCP), (RING_MCP, RING_PIP), (RING_PIP, RING_DIP), (RING_DIP, RING_TIP),
    # Pinky finger
    (WRIST, PINKY_MCP), (PINKY_MCP, PINKY_PIP), (PINKY_PIP, PINKY_DIP), (PINKY_DIP, PINKY_TIP),
    # Palm base cross-connections
    (INDEX_MCP, MIDDLE_MCP), (MIDDLE_MCP, RING_MCP), (RING_MCP, PINKY_MCP)
]

RELIABILITY_WARNING = "Movement could not be measured reliably. Adjust camera position or lighting."
CLINICAL_DISCLAIMER = "Camera-based estimate, not a clinical measurement."


@dataclass
class HandDetectionResult:
    """Encapsulates hand tracking output for a single frame."""
    is_tracked: bool
    landmarks: Optional[np.ndarray] = None          # (21, 3) normalized float array (x, y, z)
    pixel_landmarks: Optional[np.ndarray] = None    # (21, 2) pixel integer array (px, py)
    handedness: str = "Unknown"                     # "Left" or "Right"
    confidence: float = 0.0
    reliability_message: Optional[str] = None
    all_hands_count: int = 0


class HandDetector:
    """
    Wrapper around MediaPipe HandLandmarker with robust error handling,
    model caching, and clinical confidence verification.
    """

    MODEL_URL = "https://storage.googleapis.com/mediapipe-models/hand_landmarker/hand_landmarker/float16/latest/hand_landmarker.task"

    def __init__(
        self,
        model_path: Optional[str] = None,
        min_confidence: float = 0.6,
        max_num_hands: int = 2,
    ):
        """
        Initialize HandLandmarker.

        Args:
            model_path: Optional path to hand_landmarker.task. If None, uses default cache dir.
            min_confidence: Minimum score required to consider tracking reliable (Hard Rule #5).
            max_num_hands: Number of hands to detect in frame.
        """
        self.min_confidence = min_confidence
        self.max_num_hands = max_num_hands

        if model_path is None:
            # Default to hand_physio_ai/models/hand_landmarker.task
            base_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
            models_dir = os.path.join(base_dir, "models")
            os.makedirs(models_dir, exist_ok=True)
            self.model_path = os.path.join(models_dir, "hand_landmarker.task")
        else:
            self.model_path = model_path

        self._ensure_model_exists()

        base_options = python.BaseOptions(model_asset_path=self.model_path)
        options = vision.HandLandmarkerOptions(
            base_options=base_options,
            num_hands=self.max_num_hands,
            min_hand_detection_confidence=0.5,
            min_hand_presence_confidence=0.5,
            min_tracking_confidence=0.5,
            running_mode=vision.RunningMode.IMAGE
        )
        self.landmarker = vision.HandLandmarker.create_from_options(options)

    def _ensure_model_exists(self) -> None:
        """Downloads the pretrained Google task model if missing."""
        if not os.path.exists(self.model_path):
            if not self.MODEL_URL.startswith("https://"):
                raise ValueError(f"Insecure or unsupported model download URL scheme: {self.MODEL_URL}")
            os.makedirs(os.path.dirname(self.model_path), exist_ok=True)
            urllib.request.urlretrieve(self.MODEL_URL, self.model_path)  # nosec B310

    def detect(
        self,
        bgr_frame: np.ndarray,
        target_hand: Optional[str] = None
    ) -> HandDetectionResult:
        """
        Process a BGR frame from OpenCV, extract landmarks, and evaluate tracking confidence.

        Args:
            bgr_frame: OpenCV BGR image array.
            target_hand: Optional filter ('Left' or 'Right'). If provided, selects the matching hand.

        Returns:
            HandDetectionResult: Tracking state, 21 landmark arrays, and reliability status.
        """
        if bgr_frame is None or bgr_frame.size == 0:
            return HandDetectionResult(
                is_tracked=False,
                reliability_message=RELIABILITY_WARNING
            )

        h, w = bgr_frame.shape[:2]

        # Convert OpenCV BGR to RGB for MediaPipe Image
        rgb_frame = cv2.cvtColor(bgr_frame, cv2.COLOR_BGR2RGB)
        mp_image = mp.Image(image_format=mp.ImageFormat.SRGB, data=rgb_frame)

        result = self.landmarker.detect(mp_image)

        hands_detected = len(result.hand_landmarks)
        if hands_detected == 0:
            return HandDetectionResult(
                is_tracked=False,
                all_hands_count=0,
                reliability_message=RELIABILITY_WARNING
            )

        # Iterate over detected hands and pick the appropriate one
        selected_index = -1
        selected_handedness = "Unknown"
        selected_confidence = 0.0

        for i, (landmarks, handedness_categories) in enumerate(zip(result.hand_landmarks, result.handedness)):
            if handedness_categories:
                hand_category = handedness_categories[0]
                label = hand_category.category_name  # "Left" or "Right"
                score = hand_category.score
            else:
                label = "Unknown"
                score = 0.5

            if target_hand is not None:
                if label.lower() == target_hand.lower():
                    selected_index = i
                    selected_handedness = label
                    selected_confidence = score
                    break
            else:
                # Default: pick the hand with highest score
                if score > selected_confidence:
                    selected_index = i
                    selected_handedness = label
                    selected_confidence = score

        # If target hand was specified but not found among detected hands
        if selected_index == -1:
            return HandDetectionResult(
                is_tracked=False,
                all_hands_count=hands_detected,
                reliability_message=RELIABILITY_WARNING
            )

        # Enforce Hard Rule #5: check if confidence meets threshold
        if selected_confidence < self.min_confidence:
            return HandDetectionResult(
                is_tracked=False,
                handedness=selected_handedness,
                confidence=selected_confidence,
                all_hands_count=hands_detected,
                reliability_message=RELIABILITY_WARNING
            )

        # Extract 21 landmarks for the selected hand
        chosen_landmarks = result.hand_landmarks[selected_index]
        norm_coords = np.zeros((21, 3), dtype=np.float32)
        pixel_coords = np.zeros((21, 2), dtype=np.int32)

        for j, lm in enumerate(chosen_landmarks):
            norm_coords[j] = [lm.x, lm.y, lm.z]
            px = int(np.clip(lm.x * w, 0, w - 1))
            py = int(np.clip(lm.y * h, 0, h - 1))
            pixel_coords[j] = [px, py]

        return HandDetectionResult(
            is_tracked=True,
            landmarks=norm_coords,
            pixel_landmarks=pixel_coords,
            handedness=selected_handedness,
            confidence=selected_confidence,
            reliability_message=None,
            all_hands_count=hands_detected
        )

    def close(self) -> None:
        """Release MediaPipe resources."""
        if hasattr(self, 'landmarker') and self.landmarker is not None:
            self.landmarker.close()
            self.landmarker = None

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()
