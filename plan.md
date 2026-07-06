# Plan de implementación — **FBI IMG**
### Detección y censura automática de datos confidenciales en imágenes
**Stack:** Python · YOLO11 (Ultralytics) · EasyOCR · OpenCV · FastAPI · React · Docker Compose
**Arquitectura:** microservicios separados (frontend / backend / qr-service / trainer)

> Verificado a julio 2026: `ultralytics` 8.4.x. Se usa **YOLO11n** como base de entrenamiento por ser el modelo estable mejor documentado para *fine-tuning* con dataset propio. YOLO26n queda como alternativa (cambia solo el nombre del peso base). Nota de licencia: Ultralytics es **AGPL-3.0**; como el proyecto es de código abierto, es compatible, pero deben publicar su código bajo la misma licencia.

---

## 1. Visión general de la arquitectura

Cuatro contenedores independientes en una misma red Docker (`fbi-net`):

```
┌──────────────────────────────────────────────────────────────┐
│                        Navegador (usuario)                     │
└───────────────────────────────┬──────────────────────────────┘
                                 │ HTTP :8080
                    ┌────────────▼────────────┐
                    │   FRONTEND (React+nginx) │  contenedor 1
                    │   Sube imagen, elige modo│
                    └────────────┬────────────┘
                                 │ HTTP :8000  (/analyze)
                    ┌────────────▼────────────┐
                    │  BACKEND (FastAPI)       │  contenedor 2
                    │  - Orquestador           │
                    │  - YOLO (detección)      │
                    │  - EasyOCR (texto)       │
                    │  - OpenCV (blur)         │
                    └───────┬─────────┬────────┘
                            │         │ HTTP interno :8100
                            │   ┌─────▼──────────┐
                            │   │ QR-SERVICE     │  contenedor 3
                            │   │ (FastAPI+pyzbar)│
                            │   │ decodifica QR   │
                            │   └────────────────┘
                            │
              (volumen compartido con pesos del modelo)
                    ┌───────▼────────┐
                    │ TRAINER        │  contenedor 4 (perfil aparte)
                    │ entrena YOLO   │  solo corre cuando entrenas
                    └────────────────┘
```

**Por qué separar el QR:** decodificar QR (WiFi, URLs, credenciales) es una responsabilidad distinta a la detección visual; aislarlo permite escalarlo, reiniciarlo o cambiar la librería sin tocar el resto. Cumple tu requisito de "las funciones del QR por separado".

**Flujo de una petición:**
1. El frontend envía la imagen + modo (`ligero` / `medio` / `completo`) al backend.
2. El backend corre YOLO → obtiene cajas (pantallas, documentos, QR, post-its, texto manuscrito).
3. Por cada caja tipo `qr_code`, el backend llama al **qr-service** para decodificar el contenido y clasificar el riesgo.
4. En modo `medio`+ corre EasyOCR sobre regiones de texto y aplica *regex* para detectar contraseñas/credenciales.
5. En modo `completo` aplica *blur* con OpenCV sobre todas las zonas de riesgo.
6. Devuelve al frontend: imagen procesada (base64) + reporte JSON de hallazgos.

---

## 2. Estructura del repositorio

```
fbi-img/
├── docker-compose.yml
├── .env
├── README.md
│
├── frontend/
│   ├── Dockerfile
│   ├── nginx.conf
│   ├── package.json
│   ├── vite.config.js
│   ├── index.html
│   └── src/
│       ├── main.jsx
│       ├── App.jsx
│       └── api.js
│
├── backend/
│   ├── Dockerfile
│   ├── requirements.txt
│   └── app/
│       ├── main.py            # FastAPI + endpoint /analyze
│       ├── config.py
│       ├── detector.py        # wrapper YOLO
│       ├── ocr.py             # wrapper EasyOCR + regex de credenciales
│       ├── redactor.py        # blur con OpenCV
│       └── qr_client.py       # llama al qr-service
│
├── qr-service/
│   ├── Dockerfile
│   ├── requirements.txt
│   └── app/
│       └── main.py            # FastAPI + pyzbar/opencv
│
├── trainer/
│   ├── Dockerfile
│   ├── requirements.txt
│   ├── train.py               # fine-tuning YOLO
│   └── data/
│       ├── data.yaml
│       ├── images/{train,val}/
│       └── labels/{train,val}/
│
└── models/                    # VOLUMEN compartido: best.pt vive aquí
    └── best.pt
```

