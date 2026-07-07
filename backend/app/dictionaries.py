"""Diccionarios para el modo COMPLETO.

- Español  (paquete wspanish -> /usr/share/dict/spanish): sirve para distinguir
  palabras reales de nombres propios (un token capitalizado que NO está en el
  diccionario suele ser un nombre) y para marcar contraseñas débiles.
- rockyou (mitad más común): lista de contraseñas filtradas. Si un token OCR
  aparece aquí, se emite una ALERTA de contraseña filtrada/débil.

Carga perezosa (solo la primera petición en modo completo) y cacheada, para no
frenar el arranque ni los modos ligero/medio.
"""
import logging
import os
import time
import unicodedata

log = logging.getLogger("uvicorn.error")

SPANISH_PATH = os.getenv("SPANISH_DICT_PATH", "/usr/share/dict/spanish")
ENGLISH_PATH = os.getenv("ENGLISH_DICT_PATH", "/usr/share/dict/american-english")
ROCKYOU_PATH = os.getenv("ROCKYOU_PATH", "/dicts/rockyou.txt")
ROCKYOU_FRACTION = float(os.getenv("ROCKYOU_FRACTION", "0.5"))   # "la mitad"
# rockyou tiene ~14.34M líneas; la mitad ≈ 7.17M (las más comunes van primero)
ROCKYOU_TOTAL = int(os.getenv("ROCKYOU_TOTAL_LINES", "14344392"))
# solo guardamos tokens de longitud razonable (memoria + menos falsos positivos)
MIN_LEN = int(os.getenv("DICT_MIN_LEN", "6"))
MAX_LEN = int(os.getenv("DICT_MAX_LEN", "24"))

_spanish = None
_rockyou = None


def strip_accents(s: str) -> str:
    return "".join(c for c in unicodedata.normalize("NFD", s)
                   if unicodedata.category(c) != "Mn")


def _load_words() -> set:
    """Palabras conocidas: español + inglés (para nombres propios y filtrar FP)."""
    words = set()
    for path in (SPANISH_PATH, ENGLISH_PATH):
        try:
            with open(path, encoding="utf-8", errors="ignore") as f:
                for line in f:
                    w = line.strip().lower()
                    if w:
                        words.add(w)
                        words.add(strip_accents(w))  # match aunque OCR pierda tildes
        except FileNotFoundError:
            log.warning("diccionario no encontrado en %s", path)
    log.info("diccionarios es+en cargados: %d entradas", len(words))
    return words


def _load_rockyou() -> set:
    words = set()
    max_lines = int(ROCKYOU_TOTAL * ROCKYOU_FRACTION)
    t0 = time.time()
    try:
        with open(ROCKYOU_PATH, encoding="latin-1") as f:
            for i, line in enumerate(f):
                if i >= max_lines:
                    break
                w = line.rstrip("\n").lower()
                if MIN_LEN <= len(w) <= MAX_LEN:
                    words.add(w)
    except FileNotFoundError:
        log.warning("rockyou no encontrado en %s (alertas desactivadas)",
                    ROCKYOU_PATH)
    log.info("rockyou cargado: %d contraseñas (mitad=%d líneas) en %.1fs",
             len(words), max_lines, time.time() - t0)
    return words


def spanish() -> set:
    global _spanish
    if _spanish is None:
        _spanish = _load_words()
    return _spanish


def rockyou() -> set:
    global _rockyou
    if _rockyou is None:
        _rockyou = _load_rockyou()
    return _rockyou


def is_common_word(token: str) -> bool:
    """True si es una palabra normal de diccionario (es/en). No es contraseña."""
    t = token.lower()
    s = spanish()
    return t in s or strip_accents(t) in s


# alias retro-compatible
is_spanish_word = is_common_word


def in_rockyou(token: str) -> bool:
    """True si el token (>=MIN_LEN) es una contraseña conocida de rockyou."""
    if len(token) < MIN_LEN:
        return False
    return token.lower() in rockyou()


def warmup():
    """Fuerza la carga (se llama en el primer análisis completo)."""
    spanish()
    rockyou()
