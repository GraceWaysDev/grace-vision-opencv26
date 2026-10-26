import io
import numpy as np
from PIL import Image
from .policy import decide

def runtime():
    import cv2
    if cv2.__version__.split(".")[0] != "5":
        raise RuntimeError("OpenCV 5 erforderlich, gefunden: " + cv2.__version__)
    return cv2

def decode(data):
    if len(data) > 12 * 1024 * 1024:
        raise ValueError("Maximal 12 MiB pro Bild.")
    with Image.open(io.BytesIO(data)) as header:
        if header.format not in {"JPEG", "PNG"}:
            raise ValueError("Nur JPEG oder PNG.")
        if header.width * header.height > 24_000_000:
            raise ValueError("Maximal 24 Megapixel.")
        if header.width < 1 or header.height < 1:
            raise ValueError("Ungültige Bildgröße.")
        # Avoid silent EXIF rotation differences in the side-by-side comparison.
        if header.getexif().get(274, 1) != 1:
            raise ValueError("Bitte vor dem Import eine korrekt ausgerichtete Kopie exportieren; EXIF-Rotation wird nicht automatisch verändert.")
        if header.mode in ("RGBA", "LA") or "transparency" in header.info:
            raise ValueError("Bitte ein Foto ohne Transparenz verwenden.")
    # EXIF access may load a PNG; Pillow.verify requires a freshly opened stream.
    with Image.open(io.BytesIO(data)) as verifier:
        verifier.verify()
    cv = runtime()
    image = cv.imdecode(np.frombuffer(data, np.uint8), cv.IMREAD_COLOR | cv.IMREAD_IGNORE_ORIENTATION)
    if image is None:
        raise ValueError("Bild nicht lesbar.")
    return image

def measure(image):
    cv = runtime()
    gray = cv.cvtColor(image, cv.COLOR_BGR2GRAY)
    h, w = gray.shape
    scale = min(1., 512 / max(w, h))
    normalized = cv.resize(gray, (max(1, round(w * scale)), max(1, round(h * scale))), interpolation=cv.INTER_AREA)
    return {
        "width": w, "height": h, "pixels": w*h,
        "sharpness": float(cv.Laplacian(normalized, cv.CV_64F).var()),
        "brightness": float(gray.mean()), "contrast": float(gray.std()),
        "dark_fraction": float((gray <= 10).mean()),
        "overexposed_fraction": float((gray >= 245).mean())
    }

def enhance(image, metrics):
    cv = runtime()
    result = image.copy()
    operations = []
    # Global luminance-only adjustments preserve geometry; no synthesis/detection/crop.
    lab = cv.cvtColor(result, cv.COLOR_BGR2LAB)
    lum, a, b = cv.split(lab)
    if metrics["brightness"] < 90 or metrics["brightness"] > 190:
        gamma = .85 if metrics["brightness"] < 90 else 1.15
        lut = np.rint(255 * (np.arange(256)/255)**gamma).astype(np.uint8)
        lum = cv.LUT(lum, lut)
        operations.append({"gamma": gamma})
    if metrics["contrast"] < 35:
        balanced = cv.createCLAHE(clipLimit=1.2, tileGridSize=(8,8)).apply(lum)
        lum = cv.addWeighted(lum, .8, balanced, .2, 0)
        operations.append({"clahe_clip": 1.2, "blend": .2})
    if metrics["sharpness"] < 80:
        denoised = cv.bilateralFilter(lum, 5, 12, 12)
        lum = cv.addWeighted(lum, .85, denoised, .15, 0)
        blurred = cv.GaussianBlur(lum, (0,0), .8)
        lum = cv.addWeighted(lum, 1.15, blurred, -.15, 0)
        operations.append({"bilateral_blend": .15, "unsharp_amount": .15, "sigma": .8})
    result = cv.cvtColor(cv.merge((lum,a,b)), cv.COLOR_LAB2BGR)
    return result, operations

def png_bytes(image):
    ok, encoded = runtime().imencode(".png", image)
    if not ok:
        raise ValueError("PNG-Encoding fehlgeschlagen.")
    return encoded.tobytes()
