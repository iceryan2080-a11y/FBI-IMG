import logging

import cv2
import httpx

from .config import QR_SERVICE_URL

log = logging.getLogger("uvicorn.error")


async def _post_image(img_bgr):
    """Codifica la imagen y la manda al qr-service. None si el servicio falla."""
    ok, buf = cv2.imencode(".png", img_bgr)
    if not ok:
        return None
    try:
        async with httpx.AsyncClient(timeout=15) as client:
            r = await client.post(
                f"{QR_SERVICE_URL}/decode",
                files={"file": ("crop.png", buf.tobytes(), "image/png")},
            )
            r.raise_for_status()
            return r.json().get("codes", [])
    except httpx.HTTPError as e:
        log.error("qr-service no disponible: %s", e)
        return None


async def decode_crop(img_bgr, bbox):
    """Recorta la zona del QR y la manda al qr-service para decodificar."""
    h, w = img_bgr.shape[:2]
    x1, y1, x2, y2 = bbox
    crop = img_bgr[max(0, y1):min(h, y2), max(0, x1):min(w, x2)]
    if crop.size == 0:
        return []
    codes = await _post_image(crop)
    return codes


async def decode_full(img_bgr):
    """Escanea la imagen completa (funciona aunque el modelo no detecte qr_code)."""
    return await _post_image(img_bgr)


async def extract_full(img_bgr):
    """Recuperación agresiva de QR incompletos vía qr-service /extract."""
    ok, buf = cv2.imencode(".png", img_bgr)
    if not ok:
        return None
    try:
        async with httpx.AsyncClient(timeout=30) as client:
            r = await client.post(
                f"{QR_SERVICE_URL}/extract",
                files={"file": ("img.png", buf.tobytes(), "image/png")},
            )
            r.raise_for_status()
            return r.json().get("codes", [])
    except httpx.HTTPError as e:
        log.error("qr-service /extract no disponible: %s", e)
        return None
