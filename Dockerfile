# syntax=docker/dockerfile:1
FROM ghcr.io/astral-sh/uv:python3.11-bookworm-slim

WORKDIR /app

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONPATH=/app \
    UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy

# The adaly-python index needs a Google access token: CI passes one as the adaly_py_token build secret; on Cloud
# Build the build's own identity is used through the metadata server.
COPY pyproject.toml uv.lock ./
RUN --mount=type=secret,id=adaly_py_token,required=false \
    export UV_INDEX_ADALY_PYTHON_USERNAME=oauth2accesstoken \
    && UV_INDEX_ADALY_PYTHON_PASSWORD="$(cat /run/secrets/adaly_py_token 2>/dev/null || python -c 'import json,urllib.request as u; r=u.Request("http://metadata.google.internal/computeMetadata/v1/instance/service-accounts/default/token", headers={"Metadata-Flavor": "Google"}); print(json.load(u.urlopen(r, timeout=5))["access_token"])')" \
    && export UV_INDEX_ADALY_PYTHON_PASSWORD \
    && uv sync --frozen --no-dev --no-install-project

COPY . .
RUN uv sync --frozen --no-dev

CMD ["uv", "run", "server.py"]
