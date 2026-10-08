import os
import json
import base64
import numpy as np

os.environ["TF_FORCE_GPU_ALLOW_GROWTH"] = "true"
os.environ["CUDA_VISIBLE_DEVICES"] = ""
os.environ.setdefault("PROTOCOL_BUFFERS_PYTHON_IMPLEMENTATION", "python")

import cv2

try:
    import tensorflow as tf
    _TF_AVAILABLE = True
except Exception as e:
    print(f"[FaceRecognizer] TensorFlow unavailable: {e}")
    tf = None
    _TF_AVAILABLE = False

_MODEL_DIR = os.path.normpath(
    os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "models")
)
MODEL_PATH = os.path.join(_MODEL_DIR, "face_recognition_model.h5")
CLASS_PATH = os.path.join(_MODEL_DIR, "class_names.json")
IMG_SIZE = (160, 160)
CONFIDENCE_THRESHOLD = 0.5

_model = None
_class_names = None
_face_cascade = None
_available = False


def _ensure_loaded():
    global _model, _class_names, _face_cascade, _available

    if _available:
        return True

    _face_cascade = cv2.CascadeClassifier(
        cv2.data.haarcascades + "haarcascade_frontalface_default.xml"
    )
    if _face_cascade.empty():
        print("[FaceRecognizer] Failed to load Haar cascade")
        return False

    if not _TF_AVAILABLE or not os.path.exists(MODEL_PATH):
        print("[FaceRecognizer] Using OpenCV face detection mode (no TF)")
        _available = True
        return True

    try:
        gpus = tf.config.list_physical_devices("GPU")
        if gpus:
            for gpu in gpus:
                try:
                    tf.config.experimental.set_memory_growth(gpu, True)
                except Exception:
                    pass

        _model = tf.keras.models.load_model(MODEL_PATH)
        with open(CLASS_PATH, "r", encoding="utf-8") as f:
            _class_names = json.load(f)

        _available = True
        print(f"[FaceRecognizer] Model loaded: {_class_names}")
        return True
    except Exception as e:
        print(f"[FaceRecognizer] Model load failed: {e}, using detection-only mode")
        _model = None
        _available = True
        return True


def is_available():
    return _ensure_loaded()


def get_class_names():
    if _ensure_loaded() and _class_names:
        return list(_class_names)
    return []


def recognize_image_bytes(image_bytes: bytes) -> dict:
    if not _ensure_loaded():
        return {"success": False, "error": "Face detection unavailable"}

    try:
        arr = np.frombuffer(image_bytes, dtype=np.uint8)
        img = cv2.imdecode(arr, cv2.IMREAD_COLOR)
    except Exception as e:
        return {"success": False, "error": f"Image parse failed: {e}"}

    if img is None:
        return {"success": False, "error": "Cannot decode image"}

    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    faces = _face_cascade.detectMultiScale(
        gray, scaleFactor=1.1, minNeighbors=5, minSize=(30, 30)
    )

    if len(faces) == 0:
        return {"success": True, "faces_found": 0, "results": [], "annotated_image": None}

    results = []
    for (x, y, w, h) in faces:
        entry = {
            "name": "Face",
            "confidence": 0.0,
            "bbox": [int(x), int(y), int(w), int(h)],
        }

        if _model is not None and _class_names:
            try:
                face_roi = img[y:y + h, x:x + w]
                rgb = cv2.cvtColor(face_roi, cv2.COLOR_BGR2RGB)
                resized = cv2.resize(rgb, IMG_SIZE)
                normalized = resized.astype(np.float32) / 255.0
                batch = np.expand_dims(normalized, axis=0)
                predictions = _model.predict(batch, verbose=0)[0]
                idx = int(np.argmax(predictions))
                confidence = float(predictions[idx])

                if confidence >= CONFIDENCE_THRESHOLD and idx < len(_class_names):
                    entry["name"] = _class_names[idx]
                    entry["confidence"] = round(confidence, 4)
                else:
                    entry["name"] = "Unknown"
                    entry["confidence"] = round(confidence, 4)

                entry["all_probs"] = {
                    _class_names[i]: round(float(predictions[i]), 4)
                    for i in range(len(_class_names))
                }
            except Exception as e:
                print(f"[FaceRecognizer] Prediction error: {e}")

        results.append(entry)

    annotated = img.copy()
    for r in results:
        x, y, w, h = r["bbox"]
        name = r["name"]
        color = (0, 255, 0) if name not in ("Unknown", "Face") else (0, 165, 255)
        cv2.rectangle(annotated, (x, y), (x + w, y + h), color, 2)
        label = f"{name}"
        if r["confidence"] > 0:
            label += f" ({r['confidence']:.1%})"
        cv2.putText(
            annotated, label, (x, y - 10),
            cv2.FONT_HERSHEY_SIMPLEX, 0.7, color, 2,
        )

    ok, buf = cv2.imencode(".jpg", annotated)
    annotated_b64 = base64.b64encode(buf).decode("utf-8")

    return {
        "success": True,
        "faces_found": len(results),
        "results": results,
        "annotated_image": "data:image/jpeg;base64," + annotated_b64,
    }