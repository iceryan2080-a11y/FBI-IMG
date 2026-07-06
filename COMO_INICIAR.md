# Cómo iniciar FBI-IMG

Guía rápida para levantar el proyecto desde cero. Todo corre en Docker.

## 0. Requisitos (una sola vez)

- Docker + Docker Compose instalados.
- Tu usuario en el grupo `docker`:
  ```bash
  sudo usermod -aG docker $USER
  ```
  Después **cierra sesión y vuelve a entrar** (o reinicia) para que aplique.
  Verifica con: `docker ps` (no debe pedir sudo).

> Si aún no reiniciaste tras el `usermod`, antepón `sg docker -c "..."` a cada
> comando docker de esta guía. Ejemplo: `sg docker -c "docker compose up -d"`.

## 1. Construir e iniciar

Desde la carpeta del proyecto (`QR-IA/`):

```bash
docker compose up --build -d
```

Primera vez tarda varios minutos (descarga PyTorch CPU, EasyOCR, YOLO,
zxing-cpp). Las siguientes veces es casi instantáneo.

Comprueba que los 3 servicios están arriba:

```bash
docker compose ps
```

Deben verse `backend` y `qr-service` como **healthy**, y `frontend` **Up**.

## 2. Abrir la app

Navegador → **http://localhost:8080**

- Sube una imagen, elige modo (ligero / medio / completo), pulsa **ANALIZAR**.
- Botón **⊙ Señalar datos comprometedores**: muestra la imagen con cajas.
- Botón **⚡ Extract (QR incompleto)**: recupera datos de un QR dañado.

## 3. Comandos útiles

```bash
docker compose logs -f backend      # ver logs del backend
docker compose logs -f qr-service   # ver logs del qr-service
docker compose restart backend      # reiniciar un servicio
docker compose down                 # apagar todo
docker compose up --build -d        # reconstruir tras cambiar código
```

## 4. (Opcional) Entrenar el modelo propio `best.pt`

Sin esto, el sistema funciona con el modelo base (yolo11n) y detecta/decodifica
QR igual. Para entrenar tus 6 clases (qr_code, screen, document, id_card,
handwritten_text, sticky_note):

```bash
# a) dataset sintético de QR para arrancar rápido (genera 300 imágenes)
docker compose --profile train run --rm trainer python make_synthetic_qr.py 300

# b) para las otras clases: etiqueta fotos reales con Label Studio o LabelImg
#    (formato YOLO) y colócalas en trainer/data/images/{train,val} + labels/

# c) entrenar (lento en CPU: horas)
docker compose --profile train up trainer      # -> genera models/best.pt

# d) recargar el backend con el modelo entrenado
docker compose up -d backend
```

Detalle completo del entrenamiento en `EXPLICACION_PROYECTO.txt` (sección 5).

## 5. Problemas comunes

| Síntoma | Solución |
|---|---|
| `permission denied ... docker.sock` | Falta grupo `docker` (paso 0) o usa `sg docker -c "..."` |
| Build falla con `EAI_AGAIN` / DNS | Ya está el workaround `network: host` en el compose |
| El puerto 8080 u 8000 está ocupado | Cambia el mapeo de puertos en `docker-compose.yml` |
| La página no refleja cambios | Recarga con Ctrl+Shift+R (limpia caché) |

## Estructura del proyecto

```
QR-IA/
├── docker-compose.yml          # orquesta los 4 servicios
├── .env                        # CONF_THRESHOLD (umbral de confianza)
├── frontend/                   # React + nginx (interfaz)
├── backend/                    # FastAPI + YOLO11 + EasyOCR + OpenCV
├── qr-service/                 # FastAPI + pyzbar + zxing-cpp (QR)
├── trainer/                    # entrenamiento YOLO (perfil aparte)
├── models/                     # best.pt vive aquí tras entrenar
├── EXPLICACION_PROYECTO.txt    # explicación detallada del proyecto
└── COMO_INICIAR.md             # esta guía
```
