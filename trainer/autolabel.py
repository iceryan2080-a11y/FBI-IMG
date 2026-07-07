"""Pseudo-etiquetado (auto-labeling) para el modelo 'proto'.

Las fotos reales añadidas a data/images/{train,val} no traen etiquetas YOLO.
Sin etiqueta, YOLO las trata como fondo vacío y EMPEORA el modelo. Este script
genera etiquetas automáticas best-effort:

  - QR codes  -> clase 0 (qr_code)   vía zxing-cpp (bbox por las 4 esquinas)
  - pantallas -> clase 1 (screen)    laptop/tv/celular del modelo base COCO
  - documento -> clase 2 (document)  'book' del modelo base COCO

Deja una vista previa con las cajas dibujadas en data/autolabel_preview/ para
que revises que las etiquetas tienen sentido antes de entrenar.

No sobreescribe etiquetas que ya existan (los QR sintéticos se respetan).
"""
import shutil
from pathlib import Path

import cv2
import numpy as np
from ultralytics import YOLO

try:
    import zxingcpp
except ImportError:
    zxingcpp = None

DATA = Path("/workspace/data")
PREVIEW = DATA / "autolabel_preview"
EXTS = (".jpg", ".jpeg", ".png", ".webp", ".bmp")

# clase COCO (modelo base) -> clase nuestra (data.yaml)
# 62 tv, 63 laptop, 67 cell phone -> screen(1) ; 73 book -> document(2)
COCO_MAP = {62: 1, 63: 1, 67: 1, 73: 2}
NAMES = ["qr_code", "screen", "document", "id_card", "handwritten_text", "sticky_note"]
COLORS = [(68, 68, 239), (36, 191, 251), (94, 197, 34), (255, 128, 0),
          (200, 60, 200), (0, 200, 200)]

coco = YOLO("yolo11n.pt")  # modelo base COCO pre-descargado en build

# Etiquetas manuales para imágenes de IDs/documentos (COCO no las detecta).
# cls, x1,y1,x2,y2 normalizados. document=2, id_card=3. Categorizadas a ojo.
MANUAL_LABELS = {
    "14_NC_O21_ID_Face 1.png":        [(3, .01, .02, .99, .98)],
    "Real_20ID_202025_0.png":         [(3, .05, .03, .78, .41), (3, .18, .46, .85, .99)],
    "testreal id-compliant junior driver_s license.jpg": [(3, .03, .02, .97, .98)],
    "ba-visa-infinite.png":           [(3, .02, .03, .98, .97)],
    "promo-gettyimages-1465282155_1200-x-627.jpg": [(3, .33, .01, .99, .42), (3, .27, .30, .79, .92)],
    "que-son-documentos-comerciales-1.jpg": [(2, .02, .05, .98, .95)],
    "word--ver-documentos--01.png":   [(2, .13, .20, .99, .99)],
    "transmisión-de-documentos-para-la-firma-D3163.png": [(2, .05, .03, .95, .98)],
    "Cover.jpg":                      [(2, .05, .03, .95, .98)],
}


def qr_boxes(img):
    """[(cls0, x1,y1,x2,y2), ...] de cada QR detectado por zxing."""
    out = []
    if zxingcpp is None:
        return out
    for r in zxingcpp.read_barcodes(img):
        if r.format != zxingcpp.BarcodeFormat.QRCode:
            continue
        p = r.position
        xs = [p.top_left.x, p.top_right.x, p.bottom_right.x, p.bottom_left.x]
        ys = [p.top_left.y, p.top_right.y, p.bottom_right.y, p.bottom_left.y]
        out.append((0, min(xs), min(ys), max(xs), max(ys)))
    return out


def coco_boxes(img):
    """[(cls, x1,y1,x2,y2), ...] mapeando detecciones COCO a nuestras clases."""
    out = []
    res = coco.predict(img, imgsz=640, conf=0.30, verbose=False)[0]
    for b in res.boxes:
        c = int(b.cls[0])
        if c in COCO_MAP:
            x1, y1, x2, y2 = b.xyxy[0].tolist()
            out.append((COCO_MAP[c], x1, y1, x2, y2))
    return out


