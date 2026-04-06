FROM ghcr.io/astral-sh/uv:python3.13-bookworm-slim

WORKDIR /app

COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev

COPY . .
RUN uv sync --frozen --no-dev

EXPOSE 8000

CMD ["sh", "-c", "uv run python main.py & PIPELINE_PID=$!; trap 'kill $PIPELINE_PID 2>/dev/null || true' INT TERM; uv run uvicorn app.api_server:app --host 0.0.0.0 --port 8000; STATUS=$?; kill $PIPELINE_PID 2>/dev/null || true; wait $PIPELINE_PID 2>/dev/null || true; exit $STATUS"]
