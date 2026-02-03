# Publisher Dockerfile
FROM python:3.14-slim

# Set working directory
WORKDIR /app

# Install uv
COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/

# Copy project files
COPY pyproject.toml .
COPY .python-version .
COPY uv.lock .

# Copy source code
COPY src/ src/
COPY data/ data/

# Install dependencies
RUN uv sync --frozen --no-dev

# Run publisher
CMD ["uv", "run", "-m", "src.publisher.main"]
