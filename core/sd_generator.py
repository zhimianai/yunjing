import os
import io
import re
import time
import base64
import threading
import traceback

_local_model_path = os.environ.get(
    "SD_LOCAL_PATH",
    r"C:\Users\OSCORP\.cache\huggingface\hub\sd-v1-5"
)

_lora_dir = os.environ.get(
    "SD_LORA_PATH",
    r"F:\ai项目\ai项目\models\sd\lora"
)

_pipe = None
_pipe_lock = threading.Lock()
_loaded = False
_load_error = None
_current_lora = None
_USE_SEQ_OFFLOAD = False


def _check_mem_ok():
    try:
        import ctypes
        class MEMORYSTATUSEX(ctypes.Structure):
            _fields_ = [("dwLength", ctypes.c_ulong), ("dwMemoryLoad", ctypes.c_ulong),
                        ("ullTotalPhys", ctypes.c_ulonglong), ("ullAvailPhys", ctypes.c_ulonglong),
                        ("ullTotalPageFile", ctypes.c_ulonglong), ("ullAvailPageFile", ctypes.c_ulonglong),
                        ("ullTotalVirtual", ctypes.c_ulonglong), ("ullAvailVirtual", ctypes.c_ulonglong),
                        ("ullAvailExtendedVirtual", ctypes.c_ulonglong)]
        ms = MEMORYSTATUSEX(); ms.dwLength = ctypes.sizeof(ms)
        ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(ms))
        avail_gb = ms.ullAvailPhys / (1024**3)
        total_gb = ms.ullTotalPhys / (1024**3)
        print(f"[SD] RAM check: avail={avail_gb:.1f}GB total={total_gb:.1f}GB")
        if avail_gb < 4.0 and not __import__('torch').cuda.is_available():
            print(f"[SD] Not enough RAM ({avail_gb:.1f}GB < 4GB needed), skipping local SD")
            return False
        return True
    except Exception:
        return True


def _load_pipe():
    global _pipe, _loaded, _load_error, _USE_SEQ_OFFLOAD
    if _loaded:
        return _pipe
    with _pipe_lock:
        if _loaded:
            return _pipe
        if not _check_mem_ok():
            _loaded = True
            _load_error = "Not enough RAM (need >=4GB free)"
            return None
        try:
            import torch
            from diffusers import StableDiffusionPipeline, EulerDiscreteScheduler

            has_cuda = torch.cuda.is_available()
            use_dtype = torch.float16 if has_cuda else torch.float32

            print(f"[SD] Loading local SD 1.5 from: {_local_model_path}")
            print(f"[SD] Device={'CUDA' if has_cuda else 'CPU'} dtype={use_dtype}")

            pipe = StableDiffusionPipeline.from_pretrained(
                _local_model_path,
                dtype=use_dtype,
                local_files_only=True,
                safety_checker=None,
                feature_extractor=None,
            )
            pipe.scheduler = EulerDiscreteScheduler.from_config(pipe.scheduler.config)

            if has_cuda:
                pipe = pipe.to("cuda")
            else:
                pipe = pipe.to("cpu")
                pipe.enable_attention_slicing(1)
                import torch as _t
                _t.set_num_threads(2)

            _pipe = pipe
            _loaded = True
            print("[SD] Model loaded OK (simple CPU mode)")
            return _pipe

        except Exception as e1:
            print(f"[SD] Load attempt 1 failed: {e1}")
            try:
                import torch
                from diffusers import StableDiffusionPipeline, EulerDiscreteScheduler

                print("[SD] Retrying minimal CPU mode...")
                pipe = StableDiffusionPipeline.from_pretrained(
                    _local_model_path,
                    dtype=torch.float32,
                    local_files_only=True,
                    safety_checker=None,
                    feature_extractor=None,
                )
                pipe.scheduler = EulerDiscreteScheduler.from_config(pipe.scheduler.config)
                pipe.enable_attention_slicing(1)
                import torch as _t
                _t.set_num_threads(1)
                _pipe = pipe
                _loaded = True
                print("[SD] Minimal CPU offload mode OK")
                return _pipe
            except Exception as e2:
                _load_error = f"All load attempts failed: {e2}"
                print(f"[SD] All load attempts failed: {e2}")
                _loaded = True
                return None


