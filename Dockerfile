# syntax=docker/dockerfile:1.6

# ── Stage 1: builder ─────────────────────────────────────────────────────────
FROM python:3.11-slim AS builder

ENV PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

RUN apt-get update && apt-get install -y --no-install-recommends \
        build-essential \
        libpoppler-cpp-dev \
        pkg-config \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /build
COPY requirements.txt ./

# CPU-only torch wheels.  By default `pip install torch` on Linux x86_64 pulls
# the full CUDA stack (~6 GB of nvidia-*, triton, cudnn).  We force the CPU
# index so docling/gliner reuse the small CPU build.
RUN pip install --prefix=/install \
        --index-url https://download.pytorch.org/whl/cpu \
        --extra-index-url https://pypi.org/simple \
        torch==2.5.1 torchvision==0.20.1

# Now the rest — they will see torch already satisfied and skip the GPU wheels.
RUN pip install --prefix=/install -r requirements.txt


# ── Stage 2: runtime ─────────────────────────────────────────────────────────
FROM python:3.11-slim AS runtime

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    HF_HOME=/home/app/.cache/huggingface \
    TRANSFORMERS_CACHE=/home/app/.cache/huggingface \
    XDG_CACHE_HOME=/home/app/.cache

# System deps:
#   tesseract-ocr  — Apache-2.0 OCR backend
#   poppler-utils  — invoked as subprocess only (no GPL linking)
#   libgl1/libglib — image ops (Pillow, OpenCV transitive)
#   curl           — healthcheck
RUN apt-get update && apt-get install -y --no-install-recommends \
        tesseract-ocr \
        tesseract-ocr-eng \
        poppler-utils \
        libgl1 \
        libglib2.0-0 \
        curl \
    && rm -rf /var/lib/apt/lists/*

# Non-root user
RUN useradd --create-home --shell /bin/bash app
WORKDIR /app

# Bring in installed packages
COPY --from=builder /install /usr/local

# App code
COPY --chown=app:app server ./server
COPY --chown=app:app requirements.txt ./

# Pre-warm models so first request doesn't pay the download cost.
# Failure here is non-fatal — runtime will lazy-load if cache is missing.
USER app
RUN python -m server.scripts.prewarm || true

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=20s --retries=3 \
    CMD curl -fsS http://localhost:8000/health || exit 1

CMD ["uvicorn", "server.main:app", "--host", "0.0.0.0", "--port", "8000"]