---

## 3. `docker-compose.yml`

```yaml
services:
  frontend:
    build: ./frontend
    ports:
      - "8080:80"
    depends_on:
      - backend
    networks: [fbi-net]

  backend:
    build: ./backend
    ports:
      - "8000:8000"
    environment:
      - QR_SERVICE_URL=http://qr-service:8100
      - MODEL_PATH=/models/best.pt
      - CONF_THRESHOLD=0.75
    volumes:
      - ./models:/models:ro          # lee los pesos entrenados
    depends_on:
      - qr-service
    networks: [fbi-net]

  qr-service:
    build: ./qr-service
    # sin 'ports': solo accesible dentro de la red interna
    networks: [fbi-net]

  # Se ejecuta SOLO al entrenar:  docker compose --profile train up trainer
  trainer:
    build: ./trainer
    profiles: [train]
    volumes:
      - ./trainer/data:/workspace/data
      - ./models:/workspace/models    # escribe best.pt aquí
    # descomenta si tienes GPU NVIDIA + nvidia-container-toolkit:
    # deploy:
    #   resources:
    #     reservations:
    #       devices: [{driver: nvidia, count: 1, capabilities: [gpu]}]
    networks: [fbi-net]

networks:
  fbi-net:
    driver: bridge
```

---

## 4. Servicio: **qr-service** (el más simple, empezar por aquí)

### `qr-service/requirements.txt`
```
fastapi==0.115.*
uvicorn[standard]==0.32.*
pyzbar==0.1.9
opencv-python-headless==4.10.*
numpy==2.1.*
python-multipart==0.0.*
```

### `qr-service/Dockerfile`
```dockerfile
FROM python:3.12-slim

# pyzbar necesita la librería del sistema libzbar
RUN apt-get update && apt-get install -y --no-install-recommends \
    libzbar0 libgl1 libglib2.0-0 && rm -rf /var/lib/apt/lists/*

WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY app/ ./app/

EXPOSE 8100
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8100"]
```

### `qr-service/app/main.py`
```python
import re
import cv2
import numpy as np
from fastapi import FastAPI, UploadFile, File
from pyzbar.pyzbar import decode as zbar_decode

app = FastAPI(title="FBI-IMG QR Service")

# Clasificación de riesgo del contenido decodificado
SENSITIVE_PATTERNS = {
    "wifi":        re.compile(r"^WIFI:", re.I),
    "url":         re.compile(r"https?://", re.I),
    "email":       re.compile(r"[\w.+-]+@[\w-]+\.[\w.-]+"),
    "credential":  re.compile(r"(pass|clave|pwd|token|secret)", re.I),
    "vcard":       re.compile(r"BEGIN:VCARD", re.I),
}

def classify(text: str) -> str:
    for label, pat in SENSITIVE_PATTERNS.items():
        if pat.search(text):
            return label
    return "generic"

@app.get("/health")
def health():
    return {"status": "ok"}

@app.post("/decode")
async def decode(file: UploadFile = File(...)):
    """Recibe una imagen (o recorte) y devuelve todos los QR decodificados."""
    data = await file.read()
    img = cv2.imdecode(np.frombuffer(data, np.uint8), cv2.IMREAD_COLOR)
    if img is None:
        return {"found": 0, "codes": []}

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

    return {"found": len(results), "codes": results}
```

---

## 5. Servicio: **backend** (orquestador + IA)

### `backend/requirements.txt`
```
fastapi==0.115.*
uvicorn[standard]==0.32.*
python-multipart==0.0.*
httpx==0.27.*
ultralytics==8.4.*
easyocr==1.7.*
opencv-python-headless==4.10.*
numpy==2.1.*
torch==2.4.*          # CPU por defecto; ver nota GPU
Pillow==10.*
```
> **Nota GPU/CPU:** por defecto instala PyTorch CPU (funciona en cualquier máquina). Para GPU, usa una imagen base `pytorch/pytorch:2.4-cuda12.1` en el Dockerfile.

