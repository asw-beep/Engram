FROM python:3.12-slim

ENV UV_LINK_MODE=copy \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1
RUN pip install --no-cache-dir uv==0.11.2

WORKDIR /srv/engram
COPY pyproject.toml uv.lock ./
# The cache mount keeps downloaded wheels out of the image layer.
RUN --mount=type=cache,target=/root/.cache/uv uv sync --frozen --no-dev
ENV PATH="/srv/engram/.venv/bin:$PATH"

COPY alembic.ini logging.json docker-entrypoint.sh ./
COPY migrations ./migrations
COPY app ./app
COPY scripts ./scripts

# A user without root, owning the folders that become volumes, so new volumes are writable.
RUN useradd --system --uid 10001 --home-dir /srv/engram engram \
    && mkdir -p /models /data/files /data/downloads \
    && chown -R engram:engram /models /data \
    && chmod +x docker-entrypoint.sh
USER engram

EXPOSE 8000
ENTRYPOINT ["./docker-entrypoint.sh"]
CMD ["uvicorn", "app.main:create_app", "--factory", "--host", "0.0.0.0", "--port", "8000", "--workers", "1", "--log-config", "logging.json"]
