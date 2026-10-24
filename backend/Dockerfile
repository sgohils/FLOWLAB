# FLOWLAB backend image: build the single page app, then serve it from the API.
#
#   docker compose up --build      ->  http://localhost:8000
#
# The build context is the repository root (see docker-compose.yml), which is
# why this file lives in backend/ but copies frontend/ too.

# ---------------------------------------------------------------- frontend build
FROM node:22-alpine AS frontend-build

WORKDIR /build

# Dependencies first: this layer is only rebuilt when package-lock.json changes.
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci

COPY frontend/ ./
# The API mounts /assets and falls back to index.html for unknown paths, so a
# successful index.html is the whole contract.
RUN npm run build && test -f dist/index.html

# ---------------------------------------------------------------- runtime image
FROM python:3.11-slim AS runtime

# OpenCV needs libGL and the ffmpeg libraries to read video containers.  There
# is no compiler in this image on purpose: every wheel FLOWLAB needs is already
# published, and adding build-essential would triple the image for nothing.
RUN apt-get update && apt-get install -y --no-install-recommends \
        libgl1 \
        libglib2.0-0 \
        ffmpeg \
    && rm -rf /var/lib/apt/lists/*

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    FLOWLAB_DATA_DIR=/data

# There is deliberately no FRONTEND_DIST variable: backend/main.py derives the
# path from backend/config.py (PROJECT_DIR / "frontend" / "dist"), so with
# WORKDIR /app it is /app/frontend/dist.  An env var that nothing reads would
# only be one more thing to keep in sync.

WORKDIR /app

COPY backend/requirements.txt backend/requirements.txt
RUN pip install --no-cache-dir -r backend/requirements.txt

COPY backend ./backend
# Without this, backend/main.py's SPA branch is dead code in the image: the API
# would serve the JSON endpoints and 404 on every page load.  It mounts
# /assets and serves index.html for any other path.
COPY --from=frontend-build /build/dist ./frontend/dist
COPY README.md ./

# The image never runs as root.  /data is the only writable location the
# application uses, so it is the only one chowned.
RUN useradd --create-home --uid 10001 flowlab \
    && mkdir -p /data \
    && chown -R flowlab:flowlab /data
USER flowlab

VOLUME ["/data"]
EXPOSE 8000

# /api/ready, not /api/health.  /api/health answers 200 whether or not the
# detector loaded, which is deliberate - the browser banner in
# frontend/src/components/ApiHealthBanner.tsx needs to read *why* the backend is
# degraded - but it makes a useless health probe: a container whose weights
# never downloaded would report healthy.  /api/ready returns 503 until the
# detector is loaded, and urlopen raises on 503, so the probe fails truthfully.
# Same endpoint and start_period as the healthcheck in docker-compose.yml, so
# docker run and docker compose agree about when this image is usable.
#
# start-period=120s, not 30s: the first /api/ready imports torch and downloads
# the ~6 MB YOLO checkpoint.  Failures inside the start period are not counted
# as retries, so a cold start reads as starting rather than unhealthy.
HEALTHCHECK --interval=15s --timeout=10s --start-period=120s --retries=5 \
    CMD ["python", "-c", "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/api/ready').read()"]

# Bound to 0.0.0.0 *inside the container only*, so the published port works.
# That is not the same as being safe on a network: the API has no
# authentication of any kind, so keep the published port on loopback and do not
# put this in front of anything routable.  See FLOWLAB_CORS_ORIGINS in
# backend/config.py and the Privacy section of the README.
CMD ["uvicorn", "backend.main:app", "--host", "0.0.0.0", "--port", "8000"]