### `backend/Dockerfile`
```dockerfile
FROM python:3.12-slim

RUN apt-get update && apt-get install -y --no-install-recommends \
    libgl1 libglib2.0-0 && rm -rf /var/lib/apt/lists/*

WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Pre-descarga los modelos de EasyOCR en build (evita descargas en runtime)
RUN python -c "import easyocr; easyocr.Reader(['es','en'], gpu=False)"

COPY app/ ./app/
EXPOSE 8000
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
```

### `backend/app/config.py`
```python
import os

MODEL_PATH     = os.getenv("MODEL_PATH", "/models/best.pt")
QR_SERVICE_URL = os.getenv("QR_SERVICE_URL", "http://qr-service:8100")
CONF_THRESHOLD = float(os.getenv("CONF_THRESHOLD", "0.75"))
IMG_SIZE       = 640   # resize previo (control de saturación de tu metodología)

# Clases de tu dataset (deben coincidir con data.yaml)
CLASS_NAMES = ["qr_code", "screen", "document", "id_card",
               "handwritten_text", "sticky_note"]

# Qué clases se difuminan siempre en modo completo
BLUR_CLASSES = {"qr_code", "id_card", "sticky_note", "handwritten_text"}
```

### `backend/app/detector.py`
```python
import cv2
import numpy as np
from ultralytics import YOLO
from .config import MODEL_PATH, CONF_THRESHOLD, IMG_SIZE, CLASS_NAMES

class Detector:
    def __init__(self):
        self.model = YOLO(MODEL_PATH)

    def detect(self, img_bgr):
        """Devuelve lista de {class, conf, bbox:[x1,y1,x2,y2]}."""
        # Resize previo a 640x640 -> control de saturación del servidor
        resized = cv2.resize(img_bgr, (IMG_SIZE, IMG_SIZE))
        sx = img_bgr.shape[1] / IMG_SIZE
        sy = img_bgr.shape[0] / IMG_SIZE

        res = self.model.predict(resized, conf=CONF_THRESHOLD, verbose=False)[0]
        out = []
        for b in res.boxes:
            cls_id = int(b.cls[0])
            x1, y1, x2, y2 = b.xyxy[0].tolist()
            out.append({
                "class": CLASS_NAMES[cls_id] if cls_id < len(CLASS_NAMES) else str(cls_id),
                "conf": round(float(b.conf[0]), 3),
                # reescalar caja a la imagen original
                "bbox": [int(x1*sx), int(y1*sy), int(x2*sx), int(y2*sy)],
            })
        return out
```

### `backend/app/ocr.py`
```python
import re
import cv2
import easyocr

# Regex locales que clasifican texto sensible (idea del repo Image-DLP)
CRED_PATTERNS = [
    re.compile(r"(contraseñ?a|password|clave|pwd|pin)\s*[:=]?\s*\S+", re.I),
    re.compile(r"(usuario|user|login)\s*[:=]?\s*\S+", re.I),
    re.compile(r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b"),   # email
    re.compile(r"\b(?:\d[ -]?){13,16}\b"),                               # tarjeta
    re.compile(r"\b\d{1,2}-\d{3,4}-\d{3,5}\b"),                          # cédula PA
]

class OcrEngine:
    def __init__(self):
        # gpu=False para correr en CPU dentro del contenedor
        self.reader = easyocr.Reader(["es", "en"], gpu=False)

    def _preprocess(self, crop):
        """B/N + contraste -> reduce falsos negativos (tu metodología)."""
        gray = cv2.cvtColor(crop, cv2.COLOR_BGR2GRAY)
        gray = cv2.convertScaleAbs(gray, alpha=1.5, beta=0)
        return cv2.adaptiveThreshold(gray, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
                                     cv2.THRESH_BINARY, 31, 10)

    def read_region(self, img_bgr, bbox):
        x1, y1, x2, y2 = bbox
        crop = img_bgr[max(0,y1):y2, max(0,x1):x2]
        if crop.size == 0:
            return []
        pre = self._preprocess(crop)
        findings = []
        for _, text, conf in self.reader.readtext(pre):
            for pat in CRED_PATTERNS:
                if pat.search(text):
                    findings.append({"text": text, "conf": round(float(conf), 3)})
                    break
        return findings
```

