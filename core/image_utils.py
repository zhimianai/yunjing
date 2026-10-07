import base64
import io


def compress_image(raw_bytes: bytes, max_side: int = 1568, quality: int = 85) -> tuple:
    from PIL import Image, ImageOps

    try:
        img = Image.open(io.BytesIO(raw_bytes))
    except Exception:
        return base64.b64encode(raw_bytes).decode('utf-8'), 'image/jpeg'

    if img.mode in ('RGBA', 'LA', 'P'):
        background = Image.new('RGB', img.size, (255, 255, 255))
        try:
            background.paste(img, mask=img.split()[-1])
        except Exception:
            background.paste(img)
        img = background
    elif img.mode != 'RGB':
        img = img.convert('RGB')

    w, h = img.size
    long_side = max(w, h)
    if long_side > max_side:
        ratio = max_side / long_side
        new_size = (max(1, int(w * ratio)), max(1, int(h * ratio)))
        img = img.resize(new_size, Image.LANCZOS)

    buf = io.BytesIO()
    img.save(buf, format='JPEG', quality=quality, optimize=True, progressive=True)
    compressed = buf.getvalue()

    return base64.b64encode(compressed).decode('utf-8'), 'image/jpeg'