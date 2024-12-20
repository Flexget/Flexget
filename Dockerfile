# TODO: Alpine version is pinned due to https://github.com/Flexget/Flexget/issues/4085
FROM docker.io/python:3.11-alpine3.20
ENV PYTHONUNBUFFERED=1

RUN apk add --no-cache --upgrade \
        ca-certificates \
        nodejs \
        build-base \
        libffi-dev \
        openssl-dev \
        unzip && \
    rm -rf /var/cache/apk/*

RUN pip install -U pip

COPY requirements-docker.txt /flexget/
RUN pip wheel --wheel-dir /dep-wheels -r /flexget/requirements-docker.txt

COPY dev_tools.py /flexget/
RUN pip install -f /dep-wheels click requests && python /flexget/dev_tools.py bundle-webui --version=v2
COPY . /flexget
RUN pip wheel --no-deps --wheel-dir /wheels -e /flexget

# TODO: Alpine version is pinned due to https://github.com/Flexget/Flexget/issues/4085
FROM docker.io/python:3.11-alpine3.20
ENV PYTHONUNBUFFERED=1

RUN apk add --no-cache --upgrade \
        ca-certificates \
        nodejs \
        tzdata && \
    rm -rf /var/cache/apk/*

COPY --from=0 /dep-wheels /dep-wheels
COPY --from=0 /flexget/requirements-docker.txt /requirements-docker.txt
COPY --from=0 /wheels /wheels

RUN pip install -U pip && \
    pip install --no-cache-dir \
                --no-index \
                -f /dep-wheels \
                -f /wheels \
                FlexGet \
                -r /requirements-docker.txt && \
    rm -rf /wheels /dep-wheels /requirements-docker.txt

VOLUME /config
WORKDIR /config

ENTRYPOINT ["flexget"]
