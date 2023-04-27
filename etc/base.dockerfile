FROM docker.io/python:3.11-alpine
ENV PYTHONUNBUFFERED 1

RUN apk add --no-cache --upgrade \
        ca-certificates \
        build-base \
        libffi-dev \
        openssl-dev \
        unzip

WORKDIR /wheels

COPY ./requirements-docker.txt /flexget/

RUN pip install -U pip && \
    pip wheel -r /flexget/requirements-docker.txt

FROM docker.io/python:3.11-alpine
ENV PYTHONUNBUFFERED 1

RUN apk add --no-cache --upgrade \
        ca-certificates \
        nodejs \
        tzdata && \
    rm -rf /var/cache/apk/*

COPY --from=0 /wheels /wheels
COPY --from=0 /flexget/requirements-docker.txt /requirements-docker.txt

RUN pip install -U pip && \
    pip install --no-cache-dir \
                --no-index \
                -f /wheels \
                -r /requirements-docker.txt && \
    rm -rf /wheels /requirements-docker.txt

VOLUME /config
WORKDIR /config

ENTRYPOINT ["flexget"]
