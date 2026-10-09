import os
import json
import base64
import numpy as np

try:
    import cv2
    _CV2_AVAILABLE = hasattr(cv2, "CascadeClassifier")
    if not _CV2_AVAILABLE:
        print("[FaceRecognizer] OpenCV loaded but broken (no CascadeClassifier)")
except Exception as e:
    print(f"[FaceRecognizer] OpenCV unavailable: {e}")
    cv2 = None
    _CV2_AVAILABLE = False

try:
    import onnxruntime as ort
    _ORT_AVAILABLE = True
    print("[FaceRecognizer] ONNX Runtime available")
except Exception as e:
    print(f"[FaceRecognizer] ONNX Runtime unavailable: {e}")
    ort = None
    _ORT_AVAILABLE = False

try:
    os.environ.setdefault("PROTOCOL_BUFFERS_PYTHON_IMPLEMENTATION", "python")
    import tensorflow as tf
    _TF_AVAILABLE = True
except Exception as e:
    print(f"[FaceRecognizer] TensorFlow unavailable: {e}")
    tf = None
    _TF_AVAILABLE = False

_MODEL_DIR = os.path.normpath(
    os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "models")
)
ONNX_MODEL_PATH = os.path.join(_MODEL_DIR, "face_recognition_model.onnx")
TF_MODEL_PATH = os.path.join(_MODEL_DIR, "face_recognition_model.h5")
TFLITE_MODEL_PATH = os.path.join(_MODEL_DIR, "face_recognition_model.tflite")
CLASS_PATH = os.path.join(_MODEL_DIR, "class_names.json")
IMG_SIZE = (160, 160)
CONFIDENCE_THRESHOLD = 0.5

_NAME_CN_MAP = {
    "JuJingyi": "鞠婧祎",
    "Alice": "爱丽丝",
    "Bob": "鲍勃",
    "Charlie": "查理",
}


def _cn(name):
    return _NAME_CN_MAP.get(name, name)

_model = None
_model_type = None
_class_names = None
_face_cascade = None
_available = False


def _ensure_loaded():
    global _model, _model_type, _class_names, _face_cascade, _available

    if _available:
        return True

    if not _CV2_AVAILABLE:
        print("[FaceRecognizer] OpenCV not available, cannot load")
        return False

    _face_cascade = cv2.CascadeClassifier(
        cv2.data.haarcascades + "haarcascade_frontalface_default.xml"
    )
    if _face_cascade.empty():
        print("[FaceRecognizer] Failed to load Haar cascade")
        return False

    if os.path.exists(CLASS_PATH):
        try:
            with open(CLASS_PATH, "r", encoding="utf-8") as f:
                _class_names = json.load(f)
        except Exception as e:
            print(f"[FaceRecognizer] class_names.json load failed: {e}")

    if _ORT_AVAILABLE and os.path.exists(ONNX_MODEL_PATH):
        try:
            _model = ort.InferenceSession(ONNX_MODEL_PATH, providers=["CPUExecutionProvider"])
            _model_type = "onnx"
            _available = True
            print(f"[FaceRecognizer] ONNX model loaded: {_class_names}")
            return True
        except Exception as e:
            print(f"[FaceRecognizer] ONNX model load failed: {e}")

    if _TF_AVAILABLE and os.path.exists(TF_MODEL_PATH):
        try:
            _model = tf.keras.models.load_model(TF_MODEL_PATH)
            _model_type = "tf"
            _available = True
            print(f"[FaceRecognizer] TF model loaded: {_class_names}")
            return True
        except Exception as e:
            print(f"[FaceRecognizer] TF model load failed: {e}")

    if _CV2_AVAILABLE and hasattr(cv2.dnn, 'readNetFromTFLite') and os.path.exists(TFLITE_MODEL_PATH):
        try:
            _model = cv2.dnn.readNetFromTFLite(TFLITE_MODEL_PATH)
            _model.setPreferableBackend(cv2.dnn.DNN_BACKEND_OPENCV)
            _model.setPreferableTarget(cv2.dnn.DNN_TARGET_CPU)
            _model_type = "cv2_tflite"
            _available = True
            print(f"[FaceRecognizer] OpenCV TFLite model loaded: {_class_names}")
            return True
        except Exception as e:
            print(f"[FaceRecognizer] OpenCV TFLite load failed: {e}")

    print("[FaceRecognizer] Using OpenCV face detection mode (no model)")
    _available = True
    return True


def is_available():
    return _ensure_loaded()


def get_class_names():
    if _ensure_loaded() and _class_names:
        return [_cn(c) for c in _class_names]
    return []


def _predict(face_img):
    rgb = cv2.cvtColor(face_img, cv2.COLOR_BGR2RGB)
    resized = cv2.resize(rgb, IMG_SIZE)
    normalized = resized.astype(np.float32) / 255.0
    batch = np.expand_dims(normalized, axis=0)

    if _model_type == "onnx":
        input_name = _model.get_inputs()[0].name
        out = _model.run(None, {input_name: batch})[0]
        return out[0]
    elif _model_type == "tf":
        return _model.predict(batch, verbose=0)[0]
    elif _model_type == "cv2_tflite":
        nchw = np.transpose(batch, (0, 3, 1, 2)).astype(np.float32)
        _model.setInput(nchw)
        out = _model.forward()
        return out[0]
    return None


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
                predictions = _predict(face_roi)
                if predictions is not None:
                    idx = int(np.argmax(predictions))
                    confidence = float(predictions[idx])

                    if confidence >= CONFIDENCE_THRESHOLD and idx < len(_class_names):
                        entry["name"] = _cn(_class_names[idx])
                        entry["raw_name"] = _class_names[idx]
                        entry["confidence"] = round(confidence, 4)
                    else:
                        entry["name"] = "Unknown"
                        entry["raw_name"] = "Unknown"
                        entry["confidence"] = round(confidence, 4)

                    entry["all_probs"] = {
                        _cn(_class_names[i]): round(float(predictions[i]), 4)
                        for i in range(len(_class_names))
                    }
            except Exception as e:
                print(f"[FaceRecognizer] Prediction error: {e}")

        results.append(entry)

    annotated = img.copy()
    for r in results:
        x, y, w, h = r["bbox"]
        raw_name = r.get("raw_name", r["name"])
        color = (0, 255, 0) if raw_name not in ("Unknown", "Face") else (0, 165, 255)
        cv2.rectangle(annotated, (x, y), (x + w, y + h), color, 2)
        label = f"{raw_name}"
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