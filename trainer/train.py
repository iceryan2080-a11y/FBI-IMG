import shutil
from pathlib import Path

from ultralytics import YOLO

DATA = Path("/workspace/data")
MODELS = Path("/workspace/models")


def has_dataset() -> bool:
    return any((DATA / "images" / "train").glob("*.[jp][pn]g"))


def main():
    if not has_dataset():
        print("⚠ No hay imágenes en data/images/train.")
        print("  Genera dataset sintético de QR:  python make_synthetic_qr.py")
        print("  O etiqueta tus fotos con Label Studio / LabelImg (formato YOLO).")
        raise SystemExit(1)

    # YOLO11n = base ligera y estable (Transfer Learning / fine-tuning)
    model = YOLO("yolo11n.pt")     # alternativa: "yolo26n.pt"
    model.train(
        data=str(DATA / "data.yaml"),
        epochs=100,
        imgsz=640,
        batch=16,
        patience=20,               # early stopping
        project=str(MODELS),
        name="proto",
        exist_ok=True,
    )
    # Copia el mejor peso a la ruta que usa el backend
    shutil.copy(MODELS / "proto" / "weights" / "best.pt", MODELS / "best.pt")
    print("✅ best.pt listo en ./models/best.pt — reinicia el backend:")
    print("   docker compose up -d --build backend")


if __name__ == "__main__":
    main()
