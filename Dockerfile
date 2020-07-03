FROM python:3-alpine
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
    pip wheel transmissionrpc && \
    pip wheel deluge-client && \
    pip wheel cloudscraper

WORKDIR /flexget-ui-v2
RUN wget https://github.com/Flexget/webui/releases/latest/download/dist.zip && \
    unzip dist.zip && \
    rm dist.zip

FROM python:3-alpine
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
                transmissionrpc \
                deluge-client \
                cloudscraper && \
    rm -rf /wheels

COPY --from=0 /flexget-ui-v2 /usr/local/lib/python3.8/site-packages/flexget/ui/v2/

RUN mkdir /root/.flexget
VOLUME /root/.flexget

ENTRYPOINT ["flexget"]
