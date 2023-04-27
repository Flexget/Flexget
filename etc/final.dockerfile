FROM docker.io/python:3.11-alpine
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

COPY . /flexget

RUN pip install -U pip && \
    pip install -r /flexget/dev-requirements.txt
RUN python /flexget/dev_tools.py bundle-webui
RUN pip wheel -e /flexget

FROM localhost:5000/flexget:base

COPY --from=0 /wheels /wheels
COPY --from=0 /flexget/requirements-docker.txt /requirements-docker.txt

RUN pip install -U pip && \
    pip install --no-cache-dir \
                --no-index \
                FlexGet && \
    rm -rf /wheels
