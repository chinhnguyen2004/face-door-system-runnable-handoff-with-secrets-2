"""
Preview/test trained SFace face recognition with webcam.

Run:
  python test_face_recognition_webcam.py

Controls:
  q/ESC = quit
"""

from __future__ import annotations

import argparse
import json
import urllib.request
from pathlib import Path

import cv2
import numpy as np

PROJECT_DIR = Path(__file__).resolve().parent
MODELS_DIR = PROJECT_DIR / "models"
DATABASE_PATH = MODELS_DIR / "embeddings.json"

# Default SFace Cosine threshold: >= 0.363 means same person.
DEFAULT_THRESHOLD = 0.363


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


def load_database() -> list[dict]:
    if not DATABASE_PATH.exists():
        raise FileNotFoundError(f"Database not found at {DATABASE_PATH}. Please run train_known_faces.py first.")
    
    with DATABASE_PATH.open("r", encoding="utf-8") as f:
        database = json.load(f)
    print(f"Loaded {len(database)} registered profiles from database.")
    return database


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--camera", type=int, default=0)
    parser.add_argument("--threshold", type=float, default=DEFAULT_THRESHOLD, help="Cosine similarity threshold (default: 0.363)")
    args = parser.parse_args()

    # Load database
    try:
        database = load_database()
    except FileNotFoundError as e:
        print(e)
        return

    # Check and download models
    yunet_path, sface_path = check_and_download_models()

    # Initialize YuNet detector
    detector = cv2.FaceDetectorYN.create(
        model=str(yunet_path),
        config="",
        input_size=(320, 320),
        score_threshold=0.9,
        nms_threshold=0.3,
        top_k=5000
    )

    # Initialize SFace recognizer
    recognizer = cv2.FaceRecognizerSF.create(
        model=str(sface_path),
        config=""
    )

    cap = cv2.VideoCapture(args.camera, cv2.CAP_DSHOW)
    if not cap.isOpened():
        cap = cv2.VideoCapture(args.camera)
    if not cap.isOpened():
        raise RuntimeError(f"Cannot open camera {args.camera}")

    cap.set(cv2.CAP_PROP_FRAME_WIDTH, 640)
    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)

    # Pre-read frame to set YuNet input size
    ret, frame = cap.read()
    if ret:
        h, w = frame.shape[:2]
        detector.setInputSize((w, h))

    print(f"\nWebcam test running (threshold: {args.threshold:.3f}). Press q or ESC to exit.")

    while True:
        ret, frame = cap.read()
        if not ret:
            print("Frame read failed")
            break

        h, w = frame.shape[:2]
        detector.setInputSize((w, h))
        retval, faces = detector.detect(frame)

        display = frame.copy()

        if retval and faces is not None:
            for face in faces:
                # Bounding box coordinates
                x, y, fw, fh = map(int, face[0:4])
                
                # Align and crop the detected face
                aligned = recognizer.alignCrop(frame, face)
                
                # Extract face feature embedding (1x128 float array)
                feat = recognizer.feature(aligned)

                best_name = "Unknown"
                best_id = ""
                best_score = -1.0

                # Compare against all database embeddings
                for profile in database:
                    db_emb = np.array(profile["embedding"], dtype=np.float32).reshape(1, 128)
                    
                    # Compute cosine similarity
                    score = recognizer.match(feat, db_emb, cv2.FaceRecognizerSF_FR_COSINE)
                    if score > best_score:
                        best_score = score
                        best_name = profile["name"]
                        best_id = profile["student_id"]

                # Determine if it's a match
                if best_score >= args.threshold:
                    label_text = f"{best_name} | {best_id} ({best_score:.3f})"
                    color = (0, 255, 0) # Green box for known
                else:
                    label_text = f"Unknown ({best_score:.3f})"
                    color = (0, 0, 255) # Red box for unknown

                # Draw bounding box and label
                cv2.rectangle(display, (x, y), (x + fw, y + fh), color, 2)
                cv2.putText(display, label_text, (x, max(30, y - 10)),
                            cv2.FONT_HERSHEY_SIMPLEX, 0.7, color, 2)

                # Draw eye/nose/mouth keypoints
                cv2.circle(display, (int(face[4]), int(face[5])), 2, (255, 0, 0), -1)   # Right eye
                cv2.circle(display, (int(face[6]), int(face[7])), 2, (0, 0, 255), -1)   # Left eye
                cv2.circle(display, (int(face[8]), int(face[9])), 2, (0, 255, 0), -1)   # Nose
                cv2.circle(display, (int(face[10]), int(face[11])), 2, (255, 0, 255), -1) # Right mouth
                cv2.circle(display, (int(face[12]), int(face[13])), 2, (0, 255, 255), -1) # Left mouth

        cv2.imshow("SFace Face Recognition Test", display)
        key = cv2.waitKey(1) & 0xFF
        if key in (ord("q"), 27):
            break

    cap.release()
    cv2.destroyAllWindows()


if __name__ == "__main__":
    main()
