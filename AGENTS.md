# AGENT ONBOARDING GUIDE (`AGENTS.md`)

This document is designed to help future AI coding agents quickly onboard, understand the codebase architecture, and continue development/debugging of the AI Face Door System.

---

## 1. PROJECT OVERVIEW & ARCHITECTURE

The system is a smart door lock powered by Face Recognition (OpenCV YuNet + SFace) and an ESP8266 NodeMCU micro-controller. 

```
[Webcam / PC Camera] ──► [Python AI Script]
                                │ (reads/writes states via Internet)
                                ▼
                       [Firebase RTDB] ◄──► [ESP8266 Board] ──► [LCD, Servo, LEDs]
                                │
                                ▼
                        [Discord Bot Webhook]
```

### Technology Stack
* **Microcontroller Firmware:** Arduino C++ (ESP8266 core).
* **AI Engine:** Python 3.11 with OpenCV (DNN Module), NumPy.
* **Database:** Firebase Realtime Database (using REST API in Python and `Firebase_ESP_Client` in C++).
* **Alert System:** Discord Webhook API.

---

## 2. HARDWARE PIN MAPPING (ESP8266 NodeMCU Lolin v3)

All components are wired on a breadboard. Here is the pin map configured in [integrated_firebase_door.ino](file:///C:/Users/Admin/Desktop/faid/face-door-system-runnable-handoff-with-secrets%202/temp/integrated_firebase_door/integrated_firebase_door.ino):

| Pin Name | GPIO Num | Connected Device | Mode | Active State | Description |
| :--- | :--- | :--- | :--- | :--- | :--- |
| `D0` | GPIO16 | **Servo Motor Signal** | OUTPUT | N/A | Controls MG90S/SG90 servo rotation (0° to 90°). |
| `D1` | GPIO5 | **LCD I2C SCL** | OUTPUT | N/A | I2C clock line for 16x2 LCD. |
| `D2` | GPIO4 | **LCD I2C SDA** | I/O | N/A | I2C data line for 16x2 LCD. |
| `D3` | GPIO0 | **LED Success (Green)** | OUTPUT | HIGH | Lights up when a registered student is matched. |
| `D4` | GPIO2 | **LED Fail (Red)** | OUTPUT | HIGH | Lights up when face is "Unknown" or auth fails. |
| `D5` | GPIO14 | **Ultrasonic TRIG** | OUTPUT | HIGH | Triggers the HC-SR04 sonar pulse. |
| `D6` | GPIO12 | **Ultrasonic ECHO** | INPUT | HIGH | Measures the HC-SR04 sonar echo duration. |

---

## 3. DATABASE SCHEMAS (Firebase RTDB Paths)

The database communicates status using the following Realtime Database JSON paths:

```json
{
  "capture_request": false,               // Boolean: Set true by ESP8266 (distance < 50cm) to request PC scan
  "status": {
    "esp01": {
      "distance_cm": 32.6,               // Float: Sonar distance measurement
      "doorOpen": false,                 // Boolean: Current door open/closed status
      "lastSeenMs": 945851355,           // Integer: ESP8266 local uptime in milliseconds (heartbeat)
      "message": "Capture requested"     // String: Device debug message
    },
    "pc_listener": {
      "running": true,                   // Boolean: Python script online status
      "timestamp": 1720311245000         // Integer: Last active timestamp from PC
    }
  },
  "recognitions": {
    "esp01": {
      "result": "nguyen tien chinh",     // String: Name of recognized face or "Unknown"
      "student_id": "20210001",          // String: Student ID or empty
      "display_label": "chinh | 20210001",// String: Label shown on LCD / Discord
      "confidence": 0.524,               // Float: Cosine similarity score
      "frames": 5,                       // Integer: Number of frames voted
      "source": "standalone",            // String: "standalone" or "firebase"
      "timestamp": 946184803             // Integer: Server timestamp (used by ESP to detect new changes)
    }
  }
}
```

---

## 4. AI PIPELINE & MODELS

* **Face Detection:** YuNet (`models/face_detection_yunet_2023mar.onnx`). Very fast, operates well in low-light and handles side profile rotations.
* **Face Embedding:** SFace (`models/face_recognition_sface_2021dec.onnx`). Generates a 128-dimensional float signature.
* **Matching Algorithm:** Cosine Similarity comparison against the registered profiles database.
* **Database Format:** Average embeddings are stored in [models/embeddings.json](file:///C:/Users/Admin/Desktop/faid/face-door-system-runnable-handoff-with-secrets%202/models/embeddings.json):
  ```json
  [
    {
      "name": "nguyen tien chinh",
      "student_id": "2021601234",
      "embedding": [0.012, -0.045, ... 128 items]
    }
  ]
  ```
* **Thresholds:** A Cosine similarity score $\ge 0.36$ represents a positive match. Anything below is treated as `Unknown`.

---

## 5. REPOSITORY CODE STRUCTURE

* [capture_known_face.py](file:///C:/Users/Admin/Desktop/faid/face-door-system-runnable-handoff-with-secrets%202/capture_known_face.py): Captures and saves 10 aligned color face images (112x112 px) using YuNet crop alignment. Handles Vietnamese unicode paths.
* [train_known_faces.py](file:///C:/Users/Admin/Desktop/faid/face-door-system-runnable-handoff-with-secrets%202/train_known_faces.py): Processes folders inside `known_faces/`, generates average SFace embeddings, and writes to `models/embeddings.json`.
* [firebase_face_recognition_listener.py](file:///C:/Users/Admin/Desktop/faid/face-door-system-runnable-handoff-with-secrets%202/firebase_face_recognition_listener.py): The main listener script. Supports two modes:
  * **Firebase Trigger Mode:** Listens for `capture_request == True` from Firebase, captures `args.frames` (default 10) to vote, writes the voted result back to `/recognitions/esp01`, and sets `capture_request = False`.
  * **Standalone Mode (`--standalone`):** Opens the webcam continuously. Scans continuously. Accumulates `args.frames` (configured via CMD to 5) face matches, performs a majority vote, writes the result to Firebase/Discord, and triggers a cooldown. Automatically resets if no face is seen for 2 seconds.
* [test_face_recognition_webcam.py](file:///C:/Users/Admin/Desktop/faid/face-door-system-runnable-handoff-with-secrets%202/test_face_recognition_webcam.py): A simple local camera test to display face detection bounding boxes and cosine similarity scores on the video preview (does not write to Firebase).
* [run_face_listener_discord.cmd](file:///C:/Users/Admin/Desktop/faid/face-door-system-runnable-handoff-with-secrets%202/run_face_listener_discord.cmd): The main interactive console launcher for the system. Options:
  1. Start Main Listener (Standalone mode, `frames=5`, `cooldown=5`, hooks up to Discord bot webhook).
  2. Capture Face.
  3. Train Model.
  4. Test Webcam.

---

## 6. CRITICAL LESSONS LEARNED & SOLUTIONS (GOTCHAS)

When editing or maintaining this project, respect the following constraints:

### 6.1. Windows Unicode Image IO Bug
* **Issue:** OpenCV (`cv2.imread`/`cv2.imwrite`) has a long-standing bug on Windows where it fails when image filepaths contain Vietnamese unicode characters (e.g. `nguyễn tiến chính`).
* **Solution:** Always read and write image files as byte arrays using NumPy:
  ```python
  # Writing:
  is_success, im_buf_arr = cv2.imencode(".jpg", aligned_face)
  im_buf_arr.tofile(filepath)

  # Reading:
  image = cv2.imdecode(np.fromfile(filepath, dtype=np.uint8), cv2.IMREAD_COLOR)
  ```

### 6.2. ESP8266 BearSSL Out of Memory (OOM) Crash
* **Issue:** Generating/verifying SSL layers for `https` connection to Firebase consumes substantial heap space. If the buffer size is too large, the ESP8266 runs out of memory, prints `Failed to initialize the SSL layer`, and disconnects.
* **Solution:** In the Arduino sketch `setupFirebase()`, force a strict buffer size limit (e.g. 512 bytes) on the `FirebaseData` instance:
  ```cpp
  fbdo.setResponseSize(512); // Restricts response buffer to save RAM
  ```

### 6.3. Software PWM Servo Jitter during WiFi/SSL Activity
* **Issue:** The ESP8266 `Servo` library relies on software-timer interrupts. The CPU-heavy cryptography of BearSSL/Firebase blocks interrupts for up to 100-200ms, making the servo spin continuously, jitter, or twitch.
* **Solution:** Dynamically attach the servo only when we need to rotate it, and detach it immediately afterwards:
  ```cpp
  doorServo.attach(SERVO_PIN);
  doorServo.write(SERVO_OPEN_DEG);
  delay(600);          // Allow movement
  doorServo.detach();  // Shut down software PWM interrupts
  ```

### 6.4. Continuous Standalone Jitter & Votes Accumulation
* **Issue:** In continuous standalone mode, if the system alerts on 1 frame, a single bad angle can cause a false positive. If we accumulate frames forever, old votes will mix with a new person's face.
* **Solution:** We accumulate exactly `args.frames` (configured to 5). Once we hit 5 frames, we vote and write the result. If a face is lost for more than 2 seconds (`now - last_face_seen_time > 2.0`), we clear the votes list to reset the state for the next user.
