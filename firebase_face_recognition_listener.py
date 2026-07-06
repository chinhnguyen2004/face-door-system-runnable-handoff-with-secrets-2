"""
Firebase-triggered face recognition listener.

Flow:
  1. Wait for /capture_request == true
  2. Collect 10 frames containing a face (duration is only a timeout)
  3. Write result to /recognitions/esp01 and /history
  4. Reset /capture_request = false

Default model behavior:
  - If known_faces/<person_name> images exist, train an LBPH model from them.
  - Else if lbph_model.xml exists in the project root, load it and use default labels.

Recommended folder layout for training:
  known_faces/
    B21DCCN001__Nguyen Van A/profile.json + *.jpg

Run:
  python firebase_face_recognition_listener.py
"""

from __future__ import annotations

import argparse
import json
import os
import threading
import time
from datetime import datetime
from urllib import error as urlerror
from urllib import request
from collections import Counter
from pathlib import Path
from typing import Iterable

import cv2
import firebase_admin
import numpy as np
from firebase_admin import credentials, db

PROJECT_DIR = Path(__file__).resolve().parent
SERVICE_ACCOUNT_PATH = PROJECT_DIR / "admin_firebase.json"
DATABASE_URL = "https://face-f49c1-default-rtdb.asia-southeast1.firebasedatabase.app/"
DEVICE_ID = "esp01"

DEFAULT_DATA_DIR = PROJECT_DIR / "known_faces"
DEFAULT_MODEL_PATH = PROJECT_DIR / "models" / "lbph_model.xml"
ROOT_MODEL_PATH = PROJECT_DIR / "lbph_model.xml"
DEFAULT_LABELS_PATH = PROJECT_DIR / "models" / "labels.json"
DEFAULT_LABELS = ["Quan", "Tuan Anh"]

FACE_SIZE = (200, 200)
THRESHOLD = 70.0
CAPTURE_DURATION_SEC = 7.0
TARGET_FACE_FRAMES = 10
CAMERA_INDEX = 0
DISCORD_WEBHOOK_URL = os.getenv("DISCORD_WEBHOOK_URL", "").strip()


def normalize_profiles(data) -> list[dict[str, str]]:
    return [
        item if isinstance(item, dict) else {"name": str(item), "student_id": ""}
        for item in data
    ]


def load_profile(person_dir: Path) -> dict[str, str]:
    profile_path = person_dir / "profile.json"
    if profile_path.exists():
        data = json.loads(profile_path.read_text(encoding="utf-8"))
        return {"name": str(data["name"]), "student_id": str(data["student_id"])}
    return {"name": person_dir.name, "student_id": ""}


def require_cv2_face() -> None:
    if not hasattr(cv2, "face"):
        raise RuntimeError(
            "cv2.face is missing. Install opencv-contrib-python: "
            "python -m pip install opencv-contrib-python"
        )


def init_firebase() -> None:
    if not SERVICE_ACCOUNT_PATH.exists():
        raise FileNotFoundError(f"Missing Admin SDK JSON: {SERVICE_ACCOUNT_PATH}")
    if not firebase_admin._apps:
        cred = credentials.Certificate(str(SERVICE_ACCOUNT_PATH))
        firebase_admin.initialize_app(cred, {"databaseURL": DATABASE_URL})


def iter_image_files(folder: Path) -> Iterable[Path]:
    for ext in ("*.jpg", "*.jpeg", "*.png", "*.bmp"):
        yield from folder.glob(ext)


def detect_largest_face_box(gray: np.ndarray, cascade: cv2.CascadeClassifier):
    faces = cascade.detectMultiScale(
        gray,
        scaleFactor=1.2,
        minNeighbors=5,
        minSize=(80, 80),
    )
    if len(faces) == 0:
        equalized = cv2.equalizeHist(gray)
        faces = cascade.detectMultiScale(
            equalized,
            scaleFactor=1.1,
            minNeighbors=4,
            minSize=(60, 60),
        )
    if len(faces) == 0:
        return None
    return max(faces, key=lambda rect: rect[2] * rect[3])


