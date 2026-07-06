"""Genera dataset sintético de QR para la clase 0 (qr_code).

Pega QR aleatorios sobre fondos generados y escribe imágenes + labels YOLO
(clase x_centro y_centro ancho alto, normalizados) en data/images y data/labels,
con split 80% train / 20% val.

Uso (dentro del contenedor trainer o con python local):
    python make_synthetic_qr.py [n_imagenes]
"""
import random
import string
import sys
from pathlib import Path

import qrcode
from PIL import Image, ImageDraw

DATA = Path(__file__).parent / "data"
if Path("/workspace/data").exists():          # dentro del contenedor
    DATA = Path("/workspace/data")

CANVAS = (640, 640)
QR_CLASS_ID = 0  # qr_code en data.yaml

PAYLOADS = [
    lambda: f"WIFI:S:red_{rand_word()};T:WPA;P:{rand_word(10)};;",
    lambda: f"https://example.com/{rand_word()}",
    lambda: f"user:{rand_word()} pass:{rand_word(8)}",
    lambda: f"{rand_word()}@example.com",
    lambda: rand_word(20),
]


def rand_word(n: int = 6) -> str:
    return "".join(random.choices(string.ascii_lowercase + string.digits, k=n))


def random_background() -> Image.Image:
    """Fondo con color/ruido aleatorio para variar el contexto."""
    base = tuple(random.randint(60, 220) for _ in range(3))
    img = Image.new("RGB", CANVAS, base)
    d = ImageDraw.Draw(img)
    for _ in range(random.randint(3, 12)):
        x1, y1 = random.randint(0, 600), random.randint(0, 600)
        x2, y2 = x1 + random.randint(20, 200), y1 + random.randint(20, 200)
        color = tuple(random.randint(0, 255) for _ in range(3))
        if random.random() < 0.5:
            d.rectangle([x1, y1, x2, y2], fill=color)
        else:
            d.ellipse([x1, y1, x2, y2], fill=color)
    return img


def make_sample(idx: int, split: str):
    img = random_background()
    labels = []
    for _ in range(random.randint(1, 3)):
        payload = random.choice(PAYLOADS)()
        qr = qrcode.make(payload).convert("RGB")
        size = random.randint(80, 280)
        qr = qr.resize((size, size))
        if random.random() < 0.5:
            qr = qr.rotate(random.uniform(-15, 15), expand=True, fillcolor="white")
            size = qr.size[0]
        x = random.randint(0, CANVAS[0] - size)
        y = random.randint(0, CANVAS[1] - size)
        img.paste(qr, (x, y))
        # label YOLO normalizado
        cx, cy = (x + size / 2) / CANVAS[0], (y + size / 2) / CANVAS[1]
        w, h = size / CANVAS[0], size / CANVAS[1]
        labels.append(f"{QR_CLASS_ID} {cx:.6f} {cy:.6f} {w:.6f} {h:.6f}")

    name = f"synth_qr_{idx:05d}"
    img.save(DATA / "images" / split / f"{name}.jpg", quality=90)
    (DATA / "labels" / split / f"{name}.txt").write_text("\n".join(labels) + "\n")


def main():
    n = int(sys.argv[1]) if len(sys.argv) > 1 else 300
    random.seed(42)
    for split in ("train", "val"):
        (DATA / "images" / split).mkdir(parents=True, exist_ok=True)
        (DATA / "labels" / split).mkdir(parents=True, exist_ok=True)
    n_train = int(n * 0.8)
    for i in range(n):
        make_sample(i, "train" if i < n_train else "val")
    print(f"✅ {n_train} train + {n - n_train} val generados en {DATA}")


if __name__ == "__main__":
    main()
