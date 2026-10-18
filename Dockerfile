FROM docker.io/python:3.11-alpine@sha256:d9368b3a5ac59afea7b5d4f2e2aea0941dbf9fdee9c369c5bec00b98244bc929 AS builder
COPY --from=ghcr.io/astral-sh/uv:0.13.0@sha256:cdc6093146eb3ff6a40107b38f008b789e050e77ad87865e381d9917da55a168 /uv /uvx /bin/
ENV UV_COMPILE_BYTECODE=1 UV_LINK_MODE=copy
WORKDIR /flexget
RUN --mount=type=cache,target=/root/.cache/uv \
    --mount=type=bind,source=scripts/bundle_webui.py,target=scripts/bundle_webui.py \
    uv run scripts/bundle_webui.py
RUN --mount=type=cache,target=/root/.cache/uv \
    --mount=type=bind,source=uv.lock,target=uv.lock \
    uv export --frozen --no-dev --group=all --no-emit-project -o pylock.toml -q && \
    uv pip install --prefix /root-dir/usr/local -r pylock.toml
COPY . /flexget
RUN --mount=type=cache,target=/root/.cache/uv \
    uv export --locked --no-dev --no-editable -o pylock.toml -q && \
    BUNDLE_WEBUI_MODE=local uv pip install --prefix /root-dir/usr/local -r pylock.toml

FROM docker.io/python:3.11-alpine@sha256:d9368b3a5ac59afea7b5d4f2e2aea0941dbf9fdee9c369c5bec00b98244bc929
ENV PYTHONUNBUFFERED=1
COPY --from=builder /root-dir /
VOLUME /config
WORKDIR /config
ENTRYPOINT ["flexget"]
