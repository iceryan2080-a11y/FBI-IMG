import cv2

# BGR
COLOR_OK    = (94, 197, 34)    # verde: detección sin riesgo
COLOR_RISK  = (36, 191, 251)   # ámbar: zona de riesgo
COLOR_FOUND = (68, 68, 239)    # rojo: hallazgo concreto (QR decodificado, credencial)


def draw_detection(img, bbox, label, color=COLOR_OK, thickness=2):
    """Dibuja caja + etiqueta con fondo sobre la imagen (para la vista anotada)."""
    h, w = img.shape[:2]
    x1, y1, x2, y2 = bbox
    x1, y1 = max(0, x1), max(0, y1)
    x2, y2 = min(w, x2), min(h, y2)
    if x2 <= x1 or y2 <= y1:
        return img
    cv2.rectangle(img, (x1, y1), (x2, y2), color, thickness)
    font, scale = cv2.FONT_HERSHEY_SIMPLEX, 0.55
    (tw, th), base = cv2.getTextSize(label, font, scale, 1)
    ty = y1 - 6 if y1 - th - base - 6 >= 0 else y2 + th + base + 6
    cv2.rectangle(img, (x1, ty - th - base), (x1 + tw + 8, ty + base), color, -1)
    cv2.putText(img, label, (x1 + 4, ty), font, scale, (10, 12, 14), 1, cv2.LINE_AA)
    return img


def blur_region(img, bbox, ksize=51):
    h, w = img.shape[:2]
    x1, y1, x2, y2 = bbox
    x1, y1 = max(0, x1), max(0, y1)
    x2, y2 = min(w, x2), min(h, y2)
    if x2 <= x1 or y2 <= y1:
        return img
    k = ksize | 1  # kernel impar
    img[y1:y2, x1:x2] = cv2.GaussianBlur(img[y1:y2, x1:x2], (k, k), 0)
    return img
