"""Swappable video inputs. Everything downstream only sees FrameSource."""
import cv2
from abc import ABC, abstractmethod
from typing import Iterator, Tuple
import numpy as np


class FrameSource(ABC):
    @abstractmethod
    def frames(self) -> Iterator[Tuple[int, float, np.ndarray]]:
        """Yield (frame_index, timestamp_seconds, BGR frame)."""


class FileSource(FrameSource):
    def __init__(self, path: str):
        self.path = path

    def frames(self):
        cap = cv2.VideoCapture(self.path)
        if not cap.isOpened():
            raise FileNotFoundError(f"Cannot open video: {self.path}")
        fps = cap.get(cv2.CAP_PROP_FPS) or 25.0
        i = 0
        try:
            while True:
                ok, frame = cap.read()
                if not ok:
                    break
                yield i, i / fps, frame
                i += 1
        finally:
            cap.release()


class RingWhepSource(FrameSource):
    """TODO: connect to the Ring live-view WHEP/WebRTC session (backend-side,
    token stays on server). Suggested: aiortc to negotiate WHEP, decode the
    video track to numpy frames, yield them here. Until the Playground video
    is confirmed, use FileSource."""

    def __init__(self, device_id: str, access_token: str):
        self.device_id, self.access_token = device_id, access_token

    def frames(self):
        raise NotImplementedError("WHEP source not implemented yet")
