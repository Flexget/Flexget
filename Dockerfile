FROM docker.io/python:3.14-alpine@sha256:f6a589d43c42b9e7f7dc67a12d37132491f362859a5d750607710cc56da3bc72 AS builder
ENV PYTHONUNBUFFERED=1

RUN apk update && apk add --upgrade \
        ca-certificates \
        nodejs \
        build-base \
        libffi-dev \
        openssl-dev \
        unzip

COPY --from=ghcr.io/astral-sh/uv:0.12.19@sha256:04d046b13e60d6bcec73cbc5e1cad25d680dea90c8573340950a0ac2d1aef424 /uv /uvx /bin/
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

FROM docker.io/python:3.14-alpine@sha256:f6a589d43c42b9e7f7dc67a12d37132491f362859a5d750607710cc56da3bc72
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
