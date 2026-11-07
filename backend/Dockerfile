FROM python:3.12-slim

ENV UV_LINK_MODE=copy
RUN pip install --no-cache-dir uv==0.11.2

WORKDIR /srv/engram
COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev

COPY app ./app
COPY scripts ./scripts

EXPOSE 8000
CMD ["uv", "run", "--frozen", "--no-dev", "uvicorn", "app.main:create_app", "--factory", "--host", "0.0.0.0", "--port", "8000", "--workers", "1"]
