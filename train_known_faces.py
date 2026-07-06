"""
Compute and save SFace embeddings for registered profiles in known_faces/.

Input:
  known_faces/
    <MSV>__<name>/profile.json + *.jpg (aligned color faces)

Output:
  models/embeddings.json (JSON list containing name, student_id, and 128-float embedding)
"""

from __future__ import annotations

import argparse
import json
import urllib.request
from pathlib import Path

import cv2
import numpy as np

PROJECT_DIR = Path(__file__).resolve().parent
KNOWN_DIR = PROJECT_DIR / "known_faces"
MODELS_DIR = PROJECT_DIR / "models"


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


def iter_images(folder: Path):
    for ext in ("*.jpg", "*.jpeg", "*.png", "*.bmp"):
        yield from folder.glob(ext)


def load_profile(person_dir: Path) -> dict[str, str]:
    profile_path = person_dir / "profile.json"
    if profile_path.exists():
        try:
            data = json.loads(profile_path.read_text(encoding="utf-8"))
            return {"name": str(data["name"]), "student_id": str(data["student_id"])}
        except Exception:
            pass
    return {"name": person_dir.name, "student_id": ""}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--data-dir", default=str(KNOWN_DIR))
    parser.add_argument("--model-dir", default=str(MODELS_DIR))
    args = parser.parse_args()

    data_dir = Path(args.data_dir)
    model_dir = Path(args.model_dir)
    model_dir.mkdir(parents=True, exist_ok=True)

    if not data_dir.exists():
        raise FileNotFoundError(f"Missing data folder: {data_dir}")

    # Make sure SFace model exists
    _, sface_path = check_and_download_models()

    # Initialize SFace recognizer
    recognizer = cv2.FaceRecognizerSF.create(
        model=str(sface_path),
        config=""
    )

    person_dirs = [p for p in sorted(data_dir.iterdir()) if p.is_dir()]
    if not person_dirs:
        raise RuntimeError(f"No person folders found in {data_dir}")

    database = []

    for person_dir in person_dirs:
        profile = load_profile(person_dir)
        person_features = []

        for img_path in iter_images(person_dir):
            # Load image using np.fromfile to support Unicode paths
            try:
                img_data = np.fromfile(str(img_path), dtype=np.uint8)
                img = cv2.imdecode(img_data, cv2.IMREAD_COLOR) if img_data.size > 0 else None
                if img is None:
                    continue
                
                # Check if it needs resize (SFace expects 112x112)
                if img.shape[0] != 112 or img.shape[1] != 112:
                    img = cv2.resize(img, (112, 112))

                # Compute feature vector (1x128 float array)
                feat = recognizer.feature(img)
                person_features.append(feat)
            except Exception as e:
                print(f"Error processing {img_path}: {e}")
                continue

        if not person_features:
            print(f"Warning: no usable images for {person_dir.name}")
        else:
            # Average all embeddings for this person to create a representative face signature
            # person_features is a list of shape (1, 128) arrays
            feats_array = np.vstack(person_features) # shape (num_samples, 128)
            avg_feat = np.mean(feats_array, axis=0) # shape (128,)

            # Normalize the average feature vector to unit length
            norm = np.linalg.norm(avg_feat)
            if norm > 0:
                avg_feat = avg_feat / norm

            database.append({
                "name": profile["name"],
                "student_id": profile["student_id"],
                "embedding": avg_feat.tolist()
            })
            print(f"Processed {len(person_features)} images for {profile['name']} ({profile['student_id']})")

    if not database:
        raise RuntimeError("No features computed; cannot save database")

    output_path = model_dir / "embeddings.json"
    output_path.write_text(json.dumps(database, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\nFeature database successfully generated and saved to {output_path}")


if __name__ == "__main__":
    main()
