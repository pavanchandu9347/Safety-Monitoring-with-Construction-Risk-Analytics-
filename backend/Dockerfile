FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONPATH=/app \
    PORT=8000

# The image is built from the repository root because the app imports the
# top-level `ai` package (computer vision / PPE models) as well as `backend/app`.
WORKDIR /app/backend

COPY backend/requirements.txt .
RUN apt-get update \
 && apt-get install -y --no-install-recommends libgl1 libglib2.0-0 \
 && rm -rf /var/lib/apt/lists/* \
 && pip install --no-cache-dir -r requirements.txt \
 && pip uninstall -y opencv-python \
 && pip install --no-cache-dir --force-reinstall opencv-python-headless

COPY backend/ .
COPY ai/ /app/ai

EXPOSE 8000

# Health probe uses the app's own /api/health endpoint (no extra tooling).
HEALTHCHECK --interval=30s --timeout=5s --start-period=60s --retries=5 \
  CMD ["python", "-c", "import urllib.request,sys; sys.exit(0 if urllib.request.urlopen('http://127.0.0.1:8000/api/health', timeout=4).status==200 else 1)"]

# Production ASGI: Gunicorn orchestrates a Uvicorn worker. WebSockets and the
# MJPEG stream are handled natively by the Uvicorn worker. A single worker is
# used by default so in-process state (job queue lock, WebSocket fan-out on one
# process) stays coherent; scale horizontally behind the reverse proxy if the
# load requires more.
CMD ["sh", "-c", "alembic -c alembic.ini upgrade head; exec gunicorn app.main:app --bind 0.0.0.0:8000 --workers 1 --worker-class uvicorn.workers.UvicornWorker --timeout 90 --graceful-timeout 90 --access-logfile - --error-logfile -"]