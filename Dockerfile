FROM ghcr.io/astral-sh/uv:python3.11-bookworm-slim

WORKDIR /app

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONPATH=/app \
    UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy

# The adaly-python index needs a Google access token. This image is built by Cloud Build (gcloud run deploy
# --source), whose Docker builder has no BuildKit (no secret mounts); the token comes from the build's own identity
# via the metadata server and lives only inside this RUN step.
COPY pyproject.toml uv.lock ./
RUN export UV_INDEX_ADALY_PYTHON_USERNAME=oauth2accesstoken \
    && UV_INDEX_ADALY_PYTHON_PASSWORD="$(python -c 'import json,urllib.request as u; r=u.Request("http://metadata.google.internal/computeMetadata/v1/instance/service-accounts/default/token", headers={"Metadata-Flavor": "Google"}); print(json.load(u.urlopen(r, timeout=5))["access_token"])')" \
    && export UV_INDEX_ADALY_PYTHON_PASSWORD \
    && uv sync --frozen --no-dev --no-install-project

COPY . .
RUN uv sync --frozen --no-dev

CMD ["uv", "run", "server.py"]
