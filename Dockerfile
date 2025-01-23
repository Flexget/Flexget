FROM docker.io/python:3.11-alpine@sha256:9af3561825050da182afc74b106388af570b99c500a69c8216263aa245a2001b AS builder
ENV PYTHONUNBUFFERED=1

RUN --mount=type=cache,target=/var/cache/apk \
    apk add --upgrade \
        ca-certificates \
        nodejs \
        build-base \
        libffi-dev \
        openssl-dev \
        unzip

COPY --from=ghcr.io/astral-sh/uv:0.5.22@sha256:db7daf75d8f12d1c982df42d9b01519fc8fca98a89a91a7623a088d07408221f /uv /uvx /bin/
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
FROM docker.io/python:3.11-alpine3.20@sha256:6e18772230b36e78251ed179a2a2a2b3cc94726f02e1fddccdcfbe05b17bdc96
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
