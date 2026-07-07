import logging
import os

from ultralytics import YOLO

from .config import (CLASS_CONF, CONF_THRESHOLD, FALLBACK_MODEL_PATH, IMG_SIZE,
                     MIN_PREDICT_CONF, MODEL_PATH)

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
        # imgsz=640 -> ultralytics hace letterbox y devuelve cajas ya reescaladas.
        # Predice al piso más bajo y filtra por umbral de cada clase.
        floor = MIN_PREDICT_CONF if self.custom else CONF_THRESHOLD
        res = self.model.predict(img_bgr, imgsz=IMG_SIZE,
                                 conf=floor, verbose=False)[0]
        out = []
        for b in res.boxes:
            cls_id = int(b.cls[0])
            name = self.names.get(cls_id, str(cls_id))
            conf = round(float(b.conf[0]), 3)
            if conf < CLASS_CONF.get(name, CONF_THRESHOLD):
                continue
            x1, y1, x2, y2 = (int(v) for v in b.xyxy[0].tolist())
            out.append({"class": name, "conf": conf, "bbox": [x1, y1, x2, y2]})
        return out
