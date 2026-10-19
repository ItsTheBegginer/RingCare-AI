import os
from unittest.mock import MagicMock
import numpy as np
import pytest
from botocore.exceptions import ClientError

from app.frames import FrameSource
from app.vision import analyze, _daily_cap_tracker


class SyntheticFrameSource(FrameSource):
    """Generates synthetic video frames for deterministic testing without external video files."""
    def __init__(self, num_frames=15, width=480, height=360):
        self.num_frames = num_frames
        self.width = width
        self.height = height

    def frames(self):
        for idx in range(self.num_frames):
            ts = idx * 0.2
            # Create a simple frame with a moving rectangle to simulate motion
            frame = np.zeros((self.height, self.width, 3), dtype=np.uint8)
            # Add motion in later frames
            if idx > 3:
                x = min(self.width - 60, idx * 20)
                frame[100:220, x:x+60] = 200
            yield idx, ts, frame


def test_opencv_backend(monkeypatch):
    """Test standard OpenCV analysis without Rekognition."""
    monkeypatch.setenv("VISION_BACKEND", "opencv")
    source = SyntheticFrameSource(num_frames=12)

    result = analyze(source, sample_every=1, n_keyframes=3)

    assert "error" not in result
    assert result["detector"] == "hog"
    assert "person_detected" in result
    assert "person_frames_pct" in result
    assert "wide_posture_frames_pct" in result
    assert "motion_peak" in result
    assert "motion_frames_pct" in result
    assert "keyframes" in result
    assert len(result["keyframes"]) > 0


def test_rekognition_detection_with_mock(monkeypatch):
    """Test Amazon Rekognition detection parsing labels, person bounding box, and signals."""
    monkeypatch.setenv("VISION_BACKEND", "rekognition")
    monkeypatch.setenv("REKOGNITION_MAX_FRAMES", "4")
    monkeypatch.setenv("REKOGNITION_DAILY_CAP", "500")

    mock_client = MagicMock()
    # Mock DetectLabels response containing Person with wide box and signals
    mock_client.detect_labels.return_value = {
        "Labels": [
            {
                "Name": "Person",
                "Confidence": 95.8,
                "Instances": [
                    {
                        "BoundingBox": {
                            "Width": 0.5,
                            "Height": 0.25,  # Width > Height -> wide posture
                            "Left": 0.2,
                            "Top": 0.6,
                        },
                        "Confidence": 96.2,
                    }
                ],
            },
            {"Name": "Fallen Person", "Confidence": 82.5},
            {"Name": "Floor", "Confidence": 91.0},
            {"Name": "Knife", "Confidence": 78.4},
        ]
    }

    source = SyntheticFrameSource(num_frames=12)
    result = analyze(source, sample_every=1, rekognition_client=mock_client)

    assert "error" not in result
    assert result["detector"] == "rekognition"
    assert result["person_detected"] is True
    assert result["person_frames_pct"] > 0
    assert result["wide_posture_frames_pct"] > 0
    assert result["bbox"] is not None
    assert result["bbox"]["width"] == 50.0
    assert result["bbox"]["height"] == 25.0
    assert result["bbox"]["confidence"] == 0.96

    # Verify per_frame details
    assert len(result["per_frame"]) > 0
    first_frame = result["per_frame"][0]
    assert first_frame["person"] is True
    assert first_frame["wide_posture"] is True
    label_names = [l["label"] for l in first_frame["labels"]]
    assert "Fallen Person" in label_names
    assert "Floor" in label_names
    assert "Knife" in label_names


def test_rekognition_fallback_on_error(monkeypatch):
    """Test graceful fallback to OpenCV HOG when Rekognition raises an AWS ClientError."""
    monkeypatch.setenv("VISION_BACKEND", "rekognition")

    mock_client = MagicMock()
    mock_client.detect_labels.side_effect = ClientError(
        error_response={"Error": {"Code": "AccessDeniedException", "Message": "Access denied"}},
        operation_name="DetectLabels",
    )

    source = SyntheticFrameSource(num_frames=12)
    result = analyze(source, sample_every=1, rekognition_client=mock_client)

    # Ingestion must never crash; detector should note fallback
    assert "error" not in result
    assert "hog (rekognition failed: AccessDeniedException)" in result["detector"]
    assert "person_detected" in result
    assert "motion_frames_pct" in result
    assert len(result["keyframes"]) > 0


def test_rekognition_daily_cap_fallback(monkeypatch):
    """Test graceful fallback to OpenCV HOG when the daily spend cap is reached."""
    monkeypatch.setenv("VISION_BACKEND", "rekognition")
    monkeypatch.setenv("REKOGNITION_DAILY_CAP", "2")

    # Artificially saturate the in-memory cap
    _daily_cap_tracker["count"] = 100
    _daily_cap_tracker["date"] = "2026-10-19"

    mock_client = MagicMock()
    source = SyntheticFrameSource(num_frames=12)
    result = analyze(source, sample_every=1, rekognition_client=mock_client)

    assert "error" not in result
    assert result["detector"] == "hog (rekognition daily cap exceeded)"
    # Rekognition API should not even be called when cap is exceeded
    mock_client.detect_labels.assert_not_called()


def test_legacy_key_compatibility(monkeypatch):
    """Ensure all legacy vision output keys required by assess.py and schema.py remain intact."""
    monkeypatch.setenv("VISION_BACKEND", "opencv")
    source = SyntheticFrameSource(num_frames=10)
    result = analyze(source, sample_every=1)

    required_keys = [
        "frames_sampled",
        "duration_s",
        "motion_avg",
        "motion_peak",
        "motion_frames_pct",
        "person_detected",
        "person_frames_pct",
        "wide_posture_frames_pct",
        "bbox",
        "keyframes",
        "detector",
        "per_frame",
    ]
    for key in required_keys:
        assert key in result, f"Missing required key: {key}"
