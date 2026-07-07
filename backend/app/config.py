import os

MODEL_PATH          = os.getenv("MODEL_PATH", "/models/best.pt")
FALLBACK_MODEL_PATH = os.getenv("FALLBACK_MODEL_PATH", "/app/yolo11n.pt")
QR_SERVICE_URL      = os.getenv("QR_SERVICE_URL", "http://qr-service:8100")
CONF_THRESHOLD      = float(os.getenv("CONF_THRESHOLD", "0.75"))
IMG_SIZE            = 640   # tamaño de inferencia (control de saturación)

# Umbral por clase: el modelo (dataset chico) da confianzas bajas en id_card/
# document. QR es fácil -> umbral alto. El resto usa CONF_THRESHOLD.
CLASS_CONF = {"qr_code": 0.35, "document": 0.20, "id_card": 0.12,
              "screen": 0.30}
# Piso para el predict de YOLO (el filtrado fino por clase se hace después).
MIN_PREDICT_CONF = min(list(CLASS_CONF.values()) + [CONF_THRESHOLD])

# Qué clases se difuminan siempre en modo completo (nombres del modelo entrenado)
BLUR_CLASSES = {"qr_code", "id_card", "sticky_note", "handwritten_text"}

# Clases sobre las que se corre OCR en modo medio/completo
OCR_CLASSES = {"handwritten_text", "sticky_note", "document", "screen"}
