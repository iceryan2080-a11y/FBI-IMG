import re

import cv2
import numpy as np
from fastapi import FastAPI, File, UploadFile
from pyzbar.pyzbar import decode as zbar_decode
from starlette.concurrency import run_in_threadpool

try:
    import zxingcpp  # decodificador tolerante para QR incompletos/dañados
except ImportError:
    zxingcpp = None

app = FastAPI(title="FBI-IMG QR Service")

# Clasificación de riesgo del contenido decodificado
SENSITIVE_PATTERNS = {
    "wifi":        re.compile(r"^WIFI:", re.I),
    "credential":  re.compile(r"(pass|clave|pwd|token|secret)", re.I),
    "email":       re.compile(r"[\w.+-]+@[\w-]+\.[\w.-]+"),
    "vcard":       re.compile(r"BEGIN:VCARD", re.I),
    "url":         re.compile(r"https?://", re.I),
}


def classify(text: str) -> str:
    for label, pat in SENSITIVE_PATTERNS.items():
        if pat.search(text):
            return label
    return "generic"


@app.get("/health")
def health():
    return {"status": "ok"}


def _decode_image(data: bytes):
    """Trabajo CPU-bound: corre en threadpool para no bloquear el event loop."""
    img = cv2.imdecode(np.frombuffer(data, np.uint8), cv2.IMREAD_COLOR)
    if img is None:
        return []

    results = []

    # 1) pyzbar (robusto para decodificar)
    for obj in zbar_decode(img):
        x, y, w, h = obj.rect
        text = obj.data.decode("utf-8", errors="replace")
        results.append({
            "content": text,
            "risk_type": classify(text),
            "bbox": [int(x), int(y), int(w), int(h)],
            "engine": "pyzbar",
        })

    # 2) Fallback OpenCV para QR que pyzbar no pilla
    if not results:
        det = cv2.QRCodeDetector()
        ok, texts, pts, _ = det.detectAndDecodeMulti(img)
        if ok and pts is not None:
            for text, p in zip(texts, pts):
                if not text:
                    continue
                xs, ys = p[:, 0], p[:, 1]
                x, y = int(xs.min()), int(ys.min())
                w, h = int(xs.max() - x), int(ys.max() - y)
                results.append({
                    "content": text,
                    "risk_type": classify(text),
                    "bbox": [x, y, w, h],
                    "engine": "opencv",
                })

    return results


@app.post("/decode")
async def decode(file: UploadFile = File(...)):
    """Recibe una imagen (o recorte) y devuelve todos los QR decodificados."""
    data = await file.read()
    results = await run_in_threadpool(_decode_image, data)
    return {"found": len(results), "codes": results}


def _zxing_read(img):
    """Lee QR con zxing-cpp (más tolerante). Devuelve lista de resultados."""
    out = []
    if zxingcpp is None:
        return out
    for r in zxingcpp.read_barcodes(img, formats=zxingcpp.BarcodeFormat.QRCode):
        if not r.text:
            continue
        p = r.position
        xs = [p.top_left.x, p.top_right.x, p.bottom_right.x, p.bottom_left.x]
        ys = [p.top_left.y, p.top_right.y, p.bottom_right.y, p.bottom_left.y]
        x, y = int(min(xs)), int(min(ys))
        out.append({
            "content": r.text,
            "risk_type": classify(r.text),
            "bbox": [x, y, int(max(xs)) - x, int(max(ys)) - y],
            "engine": "zxing",
            "error_corrected": True,
        })
    return out


def _extract_image(data: bytes):
    """Intento agresivo de recuperar un QR incompleto/dañado.

    Prueba varios preprocesados y motores tolerantes (zxing-cpp además de
    pyzbar/opencv). La corrección de errores Reed-Solomon interna reconstruye
    los módulos faltantes mientras el daño no supere la capacidad del nivel ECC.
    """
    img = cv2.imdecode(np.frombuffer(data, np.uint8), cv2.IMREAD_COLOR)
    if img is None:
        return []

    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    # variantes: original, gris, escalado 3x (rescata QR pequeños/pixelados),
    # binarizado Otsu y cierre morfológico (rellena huecos pequeños)
    up = cv2.resize(gray, None, fx=3, fy=3, interpolation=cv2.INTER_CUBIC)
    _, otsu = cv2.threshold(up, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
    kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (3, 3))
    closed = cv2.morphologyEx(otsu, cv2.MORPH_CLOSE, kernel)
    variants = [img, gray, up, otsu, closed]

    seen = set()
    results = []
    for v in variants:
        engines = _zxing_read(v)
        # también pyzbar sobre cada variante (a veces pilla lo que zxing no)
        for obj in zbar_decode(v):
            text = obj.data.decode("utf-8", errors="replace")
            engines.append({
                "content": text, "risk_type": classify(text),
                "bbox": [int(c) for c in obj.rect], "engine": "pyzbar",
                "error_corrected": True,
            })
        for e in engines:
            if e["content"] in seen:
                continue
            seen.add(e["content"])
            results.append(e)
    return results


@app.post("/extract")
async def extract(file: UploadFile = File(...)):
    """Recuperación de QR incompletos: motores tolerantes + preprocesado."""
    data = await file.read()
    results = await run_in_threadpool(_extract_image, data)
    return {"found": len(results), "codes": results, "zxing": zxingcpp is not None}
