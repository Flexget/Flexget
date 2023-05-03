FROM docker.io/python:3.11-alpine
ENV PYTHONUNBUFFERED 1

RUN apk add --no-cache --upgrade \
        ca-certificates \
        nodejs \
        build-base \
        libffi-dev \
        openssl-dev \
        git \
        cargo \
        rust \
        unzip && \
    rm -rf /var/cache/apk/*

WORKDIR /wheels

COPY . /flexget

ENV CARGO_NET_GIT_FETCH_WITH_CLI true
RUN pip install -U pip && \
    pip install -r /flexget/dev-requirements.txt
RUN python /flexget/dev_tools.py bundle-webui --version=v2
RUN pip wheel -r /flexget/requirements-docker.txt && \
    pip wheel -e /flexget

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
                FlexGet \
                -r /requirements-docker.txt && \
    rm -rf /wheels /requirements-docker.txt

VOLUME /config
WORKDIR /config

ENTRYPOINT ["flexget"]