### `backend/app/redactor.py`
```python
import cv2

def blur_region(img, bbox, ksize=51):
    x1, y1, x2, y2 = bbox
    x1, y1 = max(0, x1), max(0, y1)
    roi = img[y1:y2, x1:x2]
    if roi.size == 0:
        return img
    k = ksize | 1  # kernel impar
    img[y1:y2, x1:x2] = cv2.GaussianBlur(roi, (k, k), 0)
    return img
```

### `backend/app/qr_client.py`
```python
import cv2
import httpx
from .config import QR_SERVICE_URL

async def decode_crop(img_bgr, bbox):
    """Recorta la zona del QR y la manda al qr-service para decodificar."""
    x1, y1, x2, y2 = bbox
    crop = img_bgr[max(0,y1):y2, max(0,x1):x2]
    if crop.size == 0:
        return []
    ok, buf = cv2.imencode(".png", crop)
    if not ok:
        return []
    async with httpx.AsyncClient(timeout=15) as client:
        r = await client.post(f"{QR_SERVICE_URL}/decode",
                              files={"file": ("crop.png", buf.tobytes(), "image/png")})
        r.raise_for_status()
        return r.json().get("codes", [])
```

### `backend/app/main.py`
```python
import base64
import cv2
import numpy as np
from fastapi import FastAPI, UploadFile, File, Form
from fastapi.middleware.cors import CORSMiddleware

from .detector import Detector
from .ocr import OcrEngine
from .redactor import blur_region
from .qr_client import decode_crop
from .config import BLUR_CLASSES

app = FastAPI(title="FBI-IMG Backend")
app.add_middleware(CORSMiddleware, allow_origins=["*"],
                   allow_methods=["*"], allow_headers=["*"])

detector = Detector()
ocr = OcrEngine()

@app.get("/health")
def health():
    return {"status": "ok"}

@app.post("/analyze")
async def analyze(file: UploadFile = File(...), mode: str = Form("completo")):
    raw = await file.read()
    img = cv2.imdecode(np.frombuffer(raw, np.uint8), cv2.IMREAD_COLOR)
    if img is None:
        return {"error": "imagen inválida"}

    detections = detector.detect(img)      # LIGERO: solo geometría
    report = []

    for d in detections:
        item = {"class": d["class"], "conf": d["conf"], "bbox": d["bbox"], "details": []}
        risky = d["class"] in BLUR_CLASSES

        # QR -> decodificar en el microservicio aparte
        if d["class"] == "qr_code":
            codes = await decode_crop(img, d["bbox"])
            item["details"] = codes
            risky = True

        # MEDIO / COMPLETO -> OCR de credenciales sobre texto/documentos
        if mode in ("medio", "completo") and d["class"] in (
                "handwritten_text", "sticky_note", "document", "screen"):
            creds = ocr.read_region(img, d["bbox"])
            if creds:
                item["details"].extend(creds)
                risky = True

        # COMPLETO -> difuminar zonas de riesgo
        if mode == "completo" and risky:
            img = blur_region(img, d["bbox"])
            item["redacted"] = True

        item["risky"] = risky
        report.append(item)

    ok, buf = cv2.imencode(".jpg", img)
    img_b64 = base64.b64encode(buf.tobytes()).decode()

    return {
        "mode": mode,
        "total_detections": len(report),
        "risky_count": sum(1 for r in report if r["risky"]),
        "report": report,
        "image_base64": f"data:image/jpeg;base64,{img_b64}",
    }
```

---

## 6. Servicio: **frontend** (React + Vite servido por nginx)

### `frontend/Dockerfile` (multi-stage)
```dockerfile
# --- build ---
FROM node:20-alpine AS build
WORKDIR /app
COPY package.json ./
RUN npm install
COPY . .
RUN npm run build

# --- serve ---
FROM nginx:alpine
COPY nginx.conf /etc/nginx/conf.d/default.conf
COPY --from=build /app/dist /usr/share/nginx/html
EXPOSE 80
```

