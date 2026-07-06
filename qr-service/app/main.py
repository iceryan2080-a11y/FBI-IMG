import re

import cv2
import numpy as np
from fastapi import FastAPI, File, UploadFile
from pyzbar.pyzbar import decode as zbar_decode
from starlette.concurrency import run_in_threadpool

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
