# API image. Build from this directory: docker build -t financepro-api .
FROM python:3.14-slim AS build
COPY --from=ghcr.io/astral-sh/uv:0.12.16 /uv /bin/uv
ENV UV_COMPILE_BYTECODE=1 UV_LINK_MODE=copy UV_PYTHON_DOWNLOADS=never
WORKDIR /app
# Dependencies first: a code-only change reuses this layer.
COPY pyproject.toml uv.lock ./
RUN uv sync --locked --no-dev --no-install-project
COPY . .
RUN uv sync --locked --no-dev --no-editable

FROM python:3.14-slim
ENV PATH="/app/.venv/bin:$PATH" PYTHONUNBUFFERED=1 ENVIRONMENT=production
WORKDIR /app
COPY --from=build /app/.venv /app/.venv
COPY --from=build /app/alembic.ini /app/alembic.ini
COPY --from=build /app/migrations /app/migrations
RUN useradd --system --create-home financepro
USER financepro
EXPOSE 8000
# Migrations first: a deploy whose migration fails never serves traffic. One process fits the free
# plan's 512 MB; FastAPI runs the synchronous endpoints in its thread pool.
CMD ["sh", "-c", "alembic upgrade head && exec uvicorn financepro.main:app --host 0.0.0.0 --port ${PORT:-8000} --proxy-headers --forwarded-allow-ips '*' --no-server-header"]
