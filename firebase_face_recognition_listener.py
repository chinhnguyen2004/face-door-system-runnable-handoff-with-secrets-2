"""
Firebase-triggered face recognition listener using YuNet + SFace.

Flow:
  1. Wait for /capture_request == true
  2. Collect 10 frames containing a face (duration is only a timeout)
  3. Write result to /recognitions/esp01 and /history
  4. Reset /capture_request = false

Recommended folder layout:
  known_faces/
    <MSV>__<name>/profile.json + *.jpg (aligned color faces)

Run:
  python firebase_face_recognition_listener.py
"""

from __future__ import annotations

import argparse
import json
import os
import threading
import time
import urllib.request
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
MODELS_DIR = PROJECT_DIR / "models"
DATABASE_PATH = MODELS_DIR / "embeddings.json"

DEFAULT_THRESHOLD = 0.363
CAPTURE_DURATION_SEC = 7.0
TARGET_FACE_FRAMES = 10
CAMERA_INDEX = 0
DISCORD_WEBHOOK_URL = os.getenv("DISCORD_WEBHOOK_URL", "").strip()


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


def init_firebase() -> None:
    if not SERVICE_ACCOUNT_PATH.exists():
        raise FileNotFoundError(f"Missing Admin SDK JSON: {SERVICE_ACCOUNT_PATH}")
    if not firebase_admin._apps:
        cred = credentials.Certificate(str(SERVICE_ACCOUNT_PATH))
        firebase_admin.initialize_app(cred, {"databaseURL": DATABASE_URL})


def load_database() -> list[dict]:
    if not DATABASE_PATH.exists():
        raise FileNotFoundError(
            f"Database not found at {DATABASE_PATH}. "
            "Please run train_known_faces.py first to compute embeddings."
        )
    with DATABASE_PATH.open("r", encoding="utf-8") as f:
        return json.load(f)


def recognize_once(
    detector: cv2.FaceDetectorYN,
    recognizer: cv2.FaceRecognizerSF,
    database: list[dict],
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

    cap.set(cv2.CAP_PROP_FRAME_WIDTH, 640)
    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)

    # Pre-read frame to set input size
    ret, frame = cap.read()
    if ret:
        h, w = frame.shape[:2]
        detector.setInputSize((w, h))

    votes: list[str] = []
    scores: list[float] = []
    start = time.time()

    window_name = "Face Door Camera Preview"
    print(f"Scanning for {duration:.1f}s; need {target_frames} valid face frames before decision...")
    if show_camera:
        print("Camera preview is ON. Press q in the preview window to cancel.")

    cancelled = False
    while time.time() - start < duration:
        ret, frame = cap.read()
        if not ret:
            time.sleep(0.05)
            continue

        elapsed = time.time() - start
        remaining = max(0.0, duration - elapsed)
        
        h, w = frame.shape[:2]
        detector.setInputSize((w, h))
        retval, faces = detector.detect(frame)

        display = frame.copy()
        largest_face = None

        if retval and faces is not None:
            # Sort to get the largest face
            faces_list = list(faces)
            faces_list.sort(key=lambda f: f[2] * f[3], reverse=True)
            largest_face = faces_list[0]

        if largest_face is None:
            if show_camera:
                cv2.putText(display, "Khong thay mat - hay nhin thang camera", (20, 35), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 180, 255), 2)
                cv2.putText(display, f"Frames hop le: {len(votes)}/{target_frames}", (20, 70), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 255, 255), 2)
                cv2.putText(display, f"Con lai: {remaining:.1f}s", (20, 105), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 255, 255), 2)
                cv2.imshow(window_name, display)
                if cv2.waitKey(1) & 0xFF == ord("q"):
                    cancelled = True
                    break
            time.sleep(0.03)
            continue

        # Extract embedding
        aligned = recognizer.alignCrop(frame, largest_face)
        feat = recognizer.feature(aligned)

        best_name = "Unknown"
        best_profile = {"name": "Unknown", "student_id": ""}
        best_score = -1.0

        for profile in database:
            db_emb = np.array(profile["embedding"], dtype=np.float32).reshape(1, 128)
            score = recognizer.match(feat, db_emb, cv2.FaceRecognizerSF_FR_COSINE)
            if score > best_score:
                best_score = score
                best_name = profile["name"]
                best_profile = {"name": profile["name"], "student_id": profile["student_id"]}

        # Decide if match
        is_known = best_score >= threshold
        if is_known:
            vote_value = json.dumps(best_profile, ensure_ascii=False, sort_keys=True)
            label_text = f"{best_name} ({best_score:.2f})"
            box_color = (0, 220, 0)
        else:
            vote_value = "Unknown"
            label_text = f"Unknown ({best_score:.2f})"
            box_color = (0, 0, 255)

        if len(votes) < target_frames:
            votes.append(vote_value)
            scores.append(float(best_score))
            print(f"Face frame {len(votes)}/{target_frames}: {label_text}")

        if show_camera:
            x, y, fw, fh = map(int, largest_face[0:4])
            cv2.rectangle(display, (x, y), (x + fw, y + fh), box_color, 2)
            cv2.putText(display, label_text, (x, max(30, y - 10)), cv2.FONT_HERSHEY_SIMPLEX, 0.7, box_color, 2)
            cv2.putText(display, f"Frames hop le: {len(votes)}/{target_frames}", (20, 35), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 255, 255), 2)
            cv2.putText(display, f"Con lai: {remaining:.1f}s", (20, 70), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 255, 255), 2)
            cv2.imshow(window_name, display)
            if cv2.waitKey(1) & 0xFF == ord("q"):
                cancelled = True
                break
        time.sleep(0.03)

    cap.release()
    if show_camera:
        cv2.destroyWindow(window_name)

    if len(votes) < target_frames:
        print(f"Not enough valid frames: {len(votes)}/{target_frames}; returning Unknown")
        return {"name": "Unknown", "student_id": ""}, None, len(votes)

    winner = Counter(votes).most_common(1)[0][0]
    result = {"name": "Unknown", "student_id": ""} if winner == "Unknown" else json.loads(winner)
    avg_score = sum(scores) / len(scores) if scores else None
    return result, avg_score, len(votes)


