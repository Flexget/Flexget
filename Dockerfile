FROM docker.io/python:3.11-alpine@sha256:d5e2fc72296647869f5eeb09e7741088a1841195059de842b05b94cb9d3771bb AS builder
ENV PYTHONUNBUFFERED=1

RUN --mount=type=cache,target=/var/cache/apk \
    apk add --upgrade \
        ca-certificates \
        nodejs \
        build-base \
        libffi-dev \
        openssl-dev \
        unzip

COPY --from=ghcr.io/astral-sh/uv:0.6.4@sha256:0d686193e6d06a262184e4367d00276e24a524357080868c1732c2718f75d4d9 /uv /uvx /bin/
ENV UV_COMPILE_BYTECODE=1 UV_LINK_MODE=copy
WORKDIR /flexget
RUN --mount=type=cache,target=/root/.cache/uv \
    --mount=type=bind,source=bundle_webui.py,target=bundle_webui.py \
    uv run bundle_webui.py
RUN --mount=type=cache,target=/root/.cache/uv \
    --mount=type=bind,source=uv.lock,target=uv.lock \
    --mount=type=bind,source=pyproject.toml,target=pyproject.toml \
    uv sync --frozen --no-dev --group=all --no-install-project
ADD . /flexget
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --frozen --no-dev --group=all

# Final image without uv
# TODO: Alpine version is pinned due to https://github.com/Flexget/Flexget/issues/4085
FROM docker.io/python:3.11-alpine3.20@sha256:520924f35357a374aa1beaa81b867f449f9f12a53f00b69ad03c3d697fdf4aad
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
