# Stage 1: Build console static assets
FROM node:22-slim AS console-build
WORKDIR /app/console
COPY console/package.json console/package-lock.json ./
RUN npm ci --ignore-scripts
COPY console/ ./
RUN npm run build

# Stage 2: Python application
FROM python:3.11-slim AS app

# Install system deps for asyncpg and sentence-transformers
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc libpq-dev && \
    rm -rf /var/lib/apt/lists/*

# Install uv
COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv

WORKDIR /app

# Install Python dependencies (cached layer)
COPY pyproject.toml ./
RUN uv sync --extra local-embeddings --no-dev --no-install-project

# Copy source code
COPY src/ src/
COPY config.yaml ./
COPY migrations/ migrations/

# Copy built console
COPY --from=console-build /app/console/dist console/dist

# Install the project itself
RUN uv sync --extra local-embeddings --no-dev

# Pre-download the embedding model at build time
RUN uv run python -c "from sentence_transformers import SentenceTransformer; SentenceTransformer('BAAI/bge-small-zh-v1.5')"

EXPOSE 8420

CMD ["uv", "run", "cortex", "serve"]
