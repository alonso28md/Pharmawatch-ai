# --- web interface: static build served by FastAPI at /app ----------------------------
FROM node:24-slim AS frontend

WORKDIR /web
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci --no-audit --no-fund
COPY frontend/ ./
RUN npm run build

# --- build stage: compilers live only here ------------------------------------------
FROM python:3.14-slim AS builder

RUN apt-get update && apt-get install -y --no-install-recommends build-essential \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app
RUN python -m venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH" \
    HF_HOME=/opt/hf \
    PYTHONDONTWRITEBYTECODE=1

COPY requirements.txt requirements.lock ./
RUN pip install --no-cache-dir -r requirements.txt -c requirements.lock

COPY src/ src/
COPY data/ data/
COPY scripts/ scripts/
COPY config/ config/

# Index the regulatory documents (downloads the embedding model into HF_HOME once).
RUN python scripts/ingest_documents.py

# --- runtime stage --------------------------------------------------------------------
FROM python:3.14-slim

RUN apt-get update && apt-get install -y --no-install-recommends curl \
    && rm -rf /var/lib/apt/lists/* \
    && useradd --create-home --uid 10001 app

WORKDIR /app
ENV PATH="/opt/venv/bin:$PATH" \
    HF_HOME=/opt/hf \
    HF_HUB_OFFLINE=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

COPY --from=builder /opt/venv /opt/venv
COPY --from=builder /opt/hf /opt/hf
COPY --from=builder --chown=app:app /app /app
COPY --chown=app:app static/ static/
COPY --from=frontend --chown=app:app /web/dist frontend/dist

USER app
EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=10s --start-period=60s --retries=3 \
    CMD curl -f http://localhost:8000/health || exit 1

CMD ["uvicorn", "src.api.main:app", "--host", "0.0.0.0", "--port", "8000"]