def crop_face_roi(gray: np.ndarray, box) -> np.ndarray:
    x, y, w, h = box
    roi = gray[y : y + h, x : x + w]
    roi = cv2.resize(roi, FACE_SIZE)
    clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8,8))
    roi = clahe.apply(roi)
    return roi


def detect_largest_face(gray: np.ndarray, cascade: cv2.CascadeClassifier) -> np.ndarray | None:
    box = detect_largest_face_box(gray, cascade)
    if box is None:
        return None
    return crop_face_roi(gray, box)


def train_from_folder(data_dir: Path, cascade: cv2.CascadeClassifier):
    labels: list[dict[str, str]] = []
    images: list[np.ndarray] = []
    ids: list[int] = []

    if not data_dir.exists():
        return None, []

    person_dirs = [p for p in sorted(data_dir.iterdir()) if p.is_dir()]
    for person_dir in person_dirs:
        profile = load_profile(person_dir)
        person_images: list[np.ndarray] = []
        for img_path in iter_image_files(person_dir):
            img_data = np.fromfile(str(img_path), dtype=np.uint8)
            img = cv2.imdecode(img_data, cv2.IMREAD_GRAYSCALE) if img_data.size > 0 else None
            if img is None:
                continue
            face = detect_largest_face(img, cascade)
            if face is None:
                face = cv2.resize(img, FACE_SIZE)
                face = cv2.equalizeHist(face)
            person_images.extend((face, cv2.flip(face, 1)))
        if person_images:
            label_id = len(labels) + 1
            images.extend(person_images)
            ids.extend([label_id] * len(person_images))
            labels.append(profile)
            print(f"Loaded {len(person_images)} training images for {profile['name']} ({profile['student_id']})")

    if not images:
        return None, []

    recognizer = cv2.face.LBPHFaceRecognizer_create(radius=2, neighbors=8, grid_x=8, grid_y=8)
    recognizer.train(images, np.array(ids))
    DEFAULT_MODEL_PATH.parent.mkdir(parents=True, exist_ok=True)
    import tempfile, shutil, os
    with tempfile.NamedTemporaryFile(delete=False, suffix=".xml") as tmp:
        tmp_model_path = tmp.name
    recognizer.write(tmp_model_path)
    shutil.move(tmp_model_path, str(DEFAULT_MODEL_PATH))
    DEFAULT_LABELS_PATH.write_text(json.dumps(labels, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Trained and saved model: {DEFAULT_MODEL_PATH}")
    return recognizer, labels


def load_or_train_model(data_dir: Path, cascade: cv2.CascadeClassifier):
    require_cv2_face()

    recognizer = cv2.face.LBPHFaceRecognizer_create()

    import tempfile, shutil, os
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
        return recognizer, labels

    recognizer, labels = train_from_folder(data_dir, cascade)
    if recognizer is not None:
        return recognizer, labels

    recognizer = cv2.face.LBPHFaceRecognizer_create()

    if ROOT_MODEL_PATH.exists():
        read_model_safe(ROOT_MODEL_PATH)
        labels = normalize_profiles(DEFAULT_LABELS)
        print(f"Loaded existing root model: {ROOT_MODEL_PATH}")
        print(f"Using default labels: {labels}")
        return recognizer, labels

    raise RuntimeError(
        "No training images or model found. Create known_faces/<person>/*.jpg "
        "or place models/lbph_model.xml + models/labels.json."
    )


def recognize_once(
    recognizer,
    labels: list[dict[str, str]],
    cascade: cv2.CascadeClassifier,
    camera_index: int,
    duration: float,
    threshold: float,
    target_frames: int,
    show_camera: bool = False,
):
    cap = cv2.VideoCapture(camera_index, cv2.CAP_DSHOW)
    if not cap.isOpened():
        cap = cv2.VideoCapture(camera_index)
    if not cap.isOpened():
        raise RuntimeError(f"Cannot open camera index {camera_index}")

    votes: list[str] = []
    confidences: list[float] = []
    start = time.time()

    window_name = "Face Door Camera Preview"
    last_preview_text = "Dang tim khuon mat..."
    print(f"Scanning for {duration:.1f}s; need {target_frames} valid face frames before decision...")
    if show_camera:
        print("Camera preview is ON. Press q in the preview window to cancel this capture.")

    cancelled = False
    while time.time() - start < duration:
        ret, frame = cap.read()
        if not ret:
            time.sleep(0.05)
            continue

        elapsed = time.time() - start
        remaining = max(0.0, duration - elapsed)
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        box = detect_largest_face_box(gray, cascade)

        if box is None:
            last_preview_text = "Khong thay mat - hay nhin thang camera"
            if show_camera:
                preview = frame.copy()
                cv2.putText(preview, last_preview_text, (20, 35), cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0, 180, 255), 2)
                cv2.putText(preview, f"Frames hop le: {len(votes)}/{target_frames}", (20, 70), cv2.FONT_HERSHEY_SIMPLEX, 0.75, (255, 255, 255), 2)
                cv2.putText(preview, f"Con lai: {remaining:.1f}s", (20, 105), cv2.FONT_HERSHEY_SIMPLEX, 0.75, (255, 255, 255), 2)
                cv2.imshow(window_name, preview)
                if cv2.waitKey(1) & 0xFF == ord("q"):
                    cancelled = True
                    break
            time.sleep(0.03)
            continue

        roi = crop_face_roi(gray, box)
        label_id, conf = recognizer.predict(roi)
        if 1 <= label_id <= len(labels) and conf <= threshold:
            profile = labels[label_id - 1]
            label_text = f"{profile['name']} | {profile.get('student_id', '')}".strip()
            vote_value = json.dumps(profile, ensure_ascii=False, sort_keys=True)
            box_color = (0, 220, 0)
        else:
            label_text = "Unknown"
            vote_value = "Unknown"
            box_color = (0, 0, 255)

        if len(votes) < target_frames:
            votes.append(vote_value)
            confidences.append(float(conf))
            print(f"Face frame {len(votes)}/{target_frames}: {label_text} conf={conf:.1f}")

        last_preview_text = f"{label_text}  conf={conf:.1f}"
        if show_camera:
            preview = frame.copy()
            x, y, w, h = box
            cv2.rectangle(preview, (x, y), (x + w, y + h), box_color, 2)
            cv2.putText(preview, last_preview_text, (x, max(30, y - 10)), cv2.FONT_HERSHEY_SIMPLEX, 0.75, box_color, 2)
            cv2.putText(preview, f"Frames hop le: {len(votes)}/{target_frames}", (20, 35), cv2.FONT_HERSHEY_SIMPLEX, 0.8, (255, 255, 255), 2)
            cv2.putText(preview, f"Con lai: {remaining:.1f}s", (20, 70), cv2.FONT_HERSHEY_SIMPLEX, 0.75, (255, 255, 255), 2)
            cv2.putText(preview, "Can mat trong khung xanh, du anh sang", (20, 105), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 255, 0), 2)
            cv2.imshow(window_name, preview)
            if cv2.waitKey(1) & 0xFF == ord("q"):
                cancelled = True
                break
        time.sleep(0.03)

    if cancelled:
        print("Camera preview cancelled by user.")

    cap.release()
    if show_camera:
        cv2.destroyWindow(window_name)

    if len(votes) < target_frames:
        print(f"Not enough valid frames: {len(votes)}/{target_frames}; returning Unknown")
        return {"name": "Unknown", "student_id": ""}, None, len(votes)
    winner = Counter(votes).most_common(1)[0][0]
    result = {"name": "Unknown", "student_id": ""} if winner == "Unknown" else json.loads(winner)
    avg_conf = sum(confidences) / len(confidences) if confidences else None
    return result, avg_conf, len(votes)


