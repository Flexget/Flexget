FROM python:2.7-alpine

ADD . /opt/flexget
WORKDIR /opt/flexget
RUN pip install -e /opt/flexget

VOLUME /root/.flexget

ENTRYPOINT ["flexget"]
CMD ["--loglevel", "info", "daemon", "start", "--autoreload-config"]