### `frontend/nginx.conf` (proxy hacia el backend)
```nginx
server {
    listen 80;
    location / {
        root /usr/share/nginx/html;
        try_files $uri /index.html;
    }
    # el navegador pega a /api/... y nginx reenvía al backend
    location /api/ {
        proxy_pass http://backend:8000/;
        client_max_body_size 20M;
    }
}
```

### `frontend/src/App.jsx` (mínimo funcional)
```jsx
import { useState } from "react";

export default function App() {
  const [file, setFile] = useState(null);
  const [mode, setMode] = useState("completo");
  const [result, setResult] = useState(null);
  const [loading, setLoading] = useState(false);

  const submit = async () => {
    if (!file) return;
    setLoading(true);
    const fd = new FormData();
    fd.append("file", file);
    fd.append("mode", mode);
    const res = await fetch("/api/analyze", { method: "POST", body: fd });
    setResult(await res.json());
    setLoading(false);
  };

  return (
    <div style={{ maxWidth: 800, margin: "2rem auto", fontFamily: "system-ui" }}>
      <h1>FBI IMG — Detector de datos confidenciales</h1>
      <input type="file" accept="image/*" onChange={(e) => setFile(e.target.files[0])} />
      <select value={mode} onChange={(e) => setMode(e.target.value)}>
        <option value="ligero">Ligero (geometría + QR)</option>
        <option value="medio">Medio (+ OCR credenciales)</option>
        <option value="completo">Completo (+ censura)</option>
      </select>
      <button onClick={submit} disabled={loading}>
        {loading ? "Analizando..." : "Analizar"}
      </button>

      {result && (
        <div>
          <p>Detecciones: {result.total_detections} · En riesgo: {result.risky_count}</p>
          <img src={result.image_base64} style={{ maxWidth: "100%" }} alt="resultado" />
          <pre style={{ background: "#f4f4f4", padding: 12, overflow: "auto" }}>
            {JSON.stringify(result.report, null, 2)}
          </pre>
        </div>
      )}
    </div>
  );
}
```

`package.json` mínimo:
```json
{
  "name": "fbi-img-frontend",
  "scripts": { "dev": "vite", "build": "vite build" },
  "dependencies": { "react": "^18.3.1", "react-dom": "^18.3.1" },
  "devDependencies": { "@vitejs/plugin-react": "^4.3.1", "vite": "^5.4.0" }
}
```
(`main.jsx`, `index.html` y `vite.config.js` son el boilerplate estándar de `npm create vite`.)

---

## 7. Pipeline de **entrenamiento** (contenedor trainer)

### Clases del dataset (`trainer/data/data.yaml`)
```yaml
path: /workspace/data
train: images/train
val: images/val
nc: 6
names: ["qr_code", "screen", "document", "id_card", "handwritten_text", "sticky_note"]
```

### Preparar el dataset
1. **Recolectar fotos** de oficinas, pantallas, post-its, QR, cédulas, texto manuscrito (mínimo ~150–300 por clase para empezar; más = mejor).
2. **Etiquetar** con **Label Studio** (repo `HumanSignal/label-studio`, desplegable local) o **LabelImg**, exportando en formato **YOLO** (un `.txt` por imagen con `clase x_centro y_centro ancho alto` normalizados).
3. Repartir 80% `train` / 20% `val` en las carpetas correspondientes.

> Truco para arrancar rápido: para `qr_code` puedes **generar dataset sintético** pegando QR aleatorios (librería `qrcode`) sobre fotos de fondo y guardando automáticamente las cajas. Reduce muchísimo el etiquetado manual de esa clase.

### `trainer/requirements.txt`
```
ultralytics==8.4.*
torch==2.4.*
```

### `trainer/Dockerfile`
```dockerfile
FROM python:3.12-slim
RUN apt-get update && apt-get install -y --no-install-recommends \
    libgl1 libglib2.0-0 && rm -rf /var/lib/apt/lists/*
WORKDIR /workspace
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY train.py .
CMD ["python", "train.py"]
```

