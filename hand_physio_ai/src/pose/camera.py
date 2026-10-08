"""
Camera Access Module for Local Webcam Streaming.

Windows Specifics:
- Uses camera index 0 with cv2.CAP_DSHOW for rapid and reliable device initialization.
- Includes a 1.0-second sensor warm-up pause upon opening.
- Tolerates up to 30 consecutive failed frame reads before declaring camera failure.
- Ensures camera hardware is safely released on exit.
"""

import time
import cv2
from typing import Optional, Tuple
import numpy as np


class CameraManager:
    """
    Manages webcam capture lifecycle with hardware warm-up and retry resilience.
    """

    def __init__(
        self,
        camera_index: int = 0,
        warmup_seconds: float = 1.0,
        max_consecutive_failures: int = 30,
    ):
        """
        Initialize camera parameters.

        Args:
            camera_index: Hardware device index (default 0 for built-in camera).
            warmup_seconds: Time to sleep after opening to allow sensor exposure/focus to settle.
            max_consecutive_failures: Consecutive read errors tolerated before giving up.
        """
        self.camera_index = camera_index
        self.warmup_seconds = warmup_seconds
        self.max_consecutive_failures = max_consecutive_failures
        self.cap: Optional[cv2.VideoCapture] = None
        self.consecutive_failures = 0
        self.is_opened = False

    def open(self) -> bool:
        """
        Open the camera device using DirectShow backend on Windows.

        Returns:
            bool: True if camera was successfully opened, False otherwise.
        """
        if self.is_opened and self.cap is not None and self.cap.isOpened():
            return True

        # Use DirectShow backend on Windows to avoid negotiation hangs
        self.cap = cv2.VideoCapture(self.camera_index, cv2.CAP_DSHOW)

        if not self.cap.isOpened():
            self.is_opened = False
            return False

        # Allow camera hardware sensor to warm up and auto-expose
        time.sleep(self.warmup_seconds)
        self.is_opened = True
        self.consecutive_failures = 0
        return True

    def read_frame(self) -> Tuple[bool, Optional[np.ndarray]]:
        """
        Read a single frame from the camera, handling warm-up blips and retries.

        Returns:
            Tuple[bool, Optional[np.ndarray]]: (Success flag, frame array or None).
        """
        if not self.is_opened or self.cap is None:
            if not self.open():
                return False, None

        ret, frame = self.cap.read()

        if ret and frame is not None and frame.size > 0:
            self.consecutive_failures = 0
            return True, frame

        # Increment consecutive failure count
        self.consecutive_failures += 1
        if self.consecutive_failures >= self.max_consecutive_failures:
            # Persistent hardware or disconnection error
            return False, None

        # Return failure for this single tick without tearing down yet
        return False, None

    def release(self) -> None:
        """Release the video capture hardware resource."""
        if self.cap is not None:
            self.cap.release()
            self.cap = None
        self.is_opened = False
        self.consecutive_failures = 0

    def __enter__(self):
        self.open()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.release()
