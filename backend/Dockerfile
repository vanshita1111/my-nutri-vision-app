# ─────────────────────────────────────────────────────────────────────────────
# NutriVision Backend — Multi-stage Dockerfile
# ─────────────────────────────────────────────────────────────────────────────
#
# Stage 1 (builder): install Python deps into a virtual env
# Stage 2 (runtime): copy only the venv — no build tools in final image
#
# Result: final image is ~40% smaller and has no compiler toolchain.

# ── Stage 1: build ────────────────────────────────────────────────────────────
FROM python:3.12-slim AS builder

# System deps needed only to compile Python packages (psycopg2, etc.)
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc g++ libpq-dev \
    && rm -rf /var/lib/apt/lists/*

# Create a virtual environment so we can copy it cleanly into the runtime stage
RUN python -m venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

# Install dependencies first (separate layer — cached unless requirements change)
COPY requirements.txt .
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

# ── Stage 2: runtime ──────────────────────────────────────────────────────────
FROM python:3.12-slim AS runtime

# Runtime system deps only (OpenCV needs libglib/libGL; curl for health checks)
RUN apt-get update && apt-get install -y --no-install-recommends \
    libglib2.0-0 libgl1 libsm6 libxext6 libxrender1 \
    libpq5 \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Copy the pre-built virtual env from builder
COPY --from=builder /opt/venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

# ── Non-root user (security best practice) ────────────────────────────────────
RUN groupadd --gid 1001 appuser && \
    useradd  --uid 1001 --gid 1001 --no-create-home appuser

WORKDIR /app

# Copy application code
COPY --chown=appuser:appuser . .

# Create writable directories the app needs
RUN mkdir -p local_image_storage && \
    chown -R appuser:appuser local_image_storage

USER appuser

ENV PYTHONPATH=/app
ENV PYTHONUNBUFFERED=1
ENV PYTHONDONTWRITEBYTECODE=1

EXPOSE 8000

# Default command (overridden by docker-compose)
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