def build_discord_alert(profile: dict[str, str], confidence: float | None, frames: int, source: str) -> dict:
    result = profile["name"]
    student_id = profile.get("student_id", "")
    confidence_text = "N/A" if confidence is None else f"{confidence:.2f}"
    now_text = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    # Keep user-facing text as Unicode escape sequences so Windows editors/shells
    # cannot corrupt Vietnamese accents or emoji into question marks.
    icon_speaker = "\U0001F50A"  # loud speaker
    icon_alarm = "\U0001F6A8"
    icon_lock = "\U0001F512"
    icon_unlock = "\U0001F513"
    icon_door = "\U0001F6AA"
    icon_wave = "\U0001F44B"
    icon_party = "\U0001F389"
    icon_ok = "\u2705"
    icon_student = "\U0001F9D1\u200D\U0001F393"
    icon_id = "\U0001F194"
    icon_camera = "\U0001F4F7"
    icon_chart = "\U0001F4CA"
    icon_clock = "\u23F1\uFE0F"
    icon_device = "\U0001F4DF"

    if result == "Unknown":
        title = f"{icon_speaker} {icon_alarm} C\u1EA3nh b\u00E1o ng\u01B0\u1EDDi l\u1EA1"
        color = 0xFF3B30
        description = (
            f"{icon_lock} Ph\u00E1t hi\u1EC7n khu\u00F4n m\u1EB7t ch\u01B0a \u0111\u0103ng k\u00FD. "
            "C\u1EEDa v\u1EABn kh\u00F3a."
        )
        content = (
            f"{icon_speaker} {icon_alarm} **C\u1EA2NH B\u00C1O NG\u01AF\u1EDCI L\u1EA0**\n"
            f"{icon_camera} H\u1EC7 th\u1ED1ng v\u1EEBa ph\u00E1t hi\u1EC7n: **Unknown**"
        )
        status_icon = icon_lock
        status_text = "T\u1EEB ch\u1ED1i m\u1EDF c\u1EEDa"
    else:
        title = f"{icon_speaker} {icon_wave} Ch\u00E0o m\u1EEBng {result}"
        color = 0x34C759
        description = (
            f"{icon_ok} Nh\u1EADn di\u1EC7n th\u00E0nh c\u00F4ng: **{result}**"
            + (f"\n{icon_id} M\u00E3 sinh vi\u00EAn: **{student_id}**" if student_id else "")
        )
        content = (
            f"{icon_speaker} {icon_party} **CH\u00C0O M\u1EEANG {result.upper()}**\n"
            + (f"{icon_student} Sinh vi\u00EAn | {icon_id} MSV: **{student_id}**" if student_id else f"{icon_student} Kh\u00E1ch \u0111\u00E3 x\u00E1c th\u1EF1c")
        )
        status_icon = icon_unlock
        status_text = "\u0110\u01B0\u1EE3c ph\u00E9p m\u1EDF c\u1EEDa"

    fields = [
        {"name": f"{icon_device} Thi\u1EBFt b\u1ECB", "value": DEVICE_ID, "inline": True},
        {"name": f"{icon_student} T\u00EAn", "value": result, "inline": True},
        {"name": f"{icon_id} M\u00E3 sinh vi\u00EAn", "value": student_id or "-", "inline": True},
        {"name": f"{icon_door} Tr\u1EA1ng th\u00E1i c\u1EEDa", "value": f"{status_icon} {status_text}", "inline": False},
        {"name": f"{icon_camera} S\u1ED1 khung h\u00ECnh", "value": str(frames), "inline": True},
        {"name": f"{icon_chart} \u0110\u1ED9 tin c\u1EADy", "value": confidence_text, "inline": True},
        {"name": f"{icon_clock} Th\u1EDDi gian", "value": now_text, "inline": False},
    ]

    return {
        "username": "Face Door Alert",
        "content": content,
        "embeds": [{
            "title": title,
            "description": description,
            "color": color,
            "fields": fields,
            "footer": {"text": "ESP8266 Firebase Face Door System"},
        }],
    }


