import logging
import os

from ultralytics import YOLO

from .config import CONF_THRESHOLD, FALLBACK_MODEL_PATH, IMG_SIZE, MODEL_PATH

log = logging.getLogger("uvicorn.error")


class Detector:
    def __init__(self):
        if os.path.exists(MODEL_PATH):
            path, self.custom = MODEL_PATH, True
        else:
            path, self.custom = FALLBACK_MODEL_PATH, False
            log.warning(
                "No existe %s — usando modelo base %s (clases COCO genéricas). "
                "Entrena con el contenedor trainer para generar best.pt.",
                MODEL_PATH, FALLBACK_MODEL_PATH,
            )
        self.model = YOLO(path)
        self.names = self.model.names  # {id: nombre} del propio modelo
        log.info("Modelo cargado: %s (%d clases)", path, len(self.names))

    def detect(self, img_bgr):
        """Devuelve lista de {class, conf, bbox:[x1,y1,x2,y2]} en coords originales."""
        # imgsz=640 -> ultralytics hace letterbox y devuelve cajas ya reescaladas
        res = self.model.predict(img_bgr, imgsz=IMG_SIZE,
                                 conf=CONF_THRESHOLD, verbose=False)[0]
        out = []
        for b in res.boxes:
            cls_id = int(b.cls[0])
            x1, y1, x2, y2 = (int(v) for v in b.xyxy[0].tolist())
            out.append({
                "class": self.names.get(cls_id, str(cls_id)),
                "conf": round(float(b.conf[0]), 3),
                "bbox": [x1, y1, x2, y2],
            })
        return out
