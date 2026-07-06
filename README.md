# FBI IMG — Detección y censura automática de datos confidenciales en imágenes

Stack: Python · YOLO11 (Ultralytics) · EasyOCR · OpenCV · FastAPI · React · Docker Compose.
Arquitectura de microservicios: **frontend** (React+nginx) · **backend** (orquestador + IA) · **qr-service** (decodificación QR aislada) · **trainer** (fine-tuning, perfil aparte).

Licencia: **AGPL-3.0** (requerida por Ultralytics).

## Requisitos

- Docker + Docker Compose (el usuario debe estar en el grupo `docker`)
- ~6 GB de disco para las imágenes (torch CPU + modelos pre-descargados)
- No requiere GPU ni conexión a internet en runtime

> Los builds usan `network: host` (workaround para redes donde el bridge de
> Docker no tiene salida a internet). Si en tu máquina el bridge funciona,
> puedes quitar esa línea del `docker-compose.yml` — todo funciona igual.

## Cómo levantar todo

```bash
# 1. levantar los tres servicios de producción
docker compose up --build -d

# 2. abrir la interfaz
#    http://localhost:8080

# 3. probar el backend directo (opcional)
curl -F "file=@foto.jpg" -F "mode=completo" http://localhost:8000/analyze
```

Modos de análisis:

| Modo | Qué hace |
|---|---|
| `ligero` | Detección YOLO + decodificación de QR |
| `medio` | + OCR (EasyOCR) con regex de credenciales sobre texto/documentos |
| `completo` | + censura (blur OpenCV) de todas las zonas de riesgo |

## Funciona sin modelo entrenado

Si `models/best.pt` no existe, el backend usa **yolo11n.pt** base (clases COCO
genéricas) y además escanea **siempre** la imagen completa en el qr-service, así
los QR se detectan, decodifican y censuran desde el primer día.

> Con el modelo base COCO conviene `CONF_THRESHOLD=0.35` (ya en `.env`).
> Cuando entrenes tu `best.pt`, súbelo a `0.75` (metodología del proyecto).

## Entrenamiento del modelo propio

```bash
# dataset sintético de QR para arrancar (opcional, clase qr_code)
docker compose --profile train run --rm trainer python make_synthetic_qr.py 300

# fine-tuning YOLO11n (100 epochs, early stopping)
docker compose --profile train up --build trainer
#   -> genera ./models/best.pt

# recargar el backend con el nuevo modelo
docker compose up -d --build backend
```

Dataset propio: etiqueta con [Label Studio](https://github.com/HumanSignal/label-studio)
o LabelImg en formato **YOLO** y coloca los archivos en
`trainer/data/images/{train,val}` y `trainer/data/labels/{train,val}`.
Clases (ver `trainer/data/data.yaml`):
`qr_code, screen, document, id_card, handwritten_text, sticky_note`.

Todo corre en **CPU** por defecto (~1–4 s por imagen). Para GPU: instala
`nvidia-container-toolkit` y descomenta el bloque `deploy` del trainer en
`docker-compose.yml`.

## Control de fallos

| Riesgo | Mitigación | Dónde |
|---|---|---|
| Falsos positivos | Umbral de confianza configurable (`.env`) | `backend/app/config.py` |
| Falsos negativos (OCR) | Pre-proceso B/N + contraste + umbral adaptativo | `backend/app/ocr.py` |
| Saturación del servidor | Inferencia a 640 px (letterbox) | `backend/app/detector.py` |
| Fuga fuera de red | qr-service sin puerto expuesto; red interna `fbi-net` | `docker-compose.yml` |
| Privacy by design | Modelos pre-descargados en build; sin internet en runtime | Dockerfiles |
| qr-service caído | `/analyze` responde igual y reporta `warnings` | `backend/app/qr_client.py` |
