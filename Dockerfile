FROM docker.io/python:3.9-alpine
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
    pip wheel -e /flexget && \
    pip wheel 'transmission-rpc>=3.0.0,<4.0.0' && \
    pip wheel deluge-client && \
    pip wheel cloudscraper

WORKDIR /flexget-ui-v2
RUN wget https://github.com/Flexget/webui/releases/latest/download/dist.zip && \
    unzip dist.zip && \
    rm dist.zip

FROM docker.io/python:3.9-alpine
ENV PYTHONUNBUFFERED 1

RUN apk add --no-cache --upgrade \
        ca-certificates \
        nodejs && \
    rm -rf /var/cache/apk/*

COPY --from=0 /wheels /wheels

RUN pip install -U pip && \
    pip install --no-cache-dir \
                --no-index \
                -f /wheels \
                FlexGet \
                'transmission-rpc>=3.0.0,<4.0.0' \
                deluge-client \
                cloudscraper && \
    rm -rf /wheels

COPY --from=0 /flexget-ui-v2 /usr/local/lib/python3.9/site-packages/flexget/ui/v2/

RUN mkdir /root/.flexget
VOLUME /root/.flexget

ENTRYPOINT ["flexget"]