def to_yolo(cls, x1, y1, x2, y2, W, H):
    x1, x2 = sorted((max(0, x1), min(W, x2)))
    y1, y2 = sorted((max(0, y1), min(H, y2)))
    cx, cy = (x1 + x2) / 2 / W, (y1 + y2) / 2 / H
    w, h = (x2 - x1) / W, (y2 - y1) / H
    return f"{cls} {cx:.6f} {cy:.6f} {w:.6f} {h:.6f}"


def process(split):
    img_dir = DATA / "images" / split
    lbl_dir = DATA / "labels" / split
    lbl_dir.mkdir(parents=True, exist_ok=True)
    (PREVIEW / split).mkdir(parents=True, exist_ok=True)

    labeled = skipped = empty = 0
    for img_path in sorted(img_dir.iterdir()):
        if img_path.suffix.lower() not in EXTS:
            continue
        lbl_path = lbl_dir / (img_path.stem + ".txt")
        if lbl_path.exists():
            skipped += 1
            continue

        img = cv2.imread(str(img_path))
        if img is None:
            print(f"  ⚠ no se pudo leer {img_path.name}")
            continue
        H, W = img.shape[:2]

        if img_path.name in MANUAL_LABELS:
            boxes = [(c, x1 * W, y1 * H, x2 * W, y2 * H)
                     for (c, x1, y1, x2, y2) in MANUAL_LABELS[img_path.name]]
        else:
            boxes = qr_boxes(img) + coco_boxes(img)
        lines = [to_yolo(c, *xy, W, H) for (c, *xy) in boxes]
        lbl_path.write_text("\n".join(lines) + ("\n" if lines else ""))

        # vista previa con las cajas dibujadas
        vis = img.copy()
        for (c, x1, y1, x2, y2) in boxes:
            col = COLORS[c]
            cv2.rectangle(vis, (int(x1), int(y1)), (int(x2), int(y2)), col, 3)
            cv2.putText(vis, NAMES[c], (int(x1), max(20, int(y1) - 8)),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.7, col, 2)
        cv2.imwrite(str(PREVIEW / split / (img_path.stem + ".jpg")), vis)

        if lines:
            labeled += 1
            tags = ", ".join(NAMES[c] for (c, *_) in boxes)
            print(f"  ✓ {img_path.name}: {tags}")
        else:
            empty += 1
            print(f"  · {img_path.name}: sin detecciones (fondo)")
    print(f"[{split}] etiquetadas={labeled} vacías={empty} "
          f"ya-existían={skipped}")


def _classes_in(lbl_path):
    if not lbl_path.exists():
        return set()
    return {ln.split()[0] for ln in lbl_path.read_text().splitlines() if ln.strip()}


def rebalance_val():
    """Asegura que val tenga ejemplos de cada clase disponible (qr/id/doc).

    Idempotente: mueve de train->val solo una imagen por clase que aún no esté
    representada en val. Así las métricas cubren todas las clases entrenadas.
    """
    tr_img = DATA / "images" / "train"
    tr_lbl = DATA / "labels" / "train"
    va_img = DATA / "images" / "val"
    va_lbl = DATA / "labels" / "val"

    val_classes = set()
    for lp in va_lbl.glob("*.txt"):
        val_classes |= _classes_in(lp)

    wanted = {"0", "2", "3"}  # qr_code, document, id_card
    for cls in sorted(wanted - val_classes):
        for p in sorted(tr_img.iterdir()):
            if p.suffix.lower() not in EXTS:
                continue
            lp = tr_lbl / (p.stem + ".txt")
            if cls in _classes_in(lp):
                shutil.move(str(p), va_img / p.name)
                shutil.move(str(lp), va_lbl / lp.name)
                print(f"[val] +clase {cls}: {p.name}")
                break


if __name__ == "__main__":
    print("== auto-etiquetado (QR=zxing, screen/document=COCO base) ==")
    process("train")
    process("val")
    rebalance_val()
    print(f"Vista previa de etiquetas en: {PREVIEW}")
