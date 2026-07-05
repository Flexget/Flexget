FROM docker.io/python:3.11-alpine@sha256:cf0253107a1e77e63c814a05428308965a47eb44a2d62fc828564c4a8c839fab AS builder
ENV PYTHONUNBUFFERED=1

RUN apk update && apk add --upgrade \
        ca-certificates \
        nodejs \
        build-base \
        libffi-dev \
        openssl-dev \
        unzip

COPY --from=ghcr.io/astral-sh/uv:0.11.26@sha256:3d868e555f8f1dbc324afa005066cd11e1053fc4743b9808ca8025283e65efa5 /uv /uvx /bin/
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

FROM docker.io/python:3.11-alpine@sha256:cf0253107a1e77e63c814a05428308965a47eb44a2d62fc828564c4a8c839fab
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