def _ensure_lora(lora_name):
    global _current_lora
    if not lora_name:
        if _current_lora:
            try:
                _pipe.unload_lora_weights()
                print(f"[SD] Unloaded LoRA: {_current_lora}")
            except Exception:
                pass
            _current_lora = None
        return True

    lora_path = os.path.join(_lora_dir, lora_name + ".safetensors")
    if not os.path.exists(lora_path):
        lora_path_ckpt = os.path.join(_lora_dir, lora_name + ".ckpt")
        if os.path.exists(lora_path_ckpt):
            lora_path = lora_path_ckpt
        else:
            alt = None
            if os.path.isdir(_lora_dir):
                for f in os.listdir(_lora_dir):
                    if f.startswith(lora_name) and (f.endswith(".safetensors") or f.endswith(".ckpt")):
                        alt = os.path.join(_lora_dir, f)
                        break
            if alt:
                lora_path = alt
            else:
                print(f"[SD] LoRA not found: {lora_name} (tried {lora_path})")
                return False

    if _current_lora == lora_path:
        return True

    try:
        _pipe.load_lora_weights(lora_path)
        _current_lora = lora_path
        print(f"[SD] LoRA loaded: {os.path.basename(lora_path)}")
        return True
    except Exception as e:
        print(f"[SD] LoRA load failed: {e}")
        return False


def is_available():
    pipe = _load_pipe()
    if pipe is not None:
        return True, "OK"
    return False, _load_error or "Unknown load error"


def list_available_loras():
    loras = []
    if os.path.isdir(_lora_dir):
        for f in os.listdir(_lora_dir):
            if f.endswith(".safetensors") or f.endswith(".ckpt"):
                loras.append(os.path.splitext(f)[0])
    return loras


def _decode_image(b64_or_url):
    from PIL import Image
    if b64_or_url.startswith("data:"):
        b64_or_url = b64_or_url.split(",", 1)[1]
    img_bytes = base64.b64decode(b64_or_url)
    img = Image.open(io.BytesIO(img_bytes)).convert("RGB")
    return img


def generate_local(prompt, size="512x512", reference_image=None, lora_name=None,
                   steps=12, guidance=7.5, seed=None, strength=0.78):
    pipe = _load_pipe()
    if pipe is None:
        return {"success": False, "error": f"SD not loaded: {_load_error}"}

    try:
        import torch

        w, h = map(int, size.split("x")) if "x" in size else (512, 512)
        w = max(256, min(512, w))
        h = max(256, min(512, h))

        if not _ensure_lora(lora_name):
            if lora_name:
                print(f"[SD] Warning: LoRA '{lora_name}' not available, generating without it")

        generator = None
        if seed is not None:
            device = "cuda" if torch.cuda.is_available() else "cpu"
            generator = torch.Generator(device=device)
            generator.manual_seed(int(seed))

        extra_kwargs = {"width": w, "height": h}

        if reference_image:
            init_img = _decode_image(reference_image)
            init_img = init_img.resize((w, h))
            extra_kwargs["image"] = init_img
            extra_kwargs["strength"] = strength
            print(f"[SD] img2img mode, strength={strength}, ref_size=({w},{h})")

        t0 = time.time()
        with torch.no_grad():
            result = pipe(
                prompt=prompt,
                num_inference_steps=steps,
                guidance_scale=guidance,
                generator=generator,
                **extra_kwargs,
            )

        img = result.images[0]
        dt = time.time() - t0
        print(f"[SD] Generated in {dt:.1f}s")

        buf = io.BytesIO()
        img.save(buf, format="PNG")
        b64 = base64.b64encode(buf.getvalue()).decode()

        return {
            "success": True,
            "image_base64": b64,
            "image_data": b64,
            "provider_used": "local-sd",
            "elapsed_seconds": round(dt, 1),
        }
    except Exception as e:
        traceback.print_exc()
        return {"success": False, "error": str(e)}