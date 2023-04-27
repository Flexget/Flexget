FROM docker.io/python:3.11-alpine as builder
ENV PYTHONUNBUFFERED 1

RUN apk add --no-cache --upgrade \
        ca-certificates \
        nodejs \
        build-base \
        libffi-dev \
        openssl-dev \
        unzip && \
    rm -rf /var/cache/apk/*

WORKDIR /wheels

COPY .. /flexget

RUN pip install -U pip && \
    pip install -r /flexget/dev-requirements.txt
RUN python /flexget/dev_tools.py bundle-webui
RUN pip wheel -e /flexget

FROM localhost:5000/name/app:latest

COPY --from=builder /wheels /wheels

RUN ls -ahl /wheels && \
    pip install --no-cache-dir \
                --no-index \
                -f /wheels \
                FlexGet && \
    rm -rf /wheels
