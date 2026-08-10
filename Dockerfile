# Servizon — container image for a public demo deployment.
#
# The application is designed to run on a closed network as a single process
# serving both the API and the built interface. That is exactly what this image
# does, so the demo and the real deployment have the same shape.
#
# Two stages: Node builds the frontend, then a slim Python runtime serves it.
# The Node toolchain never reaches the final image.

# --- stage 1: build the interface ------------------------------------------
FROM node:20-alpine AS frontend

WORKDIR /build

# Copy manifests first so the dependency layer is cached independently of
# source changes — a CSS edit should not reinstall node_modules.
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci

COPY frontend/ ./
RUN npm run build


# --- stage 2: runtime -------------------------------------------------------
FROM python:3.12-slim

# Keeps the image small and the logs unbuffered so a crash is visible in the
# host's log viewer rather than swallowed by Python's output buffer.
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

COPY backend/requirements.txt backend/requirements.txt
RUN pip install --no-cache-dir -r backend/requirements.txt

COPY backend/ backend/
COPY scripts/ scripts/

# The layout the application expects: config.py resolves the interface to
# <project root>/frontend/dist, one level above the backend package.
COPY --from=frontend /build/dist frontend/dist

# Run as an unprivileged user. The scenario store writes a SQLite file, so the
# data directory has to be writable by that user.
RUN useradd --create-home --uid 10001 servizon \
    && mkdir -p /app/backend/data /app/backend/logs \
    && chown -R servizon:servizon /app
USER servizon

WORKDIR /app/backend

EXPOSE 8000

# Hosts inject the port. Shell form so ${PORT} is expanded at start-up; the
# default keeps `docker run -p 8000:8000` working locally.
CMD uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000}
