"""
Capture face images for LBPH training.

Examples:
  python capture_known_face.py
  python capture_known_face.py --name "Nguyen Van A" --msv "B21DCCN001"

Controls:
  SPACE = save current detected face immediately
  q/ESC = quit

Saved folder:
  known_faces/<MSV>__<name>/*.jpg
"""

from __future__ import annotations

import argparse
import json
import re
import time
from pathlib import Path

import cv2

PROJECT_DIR = Path(__file__).resolve().parent
KNOWN_DIR = PROJECT_DIR / "known_faces"
FACE_SIZE = (200, 200)


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


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--name", help="Full name; prompted if omitted")
    parser.add_argument("--student-id", "--msv", dest="student_id", help="Student ID; prompted if omitted")
    parser.add_argument("--camera", type=int, default=0)
    parser.add_argument("--count", type=int, default=120, help="Target number of saved face images")
    parser.add_argument("--interval", type=float, default=0.25, help="Seconds between auto-saves")
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

    cascade = cv2.CascadeClassifier(cv2.data.haarcascades + "haarcascade_frontalface_default.xml")
    if cascade.empty():
        raise RuntimeError("Cannot load Haar cascade")

    cap = cv2.VideoCapture(args.camera, cv2.CAP_DSHOW)
    if not cap.isOpened():
        cap = cv2.VideoCapture(args.camera)
    if not cap.isOpened():
        raise RuntimeError(f"Cannot open camera {args.camera}")

    idx = next_index(out_dir, student_id)
    saved = 0
    last_save = 0.0

    print(f"Capturing for: {name} | MSV: {student_id}")
    print(f"Output: {out_dir}")
    print("Look at the camera. SPACE saves manually, q/ESC quits.")

    while saved < args.count:
        ret, frame = cap.read()
        if not ret:
            print("Frame read failed")
            break

        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        faces = cascade.detectMultiScale(gray, scaleFactor=1.2, minNeighbors=5)
        faces = sorted(faces, key=lambda r: r[2] * r[3], reverse=True)

        face_to_save = None
        if faces:
            x, y, w, h = faces[0]
            cv2.rectangle(frame, (x, y), (x + w, y + h), (0, 255, 0), 2)
            roi = gray[y : y + h, x : x + w]
            face_to_save = cv2.resize(roi, FACE_SIZE)
            face_to_save = cv2.equalizeHist(face_to_save)

        cv2.putText(frame, f"{name} | {student_id}: {saved}/{args.count}", (10, 30), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 255, 255), 2)
        cv2.putText(frame, "SPACE save | q quit", (10, 60), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 255, 255), 2)
        cv2.imshow("Capture Known Face", frame)

        key = cv2.waitKey(1) & 0xFF
        now = time.time()
        should_save = key == 32 or (face_to_save is not None and now - last_save >= args.interval)

        if should_save and face_to_save is not None:
            path = out_dir / f"{student_id}_{idx:04d}.jpg"
            is_success, im_buf_arr = cv2.imencode(".jpg", face_to_save)
            if is_success:
                im_buf_arr.tofile(str(path))
            print(f"Saved {path}")
            idx += 1
            saved += 1
            last_save = now

        if key in (ord("q"), 27):
            break

    cap.release()
    cv2.destroyAllWindows()
    print(f"Done. Saved {saved} new images for {name} ({student_id})")


if __name__ == "__main__":
    main()
