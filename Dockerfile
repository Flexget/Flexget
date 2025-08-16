FROM docker.io/python:3.13-alpine@sha256:a70b35b575e33d951e3f9d3fe94163ef0fd338c22552bc587a1b098a87ed6184 AS builder
ENV PYTHONUNBUFFERED=1

RUN --mount=type=cache,target=/var/cache/apk \
    apk add --upgrade \
        ca-certificates \
        nodejs \
        build-base \
        libffi-dev \
        openssl-dev \
        unzip

COPY --from=ghcr.io/astral-sh/uv:0.8.8@sha256:67b2bcccdc103d608727d1b577e58008ef810f751ed324715eb60b3f0c040d30 /uv /uvx /bin/
ENV UV_COMPILE_BYTECODE=1 UV_LINK_MODE=copy
WORKDIR /flexget
RUN --mount=type=cache,target=/root/.cache/uv \
    --mount=type=bind,source=scripts/bundle_webui.py,target=scripts/bundle_webui.py \
    uv run scripts/bundle_webui.py
RUN --mount=type=cache,target=/root/.cache/uv \
    --mount=type=bind,source=uv.lock,target=uv.lock \
    --mount=type=bind,source=pyproject.toml,target=pyproject.toml \
    uv sync --frozen --no-dev --group=all --no-install-project
ADD . /flexget
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --frozen --no-dev --group=all

FROM docker.io/python:3.13-alpine@sha256:a70b35b575e33d951e3f9d3fe94163ef0fd338c22552bc587a1b098a87ed6184
ENV PYTHONUNBUFFERED=1

RUN --mount=type=cache,target=/var/cache/apk \
    apk add --upgrade \
        ca-certificates \
        nodejs \
        tzdata

# Copy the application from the builder
COPY --from=builder --chown=app:app /flexget /flexget

# Place executables in the environment at the front of the path
ENV PATH="/flexget/.venv/bin:$PATH"

VOLUME /config
WORKDIR /config

ENTRYPOINT ["flexget"]