def build_discord_alert(profile: dict[str, str], confidence: float | None, frames: int, source: str) -> dict:
    result = profile["name"]
    student_id = profile.get("student_id", "")
    confidence_text = "N/A" if confidence is None else f"{confidence:.3f}"
    now_text = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    icon_speaker = "\U0001F50A"
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
        description = f"{icon_lock} Ph\u00E1t hi\u1EC7n khu\u00F4n m\u1EB7t ch\u01B0a \u0111\u0103ng k\u00FD. C\u1EEDa v\u1EABn kh\u00F3a."
        content = f"{icon_speaker} {icon_alarm} **C\u1EA2NH B\u00C1O NG\u01AF\u1EDCI L\u1EA0**\n{icon_camera} H\u1EC7 th\u1ED1ng v\u1EEBa ph\u00E1t hi\u1EC7n: **Unknown**"
        status_icon = icon_lock
        status_text = "T\u1EEB ch\u1ED1i m\u1EDF c\u1EEDa"
    else:
        title = f"{icon_speaker} {icon_wave} Ch\u00E0o m\u1EEBng {result}"
        color = 0x34C759
        description = f"{icon_ok} Nh\u1EADn di\u1EC7n th\u00E0nh c\u00F4ng: **{result}**" + (f"\n{icon_id} M\u00E3 sinh vi\u00EAn: **{student_id}**" if student_id else "")
        content = f"{icon_speaker} {icon_party} **CH\u00C0O M\u1EEANG {result.upper()}**\n" + (f"{icon_student} Sinh vi\u00EAn | {icon_id} MSV: **{student_id}**" if student_id else f"{icon_student} Kh\u00E1ch \u0111\u00E3 x\u00E1c th\u1EF1c")
        status_icon = icon_unlock
        status_text = "\u0110\u01B0\u1EE3c ph\u00E9p m\u1EDF c\u1EEDa"

    fields = [
        {"name": f"{icon_device} Thi\u1EBFt b\u1ECB", "value": DEVICE_ID, "inline": True},
        {"name": f"{icon_student} T\u00EAn", "value": result, "inline": True},
        {"name": f"{icon_id} M\u00E3 sinh vi\u00EAn", "value": student_id or "-", "inline": True},
        {"name": f"{icon_door} Tr\u1EA1ng th\u00E1i c\u1EEDa", "value": f"{status_icon} {status_text}", "inline": False},
        {"name": f"{icon_camera} S\u1ED1 khung h\u00ECnh", "value": str(frames), "inline": True},
        {"name": f"{icon_chart} Cosine similarity", "value": confidence_text, "inline": True},
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
    if not enabled:
        return

    def worker() -> None:
        try:
            import winsound
            if result == "Unknown":
                melody = [
                    (1200, 220), (700, 220),
                    (1200, 220), (700, 220),
                    (1500, 350), (500, 450),
                ]
            else:
                melody = [
                    (523, 180), (659, 180), (784, 220),
                    (1047, 320), (784, 180), (1047, 420),
                ]
            for frequency, duration_ms in melody:
                winsound.Beep(frequency, duration_ms)
                time.sleep(0.04)
        except Exception as exc:
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
    parser.add_argument("--threshold", type=float, default=DEFAULT_THRESHOLD)
    parser.add_argument("--frames", type=int, default=TARGET_FACE_FRAMES, help="Face frames required before deciding")
    parser.add_argument("--discord-webhook", default=DISCORD_WEBHOOK_URL, help="Discord webhook URL, or set DISCORD_WEBHOOK_URL")
    parser.add_argument("--notify-known", action="store_true", help="Also send Discord messages for recognized known faces")
    parser.add_argument("--no-sound", action="store_true", help="Disable PC speaker melodies for alerts/welcome")
    parser.add_argument("--show-camera", action="store_true", help="Show webcam preview with face box while recognizing")
    parser.add_argument("--standalone", action="store_true", help="Run camera continuously without waiting for Firebase trigger")
    parser.add_argument("--cooldown", type=float, default=5.0, help="Seconds between recognitions in standalone mode")
    args = parser.parse_args()

    # Defensive check: if the user supplies an old threshold (like 70), fallback to default Cosine threshold
    if args.threshold > 1.0:
        print(f"[Warning] Supplied threshold {args.threshold} is not valid for Cosine Similarity. Resetting to {DEFAULT_THRESHOLD}")
        args.threshold = DEFAULT_THRESHOLD

    if args.frames < 1:
        parser.error("--frames must be at least 1")

    init_firebase()
    yunet_path, sface_path = check_and_download_models()

    # Load database
    try:
        database = load_database()
    except FileNotFoundError as e:
        print(e)
        return

    # Initialize YuNet
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

    print(f"Loaded SFace database with {len(database)} profiles.")

    # ---- STANDALONE MODE: Camera opens immediately and scans continuously ----
    if args.standalone:
        print("[STANDALONE] Camera is opening now. Scanning continuously. Ctrl+C to stop.")
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

        window_name = "Face Door - Standalone"
        last_result_time = 0.0
        flag_ref = db.reference("/capture_request")
        try:
            while True:
                ret, frame = cap.read()
                if not ret:
                    time.sleep(0.05)
                    continue

                h, w = frame.shape[:2]
                detector.setInputSize((w, h))
                retval, faces = detector.detect(frame)

                now = time.time()
                cooldown_ok = (now - last_result_time) >= args.cooldown

                display = frame.copy()
                largest_face = None

                if retval and faces is not None:
                    faces_list = list(faces)
                    faces_list.sort(key=lambda f: f[2] * f[3], reverse=True)
                    largest_face = faces_list[0]

                if largest_face is not None:
                    # Align and match
                    aligned = recognizer.alignCrop(frame, largest_face)
                    feat = recognizer.feature(aligned)

                    best_name = "Unknown"
                    best_profile = {"name": "Unknown", "student_id": ""}
                    best_score = -1.0

                    for profile in database:
                        db_emb = np.array(profile["embedding"], dtype=np.float32).reshape(1, 128)
                        score = recognizer.match(feat, db_emb, cv2.FaceRecognizerSF_FR_COSINE)
                        if score > best_score:
                            best_score = score
                            best_name = profile["name"]
                            best_profile = {"name": profile["name"], "student_id": profile["student_id"]}

                    is_known = best_score >= args.threshold
                    if is_known:
                        label_text = f"{best_name} ({best_score:.2f})"
                        box_color = (0, 220, 0)
                        if cooldown_ok:
                            write_result(best_profile, float(best_score), 1, "standalone",
                                         args.discord_webhook, args.notify_known, not args.no_sound)
                            flag_ref.set(False)
                            last_result_time = now
                            print(f"[STANDALONE] Recognized: {label_text}")
                    else:
                        label_text = f"Unknown ({best_score:.2f})"
                        box_color = (0, 0, 255)
                        if cooldown_ok and best_score >= 0.15: # only trigger unknown notification for actual faces, not random noise
                            write_result(best_profile, float(best_score), 1, "standalone",
                                         args.discord_webhook, args.notify_known, not args.no_sound)
                            last_result_time = now
                            print(f"[STANDALONE] Recognized Unknown")

                    x, y, fw, fh = map(int, largest_face[0:4])
                    cv2.rectangle(display, (x, y), (x+fw, y+fh), box_color, 2)
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
                    profile, score, frames = recognize_once(
                        detector, recognizer, database, args.camera,
                        args.duration, args.threshold, args.frames, args.show_camera
                    )
                    write_result(profile, score, frames,
                                 "firebase_face_recognition_listener.py",
                                 args.discord_webhook, args.notify_known, not args.no_sound)
                    print(f"Result={profile['name']} MSV={profile.get('student_id', '')} score={score} frames={frames}")
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
