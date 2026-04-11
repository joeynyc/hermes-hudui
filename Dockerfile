# Build stage for frontend
FROM node:20-alpine AS frontend-builder

WORKDIR /app/frontend

COPY frontend/package.json frontend/package-lock.json* ./
RUN npm install

COPY frontend/ ./
RUN npm run build

# Production stage
FROM python:3.11-slim

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    && rm -rf /var/lib/apt/lists/*

# Create app directory and non-root user
RUN mkdir -p /app && \
    useradd --create-home appuser && \
    chown -R appuser:appuser /app

WORKDIR /app

# Copy pyproject.toml
COPY pyproject.toml .

# Copy backend source
COPY backend/ ./backend/

# Copy built frontend from builder stage
COPY --from=frontend-builder /app/frontend/dist ./backend/static/

# Ensure static directory exists
RUN chmod -R 755 /app/backend/static

# Create virtual environment and install
RUN python -m venv /app/venv && \
    /app/venv/bin/pip install --upgrade pip && \
    /app/venv/bin/pip install -e . && \
    rm -rf /root/.cache/pip

# Create data directory with correct ownership
RUN mkdir -p /data/hermes && chown -R appuser:appuser /data /app

# Switch to non-root user
USER appuser

# Activate virtual environment in shell
ENV PATH="/app/venv/bin:$PATH" \
    PYTHONUNBUFFERED=1 \
    HERMES_HOME=/data/hermes

# Expose port
EXPOSE 3001

# Run the application
CMD ["hermes-hudui", "--host", "0.0.0.0", "--port", "3001"]