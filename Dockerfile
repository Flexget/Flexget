FROM docker.io/python:3.11-alpine@sha256:09d17d5e4c16d0a7a1eea690bcb7c6ab8616b211f8421e429e97c1bef5bd0ed2 AS builder
COPY --from=ghcr.io/astral-sh/uv:0.13.5@sha256:32a7bb39b496babbd997b0a39a4d66c126bdaf5661b302bf6f06abda8deca6ff /uv /uvx /bin/
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

FROM docker.io/python:3.11-alpine@sha256:09d17d5e4c16d0a7a1eea690bcb7c6ab8616b211f8421e429e97c1bef5bd0ed2
ENV PYTHONUNBUFFERED=1
COPY --from=builder /root-dir /
VOLUME /config
WORKDIR /config
ENTRYPOINT ["flexget"]