### `trainer/train.py`
```python
from ultralytics import YOLO

def main():
    # YOLO11n = base ligera y estable (Transfer Learning / fine-tuning)
    model = YOLO("yolo11n.pt")     # alternativa: "yolo26n.pt"
    model.train(
        data="/workspace/data/data.yaml",
        epochs=100,
        imgsz=640,
        batch=16,
        patience=20,               # early stopping
        project="/workspace/models",
        name="fbi_run",
    )
    # Copia el mejor peso a la ruta que usa el backend
    import shutil
    shutil.copy("/workspace/models/fbi_run/weights/best.pt",
                "/workspace/models/best.pt")
    print("✅ best.pt listo en ./models/best.pt")

if __name__ == "__main__":
    main()
```

Entrenar:
```bash
docker compose --profile train up --build trainer
```
Al terminar, `models/best.pt` queda disponible para el backend (volumen compartido). Solo reinicia el backend:
```bash
docker compose up -d --build backend
```

---

## 8. Control de fallos (mapeado desde tu metodología)

| Riesgo | Mitigación | Dónde está en el código |
|---|---|---|
| Falsos positivos | Umbral de confianza `conf ≥ 0.75` | `config.CONF_THRESHOLD` + `detector.py` |
| Falsos negativos (OCR) | Pre-proceso B/N + contraste + umbral adaptativo | `ocr.py::_preprocess` |
| Saturación del servidor | Resize previo a 640×640 antes de inferir | `detector.py::detect` |
| Fuga fuera de red | qr-service **sin puerto expuesto**; todo en `fbi-net` | `docker-compose.yml` |
| Privacy by design | Sin llamadas a internet en runtime; modelos pre-descargados en build | Dockerfiles |

---

## 9. Cómo levantar todo

```bash
# 0. (solo la primera vez) entrenar el modelo
docker compose --profile train up --build trainer
#    -> genera ./models/best.pt

# 1. levantar los tres servicios de producción
docker compose up --build -d

# 2. abrir la interfaz
#    http://localhost:8080

# 3. probar el backend directo (opcional)
curl -F "file=@foto.jpg" -F "mode=completo" http://localhost:8000/analyze
```

> Si aún no tienes `best.pt` y quieres probar la tubería completa antes de entrenar, cambia temporalmente `MODEL_PATH` a `yolo11n.pt` en el backend: detectará clases COCO genéricas (funciona para validar el flujo, aunque no las clases sensibles reales).

---

## 10. Orden de construcción recomendado (para que "funcione" por etapas)

1. **qr-service** solo → probar `/decode` con una foto de un QR. *(1–2 días)*
2. **backend** con `yolo11n.pt` base + integrar qr-service → validar `/analyze` en modo ligero. *(2–3 días)*
3. Añadir **OCR** (modo medio) y **blur** (modo completo). *(2–3 días)*
4. **frontend** conectado vía nginx proxy. *(2 días)*
5. **Dataset + entrenamiento** del modelo propio → sustituir por `best.pt`. *(la parte más larga: 1–2 semanas según cuánto etiquetes)*
6. Ajuste de umbrales, evaluación en entorno cerrado, documentación. *(1 semana)*

Esto encaja con tu cronograma de 3 fases y deja un MVP demostrable desde la etapa 2.

---

## 11. Notas finales

- **Licencia:** al usar Ultralytics (AGPL-3.0), tu repositorio también debe ser AGPL-3.0. Coincide con tu objetivo de "código abierto", solo decláralo en el `LICENSE`.
- **Rendimiento CPU:** todo el stack corre en CPU. YOLO11n + EasyOCR en CPU procesa una imagen en ~1–4 s. Con GPU baja a <0.5 s (descomenta el bloque `deploy` del trainer y usa base `pytorch/pytorch:cuda`).
- **Escalar el qr-service:** `docker compose up --scale qr-service=3` si necesitas paralelizar decodificación.
- **Siguiente iteración:** añadir cola (Redis/RQ) si procesan lotes grandes, y persistir el reporte JSON para auditoría.