def send_discord_alert(webhook_url: str, profile: dict[str, str], confidence: float | None, frames: int, source: str) -> bool:
    if not webhook_url:
        return False

    payload = json.dumps(
        build_discord_alert(profile, confidence, frames, source),
        ensure_ascii=False,
    ).encode("utf-8")
    req = request.Request(
        webhook_url,
        data=payload,
        headers={"Content-Type": "application/json", "User-Agent": "DiscordBot (https://discord.com, 1.0)"},
        method="POST",
    )
    try:
        with request.urlopen(req, timeout=8) as resp:
            return 200 <= resp.status < 300
    except (urlerror.URLError, TimeoutError) as exc:
        print(f"Discord alert failed: {exc}")
        return False


def play_pc_sound(result: str, enabled: bool = True) -> None:
    """Play a short Windows melody on the PC running this listener."""
    if not enabled:
        return

    def worker() -> None:
        try:
            import winsound

            if result == "Unknown":
                # Loud warning pattern: high-low siren, repeated.
                melody = [
                    (1200, 220), (700, 220),
                    (1200, 220), (700, 220),
                    (1500, 350), (500, 450),
                ]
            else:
                # Welcome melody: short rising tune.
                melody = [
                    (523, 180), (659, 180), (784, 220),
                    (1047, 320), (784, 180), (1047, 420),
                ]

            for frequency, duration_ms in melody:
                winsound.Beep(frequency, duration_ms)
                time.sleep(0.04)
        except Exception as exc:
            # Sound is optional; do not break Firebase/Discord flow if audio fails.
            print(f"PC sound skipped: {exc}")

    threading.Thread(target=worker, daemon=True).start()


