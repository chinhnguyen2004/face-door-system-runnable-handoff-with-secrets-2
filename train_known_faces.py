"""
Train an LBPH face recognizer from known_faces/<person> images.

Input:
  known_faces/
    B21DCCN001__Nguyen Van A/profile.json + *.jpg

Output:
  models/lbph_model.xml
  models/labels.json

Run:
  python train_known_faces.py
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import tempfile
import shutil

import cv2
import numpy as np

PROJECT_DIR = Path(__file__).resolve().parent
DEFAULT_DATA_DIR = PROJECT_DIR / "known_faces"
DEFAULT_MODEL_DIR = PROJECT_DIR / "models"
FACE_SIZE = (200, 200)


def require_cv2_face() -> None:
    if not hasattr(cv2, "face"):
        raise RuntimeError("cv2.face missing. Install: python -m pip install opencv-contrib-python")


def iter_images(folder: Path):
    for ext in ("*.jpg", "*.jpeg", "*.png", "*.bmp"):
        yield from folder.glob(ext)


def load_profile(person_dir: Path) -> dict[str, str]:
    profile_path = person_dir / "profile.json"
    if profile_path.exists():
        data = json.loads(profile_path.read_text(encoding="utf-8"))
        return {"name": str(data["name"]), "student_id": str(data["student_id"])}
    return {"name": person_dir.name, "student_id": ""}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--data-dir", default=str(DEFAULT_DATA_DIR))
    parser.add_argument("--model-dir", default=str(DEFAULT_MODEL_DIR))
    args = parser.parse_args()

    require_cv2_face()
    data_dir = Path(args.data_dir)
    model_dir = Path(args.model_dir)
    model_dir.mkdir(parents=True, exist_ok=True)

    if not data_dir.exists():
        raise FileNotFoundError(f"Missing data folder: {data_dir}")

    images: list[np.ndarray] = []
    ids: list[int] = []
    labels: list[dict[str, str]] = []

    person_dirs = [p for p in sorted(data_dir.iterdir()) if p.is_dir()]
    if not person_dirs:
        raise RuntimeError(f"No person folders found in {data_dir}")

    for person_dir in person_dirs:
        profile = load_profile(person_dir)
        person_images: list[np.ndarray] = []
        for img_path in iter_images(person_dir):
            # cv2.imread không đọc được đường dẫn có dấu tiếng Việt trên Windows, dùng np.fromfile + cv2.imdecode thay thế
            img_data = np.fromfile(str(img_path), dtype=np.uint8)
            img = cv2.imdecode(img_data, cv2.IMREAD_GRAYSCALE) if img_data.size > 0 else None
            if img is None:
                print(f"Skip unreadable: {img_path}")
                continue
            img = cv2.resize(img, FACE_SIZE)
            
            # 1. CLAHE (Contrast Limited Adaptive Histogram Equalization) - Cân bằng sáng tốt hơn cho khuôn mặt
            clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8,8))
            img_clahe = clahe.apply(img)
            
            # 2. Bilateral Filter - Khử nhiễu giữ đường nét khuôn mặt
            img_bilateral = cv2.bilateralFilter(img_clahe, d=5, sigmaColor=50, sigmaSpace=50)
            
            # 3. Gaussian Blur - Khử nhiễu hạt nhẹ
            img_blur = cv2.GaussianBlur(img_clahe, (3, 3), 0)
            
            # Data Augmentation: Thêm ảnh đã xử lý nhiễu và phiên bản lật ngược (flip) để tăng cường dữ liệu
            person_images.extend((
                img_clahe, cv2.flip(img_clahe, 1),
                img_bilateral, cv2.flip(img_bilateral, 1),
                img_blur, cv2.flip(img_blur, 1)
            ))

        if not person_images:
            print(f"Warning: no usable images for {person_dir.name}")
        else:
            label_id = len(labels) + 1
            images.extend(person_images)
            ids.extend([label_id] * len(person_images))
            labels.append(profile)
            print(f"Loaded {len(person_images)} samples for {profile['name']} ({profile['student_id']})")

    if not images:
        raise RuntimeError("No images loaded; cannot train")

    recognizer = cv2.face.LBPHFaceRecognizer_create(radius=2, neighbors=8, grid_x=8, grid_y=8)
    recognizer.train(images, np.array(ids))

    model_path = model_dir / "lbph_model.xml"
    labels_path = model_dir / "labels.json"
    
    # Lưu ra file tạm trước để tránh lỗi thư viện OpenCV không hiểu được đường dẫn tiếng Việt
    with tempfile.NamedTemporaryFile(delete=False, suffix=".xml") as tmp:
        tmp_model_path = tmp.name
    recognizer.write(tmp_model_path)
    shutil.move(tmp_model_path, str(model_path))
    
    labels_path.write_text(json.dumps(labels, ensure_ascii=False, indent=2), encoding="utf-8")

    print("Training complete")
    print(f"Model: {model_path}")
    print(f"Labels: {labels_path}")
    print(f"Profiles: {labels}")


if __name__ == "__main__":
    main()
