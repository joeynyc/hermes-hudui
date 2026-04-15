# syntax=docker/dockerfile:1.7

# ── Stage 1: build the React frontend ────────────────────────────────────────
FROM node:20-alpine AS frontend-builder

WORKDIR /build/frontend

# Install dependencies first so the npm-install layer is cached when only
# application source changes.
COPY frontend/package.json frontend/package-lock.json ./
RUN --mount=type=cache,target=/root/.npm npm ci --no-audit --no-fund

COPY frontend/ ./
RUN npm run build


# ── Stage 2: Python runtime ──────────────────────────────────────────────────
FROM python:3.12-slim AS runtime

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

# Install the package metadata first so the pip-install layer caches when
# only backend source changes.
COPY pyproject.toml README.md ./
COPY backend/ ./backend/

# Drop the built frontend into backend/static (mirrors install.sh).
COPY --from=frontend-builder /build/frontend/dist/index.html backend/static/index.html
COPY --from=frontend-builder /build/frontend/dist/assets/    backend/static/assets/

RUN pip install --no-cache-dir .

# Run as a non-root user. Cleaner uid/gid than the python:slim default.
RUN addgroup --system --gid 1000 hermes \
 && adduser  --system --uid 1000 --ingroup hermes --home /home/hermes hermes \
 && chown -R hermes:hermes /app /home/hermes
USER hermes

EXPOSE 3001

# `--host 0.0.0.0` is needed inside a container so the port mapping reaches
# the FastAPI app (the in-process default is 127.0.0.1 for safety).
ENTRYPOINT ["hermes-hudui"]
CMD ["--host", "0.0.0.0", "--port", "3001"]

# Hit the API health endpoint Docker can use to mark the container live/dead.
HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD python -c "import urllib.request, sys; \
sys.exit(0 if urllib.request.urlopen('http://127.0.0.1:3001/api/health', timeout=3).status == 200 else 1)" \
    || exit 1
