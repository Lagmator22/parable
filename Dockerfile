# Multi-stage universal Docker build (Render Free, Koyeb Free, Railway, Fly, or local Docker)
FROM node:22-bookworm-slim AS frontend-builder
WORKDIR /app/frontend
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci --no-audit --no-fund
COPY frontend/ ./
RUN npm run build

FROM node:22-bookworm-slim AS bridge-builder
WORKDIR /app/arkiv-bridge
COPY arkiv-bridge/package.json arkiv-bridge/package-lock.json ./
RUN npm ci --omit=dev --no-audit --no-fund

FROM python:3.12-slim-bookworm AS runtime
WORKDIR /app

COPY --from=ghcr.io/astral-sh/uv:0.6.12 /uv /usr/local/bin/uv
COPY --from=node:22-bookworm-slim /usr/local/bin/node /usr/local/bin/node

ENV UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    PYTHONUNBUFFERED=1 \
    PATH="/app/engine/.venv/bin:$PATH"

COPY engine/pyproject.toml engine/uv.lock /app/engine/
RUN cd /app/engine && uv sync --frozen --no-dev --no-install-project

COPY engine/parable /app/engine/parable
COPY --from=frontend-builder /app/frontend/dist /app/frontend/dist
COPY arkiv-bridge/index.mjs arkiv-bridge/package.json /app/arkiv-bridge/
COPY --from=bridge-builder /app/arkiv-bridge/node_modules /app/arkiv-bridge/node_modules
COPY deploy/docker-start.sh /app/deploy/docker-start.sh
RUN chmod +x /app/deploy/docker-start.sh

EXPOSE 8000
CMD ["/app/deploy/docker-start.sh"]
