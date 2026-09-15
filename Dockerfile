# Build stage
FROM python:3.11-slim as backend-builder

WORKDIR /build

# Install build dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    && rm -rf /var/lib/apt/lists/*

COPY backend/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Frontend build stage
FROM node:18-alpine as frontend-builder

WORKDIR /build

COPY frontend/package*.json ./
RUN npm ci

COPY frontend . .
RUN npm run build

# Runtime stage
FROM python:3.11-slim

WORKDIR /app

# Install runtime dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Create non-root user
RUN useradd -m -u 1000 appuser

# Copy Python dependencies from builder
COPY --from=backend-builder /usr/local/lib/python3.11/site-packages /usr/local/lib/python3.11/site-packages
COPY --from=backend-builder /usr/local/bin /usr/local/bin

# Copy backend
COPY backend/app ./app
COPY backend/alembic ./alembic
COPY backend/alembic.ini .

# Copy frontend dist
COPY --from=frontend-builder /build/dist ./app/static

# Create necessary directories
RUN mkdir -p /config && chown -R appuser:appuser /app /config

# Switch to non-root user
USER appuser

# Environment
ENV PYTHONUNBUFFERED=1
ENV DATABASE_PATH=/config/franchise-manager.db

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=40s --retries=3 \
    CMD curl -f http://localhost:${APP_PORT:-8787}/api/health || exit 1

EXPOSE 8787

CMD ["python", "-m", "uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8787"]
