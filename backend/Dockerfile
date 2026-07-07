FROM python:3.12-slim-bookworm

RUN apt-get update && apt-get install -y --no-install-recommends \
    libgl1 libglib2.0-0 wspanish wamerican && rm -rf /var/lib/apt/lists/*
# wspanish -> /usr/share/dict/spanish ; wamerican -> /usr/share/dict/american-english
# (palabras conocidas es+en: distinguir nombres propios y filtrar FP de rockyou)

WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Pre-descarga en build (privacy by design: sin internet en runtime)
# 1) modelos de EasyOCR
RUN python -c "import easyocr; easyocr.Reader(['es','en'], gpu=False)"
# 2) peso base yolo11n.pt (fallback cuando aún no existe /models/best.pt)
RUN python -c "from ultralytics import YOLO; YOLO('yolo11n.pt')"

COPY app/ ./app/
EXPOSE 8000
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
