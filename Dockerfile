FROM python:3.12-slim
COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv

WORKDIR /app
ENV UV_LINK_MODE=copy PYTHONUNBUFFERED=1

COPY pyproject.toml README.md ./
COPY src ./src
RUN uv sync --no-dev

COPY ui ./ui
EXPOSE 8000 8501
CMD ["uv", "run", "uvicorn", "api.main:app", "--app-dir", "src", "--host", "0.0.0.0", "--port", "8000"]
