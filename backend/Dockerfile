FROM ghcr.io/astral-sh/uv:python3.11-bookworm-slim

# Intel GPU packages for OpenVINO execution provider
RUN apt-get update && apt-get install -y --no-install-recommends \
    intel-opencl-icd \
    libdrm2 \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev

COPY . .

EXPOSE 8000

CMD ["uv", "run", "uvicorn", "app.api_server:app", "--host", "0.0.0.0", "--port", "8000"]
