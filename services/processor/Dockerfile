# syntax=docker/dockerfile:1.7
FROM python:3.12-slim AS base
WORKDIR /app
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

FROM base AS builder
COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv

COPY pyproject.toml ./
COPY packages/obs_core/ ./packages/obs_core/
COPY services/processor/ ./services/processor/

RUN uv pip install --system --no-cache \
        ./packages/obs_core \
        ./services/processor

FROM base AS runtime
RUN groupadd --gid 1001 appgroup && \
    useradd --uid 1001 --gid appgroup --no-create-home appuser

COPY --from=builder /usr/local/lib/python3.12/site-packages /usr/local/lib/python3.12/site-packages
COPY services/processor/src /app/src

USER appuser

CMD ["python", "-m", "processor.main"]
