# Imagem única do backend (F1.8): uma imagem, três entradas (api, worker, cli).
FROM python:3.14.10-slim AS construcao
ENV UV_PYTHON_DOWNLOADS=never UV_LINK_MODE=copy
RUN pip install --no-cache-dir uv==0.13.7
WORKDIR /app
COPY pyproject.toml uv.lock README.md ./
COPY src ./src
RUN uv sync --locked --no-dev --no-editable

FROM python:3.14.10-slim
RUN useradd --system --uid 10001 --no-create-home --shell /usr/sbin/nologin dynaprice \
    && apt-get update && apt-get install -y --no-install-recommends unixodbc \
    && rm -rf /var/lib/apt/lists/*
WORKDIR /app
COPY --from=construcao /app/.venv /app/.venv
COPY docker-entrypoint.sh /usr/local/bin/docker-entrypoint.sh
ENV PATH="/app/.venv/bin:$PATH" PYTHONUNBUFFERED=1 OMP_NUM_THREADS=1
USER 10001:10001
ENTRYPOINT ["docker-entrypoint.sh"]
CMD ["api"]
