FROM alpine
MAINTAINER Rémi Alvergnat <toilal.dev@gmail.com>

RUN apk add --update python3 ca-certificates nodejs build-base python3-dev libffi-dev openssl-dev unzip && \
    rm -rf /var/cache/apk/*

ADD . /opt/flexget
WORKDIR /opt/flexget

RUN pip3 install -e . && \
    pip3 install transmissionrpc && \
    pip3 install deluge-client && \
    pip3 install cloudscraper

WORKDIR /opt/flexget/flexget/ui/v2
RUN wget https://github.com/Flexget/webui/releases/latest/download/dist.zip && \
    unzip dist.zip && \
    rm dist.zip
WORKDIR /opt/flexget

RUN mkdir /root/.flexget
VOLUME /root/.flexget

ENTRYPOINT ["flexget"]
