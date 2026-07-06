"""
Capture aligned face images using YuNet for SFace face recognition.

Examples:
  python capture_known_face.py
  python capture_known_face.py --name "Nguyen Van A" --msv "B21DCCN001"

Controls:
  SPACE = save current detected face immediately
  q/ESC = quit

Saved folder:
  known_faces/<MSV>__<name>/*.jpg (each is a 112x112 aligned color face)
"""

from __future__ import annotations

import argparse
import json
import re
import time
import urllib.request
from pathlib import Path

import cv2
import numpy as np

PROJECT_DIR = Path(__file__).resolve().parent
KNOWN_DIR = PROJECT_DIR / "known_faces"
MODELS_DIR = PROJECT_DIR / "models"


def safe_component(value: str, field_name: str) -> str:
    value = value.strip()
    value = re.sub(r'[<>:"/\\|?*]+', "_", value)
    value = re.sub(r"\s+", " ", value)
    if not value:
        raise ValueError(f"{field_name} cannot be empty")
    return value


def next_index(folder: Path, name: str) -> int:
    max_idx = 0
    for p in folder.glob(f"{name}_*.jpg"):
        try:
            idx = int(p.stem.rsplit("_", 1)[-1])
            max_idx = max(max_idx, idx)
        except Exception:
            pass
    return max_idx + 1


def check_and_download_models() -> tuple[Path, Path]:
    MODELS_DIR.mkdir(parents=True, exist_ok=True)
    yunet_path = MODELS_DIR / "face_detection_yunet_2023mar.onnx"
    sface_path = MODELS_DIR / "face_recognition_sface_2021dec.onnx"

    if not yunet_path.exists():
        print(f"Downloading YuNet face detector to {yunet_path}...")
        url = "https://github.com/opencv/opencv_zoo/raw/main/models/face_detection_yunet/face_detection_yunet_2023mar.onnx"
        urllib.request.urlretrieve(url, str(yunet_path))

    if not sface_path.exists():
        print(f"Downloading SFace face recognizer to {sface_path}...")
        url = "https://github.com/opencv/opencv_zoo/raw/main/models/face_recognition_sface/face_recognition_sface_2021dec.onnx"
        urllib.request.urlretrieve(url, str(sface_path))

    return yunet_path, sface_path


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--name", help="Full name; prompted if omitted")
    parser.add_argument("--student-id", "--msv", dest="student_id", help="Student ID; prompted if omitted")
    parser.add_argument("--camera", type=int, default=0)
    parser.add_argument("--count", type=int, default=120, help="Target number of saved face images")
    parser.add_argument("--interval", type=float, default=0.20, help="Seconds between auto-saves")
    args = parser.parse_args()

    student_id = safe_component(args.student_id or input("Nhap MSV: "), "Student ID")
    name = safe_component(args.name or input("Nhap ho ten: "), "Name")
    folder_name = f"{student_id}__{name}"
    out_dir = KNOWN_DIR / folder_name
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "profile.json").write_text(
        json.dumps({"name": name, "student_id": student_id}, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    # Make sure models exist
    yunet_path, sface_path = check_and_download_models()

    # Initialize YuNet
    # We will initialize with a dummy size and update it when we get the first frame
    detector = cv2.FaceDetectorYN.create(
        model=str(yunet_path),
        config="",
        input_size=(320, 320),
        score_threshold=0.9,
        nms_threshold=0.3,
        top_k=5000
    )

    # Initialize SFace
    recognizer = cv2.FaceRecognizerSF.create(
        model=str(sface_path),
        config=""
    )

    cap = cv2.VideoCapture(args.camera, cv2.CAP_DSHOW)
    if not cap.isOpened():
        cap = cv2.VideoCapture(args.camera)
    if not cap.isOpened():
        raise RuntimeError(f"Cannot open camera {args.camera}")

    # Set camera resolution if possible
    cap.set(cv2.CAP_PROP_FRAME_WIDTH, 640)
    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)

    # Read one frame to get size
    ret, frame = cap.read()
    if ret:
        h, w = frame.shape[:2]
        detector.setInputSize((w, h))

    idx = next_index(out_dir, student_id)
    saved = 0
    last_save = 0.0

    print(f"\nCapturing for: {name} | MSV: {student_id}")
    print(f"Output: {out_dir}")
    print("Look at the camera. SPACE saves manually, q/ESC quits.")

    while saved < args.count:
        ret, frame = cap.read()
        if not ret:
            print("Frame read failed")
            break

        h, w = frame.shape[:2]
        detector.setInputSize((w, h))
        retval, faces = detector.detect(frame)

        face_to_save = None
        display = frame.copy()

        if retval and faces is not None:
            # Sort by face bounding box area (w * h) to get the largest face
            faces_list = list(faces)
            faces_list.sort(key=lambda f: f[2] * f[3], reverse=True)
            largest_face = faces_list[0]

            # Bounding box
            x, y, fw, fh = map(int, largest_face[0:4])
            cv2.rectangle(display, (x, y), (x + fw, y + fh), (0, 255, 0), 2)

            # Draw 5 landmarks
            # Right eye (blue)
            cv2.circle(display, (int(largest_face[4]), int(largest_face[5])), 3, (255, 0, 0), -1)
            # Left eye (red)
            cv2.circle(display, (int(largest_face[6]), int(largest_face[7])), 3, (0, 0, 255), -1)
            # Nose tip (green)
            cv2.circle(display, (int(largest_face[8]), int(largest_face[9])), 3, (0, 255, 0), -1)
            # Right mouth corner (pink)
            cv2.circle(display, (int(largest_face[10]), int(largest_face[11])), 3, (255, 0, 255), -1)
            # Left mouth corner (yellow)
            cv2.circle(display, (int(largest_face[12]), int(largest_face[13])), 3, (0, 255, 255), -1)

            # Crop and align face using SFace recognizer.alignCrop
            face_to_save = recognizer.alignCrop(frame, largest_face)

        cv2.putText(display, f"{name} | {student_id}: {saved}/{args.count}", (10, 30), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 255, 255), 2)
        cv2.putText(display, "SPACE save | q quit", (10, 60), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 255, 255), 2)
        cv2.imshow("Capture Aligned Face", display)

        key = cv2.waitKey(1) & 0xFF
        now = time.time()
        should_save = (key == 32) or (face_to_save is not None and (now - last_save >= args.interval))

        if should_save and face_to_save is not None:
            path = out_dir / f"{student_id}_{idx:04d}.jpg"
            # cv2.imwrite doesn't support unicode paths on Windows, use imencode + tofile
            is_success, im_buf_arr = cv2.imencode(".jpg", face_to_save)
            if is_success:
                im_buf_arr.tofile(str(path))
                idx += 1
                saved += 1
                last_save = now
                print(f"Saved aligned face: {path.name} ({saved}/{args.count})")

        if key in (ord("q"), 27):
            break

    cap.release()
    cv2.destroyAllWindows()
    print(f"\nDone! Saved {saved} new aligned images for {name} ({student_id})")
