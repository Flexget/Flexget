FROM docker.io/python:3.11-alpine@sha256:bb1d70c1df30d8ee1e05214dbe82d6cdfd29833c1f47ce917f20991aca93acaa AS builder
COPY --from=ghcr.io/astral-sh/uv:0.13.6@sha256:af22a52f5eafef3d78e551599d405c02df61919d18028f0cea8eda93bc9986d0 /uv /uvx /bin/
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

FROM docker.io/python:3.11-alpine@sha256:bb1d70c1df30d8ee1e05214dbe82d6cdfd29833c1f47ce917f20991aca93acaa
ENV PYTHONUNBUFFERED=1
COPY --from=builder /root-dir /
VOLUME /config
WORKDIR /config
ENTRYPOINT ["flexget"]
