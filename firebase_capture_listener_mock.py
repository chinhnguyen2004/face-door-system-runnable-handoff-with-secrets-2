"""
Mock listener for the next step before real face recognition.

It waits for:
    /capture_request == true

Then writes a mock recognition result to:
    /recognitions/esp01

Run:
    python firebase_capture_listener_mock.py

Stop with Ctrl+C.
"""

from __future__ import annotations

import json
import time
from pathlib import Path

import firebase_admin
from firebase_admin import credentials, db

PROJECT_DIR = Path(__file__).resolve().parent
SERVICE_ACCOUNT_PATH = PROJECT_DIR / "admin_firebase.json"
DATABASE_URL = "https://face-f49c1-default-rtdb.asia-southeast1.firebasedatabase.app/"
DEVICE_ID = "esp01"
MOCK_RESULT = "TEST_OK"


def init_firebase() -> None:
    with SERVICE_ACCOUNT_PATH.open("r", encoding="utf-8") as f:
        key_info = json.load(f)
    if key_info.get("type") != "service_account" or "private_key" not in key_info:
        raise RuntimeError("admin_firebase.json is not a valid service account key")

    if not firebase_admin._apps:
        cred = credentials.Certificate(str(SERVICE_ACCOUNT_PATH))
        firebase_admin.initialize_app(cred, {"databaseURL": DATABASE_URL})


def main() -> None:
    init_firebase()

    flag_ref = db.reference("/capture_request")
    result_ref = db.reference(f"/recognitions/{DEVICE_ID}")
    status_ref = db.reference("/status/pc_listener")

    status_ref.update({
        "running": True,
        "mode": "mock",
        "updated_at_ms": int(time.time() * 1000),
    })

    print("Mock Firebase listener is running")
    print("Waiting for /capture_request == true")
    print("Press Ctrl+C to stop")

    try:
        while True:
            flag = flag_ref.get()
            if flag is True:
                data = {
                    "result": MOCK_RESULT,
                    "timestamp": {".sv": "timestamp"},
                    "source": "firebase_capture_listener_mock.py",
                }
                result_ref.set(data)
                flag_ref.set(False)
                print("capture_request received -> wrote result TEST_OK and reset flag")
            time.sleep(0.5)
    except KeyboardInterrupt:
        status_ref.update({
            "running": False,
            "stopped_at_ms": int(time.time() * 1000),
        })
        print("Stopped")


if __name__ == "__main__":
    main()
