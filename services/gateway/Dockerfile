# syntax=docker/dockerfile:1.7
FROM python:3.12-slim AS base
WORKDIR /app
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

# ── Build stage: install deps ─────────────────────────────────────────────────
FROM base AS builder
COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv

# Copy workspace manifests first for layer caching
COPY pyproject.toml ./
COPY packages/obs_core/ ./packages/obs_core/
COPY services/gateway/ ./services/gateway/

# Install only gateway + obs_core (no dev extras)
RUN uv sync --no-dev \
        --package obs-gateway \
        --no-install-workspace \
    && uv pip install \
        --system \
        --no-cache \
        ./packages/obs_core \
        ./services/gateway

# ── Runtime stage ─────────────────────────────────────────────────────────────
FROM base AS runtime
# Least-privilege: non-root user
RUN groupadd --gid 1001 appgroup && \
    useradd --uid 1001 --gid appgroup --no-create-home appuser

COPY --from=builder /usr/local/lib/python3.12/site-packages /usr/local/lib/python3.12/site-packages
COPY --from=builder /usr/local/bin/uvicorn /usr/local/bin/uvicorn
COPY services/gateway/src /app/src

USER appuser
EXPOSE 8080

# Workload Identity provides credentials via the metadata server — no key files.
CMD ["uvicorn", "gateway.main:app", \
     "--host", "0.0.0.0", \
     "--port", "8080", \
     "--log-config", "none"]
