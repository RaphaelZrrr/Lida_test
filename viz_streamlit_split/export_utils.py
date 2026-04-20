import io
from PIL import Image


def png_bytes_to_jpeg_bytes(png_bytes: bytes, quality: int = 95) -> bytes:
    img = Image.open(io.BytesIO(png_bytes)).convert("RGB")
    out = io.BytesIO()
    img.save(out, format="JPEG", quality=quality)
    out.seek(0)
    return out.read()


def png_bytes_to_pdf_bytes(png_bytes: bytes) -> bytes:
    img = Image.open(io.BytesIO(png_bytes)).convert("RGB")
    out = io.BytesIO()
    img.save(out, format="PDF")
    out.seek(0)
    return out.read()