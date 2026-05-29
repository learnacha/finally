# Stage 1: Build Next.js frontend as static export
FROM node:20-slim AS frontend-builder

WORKDIR /app/frontend

# Copy package files first for better layer caching
COPY frontend/package*.json ./

RUN npm ci

# Copy the rest of the frontend source
COPY frontend/ ./

# Build the static export (output goes to frontend/out/)
RUN npm run build


# Stage 2: Python backend with uv
FROM python:3.12-slim AS final

WORKDIR /app

# Install uv
RUN pip install uv --no-cache-dir

# Copy backend project files
COPY backend/pyproject.toml backend/uv.lock ./

# Install Python dependencies from lockfile (no dev deps)
RUN uv sync --frozen --no-dev

# Copy the backend application code
COPY backend/ ./

# Copy the frontend static export from Stage 1
COPY --from=frontend-builder /app/frontend/out ./static

# Create db directory for SQLite volume mount
RUN mkdir -p /app/db

EXPOSE 8000

CMD ["uv", "run", "uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
