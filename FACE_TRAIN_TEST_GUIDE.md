# Face Train/Test Workflow

## 1. Capture training images

Run once per person. If no arguments are supplied, the program asks for the name and MSV:

```powershell
python capture_known_face.py
```

Or supply them directly:

```powershell
python capture_known_face.py --name "Nguyen Van A" --msv "B21DCCN001" --camera 0 --count 80
```

Controls:
- SPACE: save current detected face manually
- q or ESC: quit

Images are saved to:

```text
known_faces/<MSV>__<person_name>/
```

Each folder also contains `profile.json` with the person's name and MSV.

## 2. Train LBPH model

```powershell
python train_known_faces.py
```

Outputs:

```text
models/lbph_model.xml
models/labels.json
```

## 3. Test recognition with webcam preview

```powershell
python test_face_recognition_webcam.py --camera 0 --threshold 60
```

If the label is wrong or shows Unknown:
- add more images
- improve lighting
- keep face centered
- try threshold 70

## 4. Run Firebase recognition listener

```powershell
python firebase_face_recognition_listener.py --camera 0 --threshold 70 --frames 10
```

When ESP8266 writes:

```text
/capture_request = true
```

the listener writes result to:

```text
/recognitions/esp01
/history
```

The listener decides as soon as it has collected 10 frames containing a face.
The 10-second duration is only a timeout when no face is visible.
