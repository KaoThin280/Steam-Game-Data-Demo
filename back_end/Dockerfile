# ============== Stage 1: Build dependencies ==============
FROM python:3.12-slim AS builder

WORKDIR /app

# Cài build tools cho một số package cần compile
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    gcc \
    libpq-dev \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements và cài dependencies vào folder riêng
COPY requirements.txt .
RUN python -m venv /opt/venv \
    && /opt/venv/bin/pip install --no-cache-dir --upgrade pip \
    && /opt/venv/bin/pip install --no-cache-dir -r requirements.txt


# ============== Stage 2: Runtime ==============
FROM python:3.12-slim

WORKDIR /app

# Cài runtime dependencies cho PostgreSQL client
RUN apt-get update && apt-get install -y --no-install-recommends \
    libpq5 \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Copy Python packages từ builder
COPY --from=builder /opt/venv /opt/venv
ENV PATH=/opt/venv/bin:$PATH \
    PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1

# Copy source code
COPY . .

# Tạo user non-root để bảo mật
RUN useradd -m -u 1000 appuser && chown -R appuser:appuser /app

COPY certs/supabase-ca.crt /usr/local/share/ca-certificates/supabase-ca.crt
RUN update-ca-certificates

USER appuser

# Expose port
EXPOSE 8000

# Healthcheck
HEALTHCHECK --interval=30s --timeout=10s --start-period=20s --retries=3 \
    CMD python -m app.healthcheck http://127.0.0.1:8000/health

# Run với uvicorn
# The free-tier deployment uses an in-process live-task registry. One worker is
# required for deterministic cancellation; scale via a durable worker queue first.
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "1", "--proxy-headers", "--forwarded-allow-ips", "127.0.0.1"]
