#!/usr/bin/env python3
"""
Rekognition Spike Test Script.
Empirically tests AWS Rekognition DetectLabels on test frames or clips,
tabulating detected caretaking (fall/posture/context) and security (weapons/masks) labels.

Usage:
    python backend/scripts/rekognition_spike.py [optional_path_to_image_or_video]
"""
import os
import sys
from pathlib import Path

# Add backend directory to path
backend_dir = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(backend_dir))

import cv2
import boto3
from botocore.exceptions import ClientError, NoCredentialsError
from dotenv import load_dotenv

load_dotenv(backend_dir / ".env")

AWS_REGION = os.getenv("AWS_REGION", "ap-south-1")

CARETAKING_SIGNALS = {
    "fall": {"Fallen Person", "Injury", "Crawling", "Kneeling"},
    "posture": {"Sitting", "Standing", "Walking", "Sleeping"},
    "context": {"Floor", "Flooring", "Ground", "Bed", "Couch", "Bedroom"},
}

SECURITY_SIGNALS = {
    "weapons": {"Weapon", "Gun", "Handgun", "Firearm", "Knife", "Dagger", "Blade"},
    "masks": {"Mask", "Gas Mask"},
    "incidents": {"Fighting", "Window - Broken", "Fire", "Smoke"},
}


def get_rekognition_client():
    return boto3.client("rekognition", region_name=AWS_REGION)


def detect_image_labels(client, jpeg_bytes, min_confidence=50, max_labels=40):
    try:
        response = client.detect_labels(
            Image={"Bytes": jpeg_bytes},
            MaxLabels=max_labels,
            MinConfidence=min_confidence,
        )
        return response
    except (ClientError, NoCredentialsError) as e:
        return {"error": str(e)}


def analyze_rekognition_response(resp):
    if "error" in resp:
        return {"error": resp["error"]}

    labels = resp.get("Labels", [])
    person_instances = []
    signals_found = {
        "fall": [],
        "posture": [],
        "context": [],
        "weapons": [],
        "masks": [],
        "incidents": [],
        "other": [],
    }

    for lbl in labels:
        name = lbl["Name"]
        conf = round(lbl["Confidence"], 1)

        # Check Person and its bounding box instances
        if name == "Person":
            for inst in lbl.get("Instances", []):
                box = inst.get("BoundingBox", {})
                inst_conf = round(inst.get("Confidence", conf), 1)
                person_instances.append({
                    "confidence": inst_conf,
                    "box": {
                        "left": round(box.get("Left", 0) * 100, 1),
                        "top": round(box.get("Top", 0) * 100, 1),
                        "width": round(box.get("Width", 0) * 100, 1),
                        "height": round(box.get("Height", 0) * 100, 1),
                    },
                })

        categorized = False
        for cat, names in CARETAKING_SIGNALS.items():
            if name in names:
                signals_found[cat].append(f"{name} ({conf}%)")
                categorized = True
        for cat, names in SECURITY_SIGNALS.items():
            if name in names:
                signals_found[cat].append(f"{name} ({conf}%)")
                categorized = True
        if not categorized and len(signals_found["other"]) < 5:
            signals_found["other"].append(f"{name} ({conf}%)")

    return {
        "person_detected": len(person_instances) > 0 or any(l["Name"] == "Person" for l in labels),
        "person_instances": person_instances,
        "signals": signals_found,
        "total_labels": len(labels),
    }


def extract_test_frames(source_path):
    p = Path(source_path)
    if not p.exists():
        return []
    if p.suffix.lower() in (".jpg", ".jpeg", ".png"):
        frame = cv2.imread(str(p))
        if frame is not None:
            _, buf = cv2.imencode(".jpg", frame, [cv2.IMWRITE_JPEG_QUALITY, 85])
            return [(p.name, buf.tobytes())]
    elif p.suffix.lower() in (".mp4", ".webm", ".mov"):
        cap = cv2.VideoCapture(str(p))
        frames = []
        count = 0
        total = int(cap.get(cv2.CAP_PROP_FRAME_COUNT) or 1)
        step = max(1, total // 4)
        while cap.isOpened():
            ret, frame = cap.read()
            if not ret or len(frames) >= 4:
                break
            if count % step == 0:
                h, w = frame.shape[:2]
                if w > 960:
                    frame = cv2.resize(frame, (960, int(h * 960 / w)))
                _, buf = cv2.imencode(".jpg", frame, [cv2.IMWRITE_JPEG_QUALITY, 85])
                frames.append((f"{p.name}_f{count}", buf.tobytes()))
            count += 1
        cap.release()
        return frames
    return []


def main():
    target = sys.argv[1] if len(sys.argv) > 1 else None
    test_files = []

    if target:
        test_files.extend(extract_test_frames(target))
    else:
        # Check clips directory for sample clips
        clips_dir = backend_dir / "clips"
        samples = list(clips_dir.glob("sample_*.mp4")) + list(clips_dir.glob("ring_*.mp4"))[:2]
        for s in samples:
            test_files.extend(extract_test_frames(s))

    print(f"=== Amazon Rekognition DetectLabels Spike Test ===")
    print(f"Target AWS Region: {AWS_REGION}")
    print(f"Frames queued for test: {len(test_files)}\n")

    try:
        client = get_rekognition_client()
    except Exception as e:
        print(f"Error initializing Rekognition client: {e}")
        return

    results_table = []
    for name, img_bytes in test_files:
        print(f"Testing frame '{name}' ({len(img_bytes)} bytes)...")
        raw_resp = detect_image_labels(client, img_bytes)
        analyzed = analyze_rekognition_response(raw_resp)
        results_table.append((name, analyzed))

    # Print Markdown Summary Table
    print("\n\n### Rekognition Spike Test Findings\n")
    print("| Test Frame | Person Detected | Fall / Injury | Posture | Context | Weapons / Security | Face Covering |")
    print("|---|---|---|---|---|---|---|")
    for name, res in results_table:
        if "error" in res:
            print(f"| `{name}` | Error: {res['error'][:40]} | - | - | - | - | - |")
            continue
        person_str = "Yes" if res["person_detected"] else "No"
        fall_str = ", ".join(res["signals"]["fall"]) or "None"
        posture_str = ", ".join(res["signals"]["posture"]) or "None"
        context_str = ", ".join(res["signals"]["context"]) or "None"
        sec_str = ", ".join(res["signals"]["weapons"] + res["signals"]["incidents"]) or "None"
        mask_str = ", ".join(res["signals"]["masks"]) or "None"
        print(f"| `{name}` | {person_str} | {fall_str} | {posture_str} | {context_str} | {sec_str} | {mask_str} |")

    print("\nSpike test completed.")


if __name__ == "__main__":
    main()
