FROM ghcr.io/astral-sh/uv:python3.13-bookworm-slim

WORKDIR /app

COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev

COPY . .
RUN uv sync --frozen --no-dev
RUN chmod +x /app/start.sh

EXPOSE 8000

CMD ["/app/start.sh"]
