import os
import json
import base64
import numpy as np

os.environ["TF_FORCE_GPU_ALLOW_GROWTH"] = "true"
os.environ["CUDA_VISIBLE_DEVICES"] = ""

import cv2

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

    if not os.path.exists(MODEL_PATH):
        print(f"[FaceRecognizer] 妯″瀷涓嶅瓨鍦? {MODEL_PATH}")
        return False

    try:
        import tensorflow as tf

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

        _face_cascade = cv2.CascadeClassifier(
            cv2.data.haarcascades + "haarcascade_frontalface_default.xml"
        )

        _available = True
        print(f"[FaceRecognizer] 妯″瀷鍔犺浇鎴愬姛: {_class_names}")
        return True
    except Exception as e:
        print(f"[FaceRecognizer] 鍔犺浇澶辫触: {e}")
        return False


def is_available():
    return _ensure_loaded()


def get_class_names():
    if _ensure_loaded():
        return list(_class_names)
    return []


def recognize_image_bytes(image_bytes: bytes) -> dict:
    if not _ensure_loaded():
        return {"success": False, "error": "浜鸿劯璇嗗埆妯″瀷鏈姞杞?}

    try:
        arr = np.frombuffer(image_bytes, dtype=np.uint8)
        img = cv2.imdecode(arr, cv2.IMREAD_COLOR)
    except Exception as e:
        return {"success": False, "error": f"鍥剧墖瑙ｆ瀽澶辫触: {e}"}

    if img is None:
        return {"success": False, "error": "鏃犳硶瑙ｇ爜鍥剧墖"}

    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    faces = _face_cascade.detectMultiScale(
        gray, scaleFactor=1.1, minNeighbors=5, minSize=(30, 30)
    )

    if len(faces) == 0:
        return {"success": True, "faces_found": 0, "results": [], "annotated_image": None}

    results = []
    for (x, y, w, h) in faces:
        face_roi = img[y:y + h, x:x + w]
        rgb = cv2.cvtColor(face_roi, cv2.COLOR_BGR2RGB)
        resized = cv2.resize(rgb, IMG_SIZE)
        normalized = resized.astype(np.float32) / 255.0
        batch = np.expand_dims(normalized, axis=0)
        predictions = _model.predict(batch, verbose=0)[0]
        idx = int(np.argmax(predictions))
        confidence = float(predictions[idx])

        if confidence < CONFIDENCE_THRESHOLD:
            name_display = "Unknown"
        else:
            name_display = _class_names[idx]

        results.append({
            "name": name_display,
            "confidence": round(confidence, 4),
            "bbox": [int(x), int(y), int(w), int(h)],
            "all_probs": {_class_names[i]: round(float(predictions[i]), 4) for i in range(len(_class_names))},
        })

    annotated = img.copy()
    for r in results:
        x, y, w, h = r["bbox"]
        color = (0, 255, 0) if r["name"] != "Unknown" else (0, 0, 255)
        cv2.rectangle(annotated, (x, y), (x + w, y + h), color, 2)
        label = f"{r['name']} ({r['confidence']:.1%})"
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