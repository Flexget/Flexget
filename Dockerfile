FROM alpine
MAINTAINER Rémi Alvergnat <toilal.dev@gmail.com>

RUN apk add --update python py-pip ca-certificates && rm -rf /var/cache/apk/*

ADD . /opt/flexget
WORKDIR /opt/flexget

RUN pip install paver
RUN pip install -e .

RUN mkdir /root/.flexget
VOLUME /root/.flexget

ENTRYPOINT ["flexget"]
