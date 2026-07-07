import re

import cv2
import easyocr

from .dictionaries import MIN_LEN, in_rockyou, is_common_word

# Regex locales que clasifican texto sensible (idea del repo Image-DLP)
CRED_PATTERNS = [
    ("credential", re.compile(r"(contraseñ?a|password|clave|pwd|pin)\s*[:=]?\s*\S+", re.I)),
    ("login",      re.compile(r"(usuario|user|login)\s*[:=]?\s*\S+", re.I)),
    ("email",      re.compile(r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b")),
    ("card",       re.compile(r"\b(?:\d[ -]?){13,16}\b")),
    ("id_pa",      re.compile(r"\b\d{1,2}-\d{3,4}-\d{3,5}\b")),   # cédula PA
]

# Fechas: numéricas (dd/mm/aaaa, aaaa-mm-dd) y textuales ("28 de enero de 2020",
# "noviembre 28, 2020"). En IDs/documentos son datos sensibles a censurar.
MONTHS = ("enero|febrero|marzo|abril|mayo|junio|julio|agosto|septiembre|"
          "octubre|noviembre|diciembre|jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec")
DATE_PATTERNS = [
    re.compile(r"\b\d{1,2}[/\-.]\d{1,2}[/\-.]\d{2,4}\b"),
    re.compile(r"\b\d{4}[/\-.]\d{1,2}[/\-.]\d{1,2}\b"),
    re.compile(rf"\b\d{{1,2}}\s+de\s+(?:{MONTHS})\s+de\s+\d{{4}}\b", re.I),
    re.compile(rf"\b(?:{MONTHS})\.?\s+\d{{1,2}},?\s+\d{{4}}\b", re.I),
]

# Palabras de cabecera de IDs/documentos: NO son nombres propios aunque vayan
# en mayúsculas (evita censurar títulos como "DRIVER LICENSE").
STOP_WORDS = {
    "driver", "license", "licencia", "identification", "card", "tarjeta",
    "credit", "debit", "visa", "master", "mastercard", "state", "usa",
    "sample", "class", "sex", "eyes", "hair", "date", "birth", "nacimiento",
    "exp", "iss", "donor", "veteran", "disabled", "communication",
    "impediment", "military", "north", "carolina", "texas", "pennsylvania",
    "under", "until", "address", "direccion", "street", "city", "apt",
    "member", "since", "valid", "thru", "banco", "aliado", "infinite",
    "documento", "documentos", "boletin", "informe", "informes", "real",
    "academia", "historia", "proposito", "transmision", "firma", "estimado",
    "nombre", "cargo", "numero", "telefono", "fax", "compania", "codigo", "postal",
}


def _dates_in(text):
    for pat in DATE_PATTERNS:
        m = pat.search(text)
        if m:
            return m.group(0)
    return None


def _name_in(text):
    """Detecta nombres propios: 2+ palabras capitalizadas que NO están en el
    diccionario español ni son cabeceras conocidas."""
    toks = re.findall(r"[A-Za-zÁÉÍÓÚÑáéíóúñ]{3,}", text)
    run, best = [], []
    for t in toks:
        proper = t[0].isupper() and t.lower() not in STOP_WORDS \
            and not is_common_word(t)
        if proper:
            run.append(t)
        else:
            if len(run) >= 2:
                best = run
            run = []
    if len(run) >= 2:
        best = run
    return " ".join(best) if len(best) >= 2 else None


CRED_CONTEXT = re.compile(r"(contrase|password|clave|pwd|pin|usuario|user|login)", re.I)


def _rockyou_hit(text):
    """Token que parece contraseña filtrada (en rockyou), con alta precisión.

    Para no marcar prosa normal (documentos, gracias, STREET) que también está
    en rockyou, solo se alerta cuando el token:
      - tiene dígito o símbolo (abcd1234, 12345678, p@ss), o
      - la línea tiene contexto de credencial ("password: qwerty", "clave: ...").
    """
    ctx = bool(CRED_CONTEXT.search(text))
    for tok in re.findall(rf"[A-Za-z0-9@._\-]{{{MIN_LEN},}}", text):
        if not in_rockyou(tok):
            continue
        if not tok.isalpha() or ctx:          # dígito/símbolo, o contexto claro
            return tok
    return None


class OcrEngine:
    def __init__(self):
        # gpu=False para correr en CPU dentro del contenedor
        self.reader = easyocr.Reader(["es", "en"], gpu=False)

    def _preprocess(self, crop):
        """B/N + contraste -> reduce falsos negativos (metodología del proyecto)."""
        gray = cv2.cvtColor(crop, cv2.COLOR_BGR2GRAY)
        gray = cv2.convertScaleAbs(gray, alpha=1.5, beta=0)
        return cv2.adaptiveThreshold(gray, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
                                     cv2.THRESH_BINARY, 31, 10)

    def read_region(self, img_bgr, bbox):
        h, w = img_bgr.shape[:2]
        x1, y1, x2, y2 = bbox
        x1, y1 = max(0, x1), max(0, y1)
        x2, y2 = min(w, x2), min(h, y2)
        crop = img_bgr[y1:y2, x1:x2]
        if crop.size == 0:
            return []
        pre = self._preprocess(crop)
        findings = []
        for pts, text, conf in self.reader.readtext(pre):
            for kind, pat in CRED_PATTERNS:
                if pat.search(text):
                    # bbox del texto en coords absolutas de la imagen original
                    xs = [int(p[0]) for p in pts]
                    ys = [int(p[1]) for p in pts]
                    findings.append({
                        "text": text,
                        "kind": kind,
                        "conf": round(float(conf), 3),
                        "bbox": [x1 + min(xs), y1 + min(ys),
                                 x1 + max(xs), y1 + max(ys)],
                    })
                    break
        return findings

    def read_full(self, img_bgr):
        """Escaneo de TODA la imagen (modo completo): credenciales, emails,
        tarjetas, cédulas, fechas, nombres propios y contraseñas de rockyou.

        Devuelve findings con bbox absoluto; cada uno se censura. Los que
        provienen de rockyou llevan alert=True para mostrarlos como alerta.
        """
        pre = self._preprocess(img_bgr)
        findings = []
        for pts, text, conf in self.reader.readtext(pre):
            xs = [int(p[0]) for p in pts]
            ys = [int(p[1]) for p in pts]
            bbox = [min(xs), min(ys), max(xs), max(ys)]
            cf = round(float(conf), 3)

            def add(kind, value, alert=False):
                findings.append({"text": value, "kind": kind, "conf": cf,
                                 "bbox": bbox, "alert": alert})

            # 1) contraseña filtrada (rockyou) -> ALERTA
            hit = _rockyou_hit(text)
            if hit:
                add("leaked_pwd", hit, alert=True)

            # 2) patrones de credenciales/datos
            for kind, pat in CRED_PATTERNS:
                if pat.search(text):
                    add(kind, text)
                    break

            # 3) fechas y nombres (típico en IDs/documentos)
            d = _dates_in(text)
            if d:
                add("date", d)
            name = _name_in(text)
            if name:
                add("name", name)
        return findings
