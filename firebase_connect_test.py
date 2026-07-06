"""
Firebase Realtime Database connection test for the face-f49c1 project.

This script uses Firebase Admin SDK credentials from:
    admin_firebase.json

It writes only a small heartbeat under:
    /status/pc

It also makes sure the required project nodes exist:
    /capture_request
    /recognitions/esp01

Run:
    python firebase_connect_test.py
"""

from __future__ import annotations

import json
import socket
import time
from datetime import datetime, timezone
from pathlib import Path

import firebase_admin
from firebase_admin import credentials, db

PROJECT_DIR = Path(__file__).resolve().parent
SERVICE_ACCOUNT_PATH = PROJECT_DIR / "admin_firebase.json"
DATABASE_URL = "https://face-f49c1-default-rtdb.asia-southeast1.firebasedatabase.app/"
DEVICE_ID = "esp01"


def init_firebase() -> None:
    if not SERVICE_ACCOUNT_PATH.exists():
        raise FileNotFoundError(f"Missing Firebase Admin key: {SERVICE_ACCOUNT_PATH}")

    # Validate without printing private key.
    with SERVICE_ACCOUNT_PATH.open("r", encoding="utf-8") as f:
        key_info = json.load(f)
    if key_info.get("type") != "service_account" or "private_key" not in key_info:
        raise RuntimeError("admin_firebase.json is not a valid Firebase Admin service account key")

    if not firebase_admin._apps:
        cred = credentials.Certificate(str(SERVICE_ACCOUNT_PATH))
        firebase_admin.initialize_app(cred, {"databaseURL": DATABASE_URL})


def main() -> None:
    init_firebase()

    now = datetime.now(timezone.utc).isoformat()
    hostname = socket.gethostname()

    heartbeat = {
        "connected": True,
        "hostname": hostname,
        "updated_at_iso": now,
        "updated_at_ms": int(time.time() * 1000),
        "database_url": DATABASE_URL,
    }

    # Safe status write for the PC/Python side.
    db.reference("/status/pc").update(heartbeat)

    # Create expected nodes if missing, without destroying existing data.
    capture_ref = db.reference("/capture_request")
    if capture_ref.get() is None:
        capture_ref.set(False)

    recog_ref = db.reference(f"/recognitions/{DEVICE_ID}")
    current_recog = recog_ref.get()
    if current_recog is None:
        recog_ref.set({
            "result": "WAITING",
            "timestamp": {".sv": "timestamp"},
            "source": "firebase_connect_test.py",
        })

    print("Firebase connected successfully")
    print(f"Database URL: {DATABASE_URL}")
    print("Wrote heartbeat to: /status/pc")
    print("Checked nodes:")
    print("  /capture_request")
    print(f"  /recognitions/{DEVICE_ID}")


if __name__ == "__main__":
    main()

