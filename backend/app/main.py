import base64

import cv2
import numpy as np
from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from starlette.concurrency import run_in_threadpool

from .config import BLUR_CLASSES, OCR_CLASSES
from .detector import Detector
from .ocr import OcrEngine
from .qr_client import decode_crop, decode_full
from .redactor import COLOR_FOUND, COLOR_OK, COLOR_RISK, blur_region, draw_detection

app = FastAPI(title="FBI-IMG Backend")
app.add_middleware(CORSMiddleware, allow_origins=["*"],
                   allow_methods=["*"], allow_headers=["*"])

detector = Detector()
ocr = OcrEngine()

MODES = ("ligero", "medio", "completo")


def _b64_jpg(img) -> str:
    ok, buf = cv2.imencode(".jpg", img)
    if not ok:
        raise HTTPException(500, "no se pudo codificar la imagen resultante")
    return "data:image/jpeg;base64," + base64.b64encode(buf.tobytes()).decode()


@app.get("/health")
def health():
    return {"status": "ok"}


@app.post("/analyze")
async def analyze(file: UploadFile = File(...), mode: str = Form("completo")):
    if mode not in MODES:
        raise HTTPException(400, f"modo inválido: {mode!r} (usa {', '.join(MODES)})")

    raw = await file.read()
    img = cv2.imdecode(np.frombuffer(raw, np.uint8), cv2.IMREAD_COLOR)
    if img is None:
        raise HTTPException(400, "imagen inválida o formato no soportado")

    detections = await run_in_threadpool(detector.detect, img)
    report = []
    blur_boxes = []
    warnings = []
    qr_contents_seen = set()

    for d in detections:
        item = {"class": d["class"], "conf": d["conf"], "bbox": d["bbox"],
                "details": []}
        risky = d["class"] in BLUR_CLASSES

        # QR detectado por YOLO -> decodificar en el microservicio aparte
        if d["class"] == "qr_code":
            codes = await decode_crop(img, d["bbox"])
            if codes is None:
                warnings.append("qr-service no disponible: QR sin decodificar")
            else:
                dx, dy = max(0, d["bbox"][0]), max(0, d["bbox"][1])
                for c in codes:
                    x, y, w, h = c["bbox"]
                    c["bbox"] = [dx + x, dy + y, dx + x + w, dy + y + h]
                item["details"] = codes
                qr_contents_seen.update(c["content"] for c in codes)
            risky = True

        # MEDIO / COMPLETO -> OCR de credenciales sobre texto/documentos
        if mode in ("medio", "completo") and d["class"] in OCR_CLASSES:
            creds = await run_in_threadpool(ocr.read_region, img, d["bbox"])
            if creds:
                item["details"].extend(creds)
                risky = True

        if mode == "completo" and risky:
            blur_boxes.append(d["bbox"])
            item["redacted"] = True

        item["risky"] = risky
        report.append(item)

    # Escaneo QR de la imagen COMPLETA: garantiza decodificación aunque el
    # modelo (p.ej. COCO base, sin entrenar) no tenga la clase qr_code.
    full_codes = await decode_full(img)
    if full_codes is None:
        warnings.append("qr-service no disponible: escaneo completo omitido")
    else:
        for code in full_codes:
            if code["content"] in qr_contents_seen:
                continue
            qr_contents_seen.add(code["content"])
            x, y, w, h = code["bbox"]
            bbox = [x, y, x + w, y + h]
            code["bbox"] = bbox
            item = {"class": "qr_code", "conf": None, "bbox": bbox,
                    "details": [code], "risky": True, "source": "qr-scan"}
            if mode == "completo":
                blur_boxes.append(bbox)
                item["redacted"] = True
            report.append(item)

    # Vista "señalar datos comprometedores": cajas sobre la imagen ORIGINAL
    # (antes del blur). Zonas de riesgo en ámbar, resto en verde, hallazgos
    # concretos (QR decodificados, credenciales OCR) en rojo con su etiqueta.
    annotated = img.copy()
    for item in report:
        label = item["class"] if item["conf"] is None else f"{item['class']} {item['conf']}"
        color = COLOR_RISK if item["risky"] else COLOR_OK
        dets = [d for d in item["details"] if "bbox" in d]
        # si el hallazgo ocupa la misma caja que la detección, una sola
        # etiqueta combinada (evita solaparse); si no, caja propia en rojo
        merged = next((d for d in dets if d["bbox"] == item["bbox"]), None)
        if merged is not None:
            tag = merged.get("risk_type") or merged.get("kind") or "hallazgo"
            draw_detection(annotated, item["bbox"], f"{item['class']}: {tag}", COLOR_FOUND)
        else:
            draw_detection(annotated, item["bbox"], label, color)
        for det in dets:
            if det is merged:
                continue
            tag = det.get("risk_type") or det.get("kind") or "hallazgo"
            draw_detection(annotated, det["bbox"], tag, COLOR_FOUND)

    # Blur al final: el OCR ya leyó todas las regiones sin zonas difuminadas
    for bbox in blur_boxes:
        img = blur_region(img, bbox)

    result = {
        "mode": mode,
        "total_detections": len(report),
        "risky_count": sum(1 for r in report if r["risky"]),
        "report": report,
        "image_base64": _b64_jpg(img),
        "image_annotated": _b64_jpg(annotated),
    }
    if warnings:
        result["warnings"] = warnings
    return result
