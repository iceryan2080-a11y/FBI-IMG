import re

import cv2
import easyocr

# Regex locales que clasifican texto sensible (idea del repo Image-DLP)
CRED_PATTERNS = [
    ("credential", re.compile(r"(contraseñ?a|password|clave|pwd|pin)\s*[:=]?\s*\S+", re.I)),
    ("login",      re.compile(r"(usuario|user|login)\s*[:=]?\s*\S+", re.I)),
    ("email",      re.compile(r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b")),
    ("card",       re.compile(r"\b(?:\d[ -]?){13,16}\b")),
    ("id_pa",      re.compile(r"\b\d{1,2}-\d{3,4}-\d{3,5}\b")),   # cédula PA
]


class OcrEngine:
    def __init__(self):
        # gpu=False para correr en CPU dentro del contenedor
        self.reader = easyocr.Reader(["es", "en"], gpu=False)

    def _preprocess(self, crop):
        """B/N + contraste -> reduce falsos negativos (metodología del proyecto)."""
        gray = cv2.cvtColor(crop, cv2.COLOR_BGR2GRAY)
        gray = cv2.convertScaleAbs(gray, alpha=1.5, beta=0)
        return cv2.adaptiveThreshold(gray, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
                                     cv2.THRESH_BINARY, 31, 10)

    def read_region(self, img_bgr, bbox):
        h, w = img_bgr.shape[:2]
        x1, y1, x2, y2 = bbox
        x1, y1 = max(0, x1), max(0, y1)
        x2, y2 = min(w, x2), min(h, y2)
        crop = img_bgr[y1:y2, x1:x2]
        if crop.size == 0:
            return []
        pre = self._preprocess(crop)
        findings = []
        for pts, text, conf in self.reader.readtext(pre):
            for kind, pat in CRED_PATTERNS:
                if pat.search(text):
                    # bbox del texto en coords absolutas de la imagen original
                    xs = [int(p[0]) for p in pts]
                    ys = [int(p[1]) for p in pts]
                    findings.append({
                        "text": text,
                        "kind": kind,
                        "conf": round(float(conf), 3),
                        "bbox": [x1 + min(xs), y1 + min(ys),
                                 x1 + max(xs), y1 + max(ys)],
                    })
                    break
        return findings
