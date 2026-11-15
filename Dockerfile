# HYPERION-MDA live crew workstation — single image, single origin.
#
#   docker build -t hyperion-mda .
#   docker run --rm -p 8000:8000 -v hyperion-state:/app/var hyperion-mda
#
# Stage 1 builds the React SPA; stage 2 serves it and the API from the same FastAPI
# process, so there is no CORS, no second port and no browser-side localhost call.
# Not a medical device. Demo thresholds, not clinically validated.

# ---- stage 1: web build -------------------------------------------------------
FROM node:22-bookworm-slim AS web
WORKDIR /web
COPY web/package.json web/package-lock.json ./
RUN npm ci
COPY web/ ./
RUN npm run build

# ---- stage 2: runtime ---------------------------------------------------------
FROM python:3.11-slim-bookworm AS runtime

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    HOST=0.0.0.0 \
    PORT=8000 \
    HYPERION_STATE_DB=/app/var/hyperion-state.db

WORKDIR /app

# Dependencies first so source edits do not bust the layer cache.
COPY requirements-api.txt ./
RUN pip install --no-cache-dir -r requirements-api.txt

# Application code and the committed, measured artifacts the UI reads.
COPY api/ ./api/
COPY backend_api.py ./
COPY artifacts/ ./artifacts/
COPY experiments/m6/outputs/features.csv experiments/m6/outputs/windows.csv \
     experiments/m6/outputs/results.json ./experiments/m6/outputs/
COPY experiments/m6/m6-lopo-config.json ./experiments/m6/
COPY scripts/ ./scripts/
COPY src/ ./src/
COPY --from=web /web/dist ./web/dist

# Unprivileged runtime user; /app/var is the durable case store volume.
RUN useradd --create-home --uid 10001 crew \
 && mkdir -p /app/var \
 && chown -R crew:crew /app/var
USER crew

VOLUME ["/app/var"]
EXPOSE 8000

# The healthcheck hits the same endpoint the cockpit's badge uses.
HEALTHCHECK --interval=15s --timeout=5s --start-period=20s --retries=3 \
  CMD python -c "import urllib.request,sys; \
sys.exit(0 if urllib.request.urlopen('http://127.0.0.1:8000/api/health', timeout=4).status==200 else 1)"

CMD ["python", "backend_api.py"]
