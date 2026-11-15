FROM docker.io/python:3.11-alpine@sha256:7fbad8e4652eae0186429a6f26cf5b23e27e8c6fd7ac4d0cfd7a6988cdeea1e1 AS builder
COPY --from=ghcr.io/astral-sh/uv:0.13.7@sha256:96f40d3904aad8d0bd010539001d36c8e2188b981e1334471a90c4a1d93bb490 /uv /uvx /bin/
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

FROM docker.io/python:3.11-alpine@sha256:7fbad8e4652eae0186429a6f26cf5b23e27e8c6fd7ac4d0cfd7a6988cdeea1e1
ENV PYTHONUNBUFFERED=1
COPY --from=builder /root-dir /
VOLUME /config
WORKDIR /config
ENTRYPOINT ["flexget"]
