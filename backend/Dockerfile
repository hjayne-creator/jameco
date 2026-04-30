# ── builder stage ────────────────────────────────────────────────────────────
FROM python:3.13-slim AS builder

WORKDIR /app

# System deps required to compile lxml / beautifulsoup4's lxml extras
RUN apt-get update && apt-get install -y --no-install-recommends \
        gcc \
        libxml2-dev \
        libxslt-dev \
    && rm -rf /var/lib/apt/lists/*

# Install Python dependencies into an isolated prefix so we can copy them
# cleanly into the runtime image without dragging in build tools.
COPY pyproject.toml .
RUN pip install --upgrade pip \
    && pip install --prefix=/install . --no-cache-dir

# ── runtime stage ─────────────────────────────────────────────────────────────
FROM python:3.13-slim AS runtime

WORKDIR /app

# Runtime shared libraries needed by lxml
RUN apt-get update && apt-get install -y --no-install-recommends \
        libxml2 \
        libxslt1.1 \
    && rm -rf /var/lib/apt/lists/*

# Copy installed packages from builder
COPY --from=builder /install /usr/local

# Copy application source
COPY app/ app/

EXPOSE 8000

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