def write_result(
    profile: dict[str, str],
    confidence: float | None,
    frames: int,
    source: str,
    discord_webhook_url: str = "",
    notify_known: bool = False,
    sound_enabled: bool = True,
) -> None:
    result = profile["name"]
    payload = {
        "result": result,
        "student_id": profile.get("student_id", ""),
        "display_label": f"{result} | {profile['student_id']}" if profile.get("student_id") else result,
        "confidence": confidence,
        "frames": frames,
        "source": source,
        "timestamp": {".sv": "timestamp"},
    }
    db.reference(f"/recognitions/{DEVICE_ID}").set(payload)
    db.reference("/history").push(payload)
    db.reference("/status/pc_listener").update({
        "running": True,
        "mode": "face_recognition",
        "last_result": result,
        "last_frames": frames,
        "updated_at_ms": int(time.time() * 1000),
    })

    should_notify = result == "Unknown" or notify_known or source.startswith("error:")
    if should_notify:
        play_pc_sound(result, sound_enabled)
    if should_notify and discord_webhook_url:
        sent = send_discord_alert(discord_webhook_url, profile, confidence, frames, source)
        db.reference("/status/pc_listener").update({
            "discord_last_sent": sent,
            "discord_last_sent_at_ms": int(time.time() * 1000),
        })


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--data-dir", default=str(DEFAULT_DATA_DIR), help="Folder containing known_faces/<person> images")
    parser.add_argument("--camera", type=int, default=CAMERA_INDEX)
    parser.add_argument("--duration", type=float, default=CAPTURE_DURATION_SEC)
    parser.add_argument("--threshold", type=float, default=THRESHOLD)
    parser.add_argument("--frames", type=int, default=TARGET_FACE_FRAMES, help="Face frames required before deciding")
    parser.add_argument("--discord-webhook", default=DISCORD_WEBHOOK_URL, help="Discord webhook URL, or set DISCORD_WEBHOOK_URL")
    parser.add_argument("--notify-known", action="store_true", help="Also send Discord messages for recognized known faces")
    parser.add_argument("--no-sound", action="store_true", help="Disable PC speaker melodies for alerts/welcome")
    parser.add_argument("--show-camera", action="store_true", help="Show webcam preview with face box while recognizing")
    parser.add_argument("--standalone", action="store_true", help="Run camera continuously without waiting for Firebase trigger")
    parser.add_argument("--cooldown", type=float, default=5.0, help="Seconds between recognitions in standalone mode")
    args = parser.parse_args()
    if args.frames < 1:
        parser.error("--frames must be at least 1")


    init_firebase()
    cascade = cv2.CascadeClassifier(cv2.data.haarcascades + "haarcascade_frontalface_default.xml")
    if cascade.empty():
        raise RuntimeError("Cannot load Haar cascade")

    recognizer, labels = load_or_train_model(Path(args.data_dir), cascade)
    print(f"Labels: {labels}")

    # ---- STANDALONE MODE: Camera opens immediately and scans continuously ----
    if args.standalone:
        print("[STANDALONE] Camera is opening now. Scanning continuously. Ctrl+C to stop.")
        cap = cv2.VideoCapture(args.camera, cv2.CAP_DSHOW)
        if not cap.isOpened():
            cap = cv2.VideoCapture(args.camera)
        if not cap.isOpened():
            raise RuntimeError(f"Cannot open camera {args.camera}")

        window_name = "Face Door - Standalone"
        last_result_time = 0.0
        flag_ref = db.reference("/capture_request")
        try:
            while True:
                ret, frame = cap.read()
                if not ret:
                    time.sleep(0.05)
                    continue

                gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
                box = detect_largest_face_box(gray, cascade)
                now = time.time()
                cooldown_ok = (now - last_result_time) >= args.cooldown

                display = frame.copy()
                if box is not None:
                    x, y, w, h = box
                    roi = crop_face_roi(gray, box)
                    label_id, conf = recognizer.predict(roi)
                    if 1 <= label_id <= len(labels) and conf <= args.threshold:
                        profile = labels[label_id - 1]
                        label_text = f"{profile['name']} | {profile.get('student_id','')}"
                        box_color = (0, 220, 0)
                        if cooldown_ok:
                            write_result(profile, float(conf), 1, "standalone",
                                         args.discord_webhook, args.notify_known, not args.no_sound)
                            flag_ref.set(False)
                            last_result_time = now
                            print(f"[STANDALONE] Recognized: {label_text} conf={conf:.1f}")
                    else:
                        label_text = f"Unknown ({conf:.0f})"
                        box_color = (0, 0, 255)
                    cv2.rectangle(display, (x, y), (x+w, y+h), box_color, 2)
                    cv2.putText(display, label_text, (x, max(30, y-10)),
                                cv2.FONT_HERSHEY_SIMPLEX, 0.8, box_color, 2)
                else:
                    cv2.putText(display, "No face detected", (20, 40),
                                cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0, 180, 255), 2)

                remaining_cd = max(0.0, args.cooldown - (now - last_result_time))
                cv2.putText(display, f"Cooldown: {remaining_cd:.1f}s" if remaining_cd > 0 else "Ready",
                            (20, 75), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 255, 0), 2)
                cv2.imshow(window_name, display)
                if cv2.waitKey(1) & 0xFF in (ord("q"), 27):
                    break
                time.sleep(0.03)
        except KeyboardInterrupt:
            pass
        finally:
            cap.release()
            cv2.destroyAllWindows()
            db.reference("/status/pc_listener").update({"running": False})
            print("[STANDALONE] Stopped.")
        return

    # ---- FIREBASE TRIGGER MODE (default): Wait for /capture_request == true ----
    print("Firebase face-recognition listener running")
    print("Waiting for /capture_request == true. Ctrl+C to stop.")

    flag_ref = db.reference("/capture_request")
    try:
        while True:
            if flag_ref.get() is True:
                try:
                    profile, conf, frames = recognize_once(
                        recognizer, labels, cascade, args.camera,
                        args.duration, args.threshold, args.frames, args.show_camera,
                    )
                    write_result(profile, conf, frames,
                                 "firebase_face_recognition_listener.py",
                                 args.discord_webhook, args.notify_known, not args.no_sound)
                    print(f"Result={profile['name']} MSV={profile.get('student_id', '')} confidence={conf} frames={frames}")
                except Exception as exc:
                    write_result({"name": "Unknown", "student_id": ""}, None, 0,
                                 f"error: {exc}", args.discord_webhook, True, not args.no_sound)
                    print(f"Recognition error: {exc}")
                finally:
                    flag_ref.set(False)
            time.sleep(0.5)
    except KeyboardInterrupt:
        db.reference("/status/pc_listener").update({
            "running": False,
            "stopped_at_ms": int(time.time() * 1000),
        })
        print("Stopped")


if __name__ == "__main__":
    main()


