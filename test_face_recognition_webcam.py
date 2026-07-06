"""
Preview/test trained LBPH face recognition with webcam.

Run:
  python test_face_recognition_webcam.py

Controls:
  q/ESC = quit
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import cv2

PROJECT_DIR = Path(__file__).resolve().parent
DEFAULT_MODEL_PATH = PROJECT_DIR / "models" / "lbph_model.xml"
DEFAULT_LABELS_PATH = PROJECT_DIR / "models" / "labels.json"
ROOT_MODEL_PATH = PROJECT_DIR / "lbph_model.xml"
DEFAULT_LABELS = ["Quan", "Tuan Anh"]
FACE_SIZE = (200, 200)


def normalize_profiles(data) -> list[dict[str, str]]:
    return [
        item if isinstance(item, dict) else {"name": str(item), "student_id": ""}
        for item in data
    ]


def require_cv2_face() -> None:
    if not hasattr(cv2, "face"):
        raise RuntimeError("cv2.face missing. Install: python -m pip install opencv-contrib-python")


def load_model():
    require_cv2_face()
    recognizer = cv2.face.LBPHFaceRecognizer_create()

    import tempfile
    import shutil
    import os
    
    def read_model_safe(model_path):
        with tempfile.NamedTemporaryFile(delete=False, suffix=".xml") as tmp:
            tmp_path = tmp.name
        shutil.copy2(str(model_path), tmp_path)
        recognizer.read(tmp_path)
        os.remove(tmp_path)

    if DEFAULT_MODEL_PATH.exists() and DEFAULT_LABELS_PATH.exists():
        read_model_safe(DEFAULT_MODEL_PATH)
        labels = normalize_profiles(json.loads(DEFAULT_LABELS_PATH.read_text(encoding="utf-8")))
        print(f"Loaded model: {DEFAULT_MODEL_PATH}")
        print(f"Labels: {labels}")
        return recognizer, labels

    if ROOT_MODEL_PATH.exists():
        read_model_safe(ROOT_MODEL_PATH)
        labels = normalize_profiles(DEFAULT_LABELS)
        print(f"Loaded root model: {ROOT_MODEL_PATH}")
        print(f"Labels: {labels}")
        return recognizer, labels

    raise FileNotFoundError("No model found. Run: python train_known_faces.py")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--camera", type=int, default=0)
    parser.add_argument("--threshold", type=float, default=60.0)
    args = parser.parse_args()

    recognizer, labels = load_model()
    cascade = cv2.CascadeClassifier(cv2.data.haarcascades + "haarcascade_frontalface_default.xml")
    if cascade.empty():
        raise RuntimeError("Cannot load Haar cascade")

    cap = cv2.VideoCapture(args.camera, cv2.CAP_DSHOW)
    if not cap.isOpened():
        cap = cv2.VideoCapture(args.camera)
    if not cap.isOpened():
        raise RuntimeError(f"Cannot open camera {args.camera}")

    print("Webcam test running. Press q/ESC to quit.")
    while True:
        ret, frame = cap.read()
        if not ret:
            print("Frame read failed")
            break

        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        faces = cascade.detectMultiScale(gray, scaleFactor=1.2, minNeighbors=5)

        for (x, y, w, h) in faces:
            roi = gray[y : y + h, x : x + w]
            roi = cv2.resize(roi, FACE_SIZE)
            clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8,8))
            roi = clahe.apply(roi)
            label_id, conf = recognizer.predict(roi)

            if 1 <= label_id <= len(labels) and conf <= args.threshold:
                profile = labels[label_id - 1]
                name = profile["name"]
                if profile.get("student_id"):
                    name = f"{name} | {profile['student_id']}"
                color = (0, 255, 0)
            else:
                name = "Unknown"
                color = (0, 0, 255)

            cv2.rectangle(frame, (x, y), (x + w, y + h), color, 2)
            cv2.putText(frame, f"{name} ({conf:.1f})", (x, y - 10), cv2.FONT_HERSHEY_SIMPLEX, 0.8, color, 2)

        cv2.imshow("Face Recognition Test", frame)
        key = cv2.waitKey(1) & 0xFF
        if key in (ord("q"), 27):
            break

    cap.release()
    cv2.destroyAllWindows()


if __name__ == "__main__":
    main()
