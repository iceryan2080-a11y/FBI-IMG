FROM python:3.12-slim-bookworm
RUN apt-get update && apt-get install -y --no-install-recommends \
    libgl1 libglib2.0-0 && rm -rf /var/lib/apt/lists/*
WORKDIR /workspace
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Pre-descarga el peso base (sin internet en runtime)
RUN python -c "from ultralytics import YOLO; YOLO('yolo11n.pt')"

COPY train.py make_synthetic_qr.py autolabel.py plot_metrics.py ./
CMD ["python", "train.py"]
