FROM python:alpine

VOLUME [ "/config" ]

RUN apk add --no-cache --virtual .build-deps \
        gcc \
        make \
        libressl-dev \
        libffi-dev \
        musl-dev &&\
    apk add --no-cache \
        boost-python3 \ 
        libstdc++ \
        unrar \
        su-exec &&\
    pip install --no-cache-dir \
        pysftp==0.2.8 \
        deluge-client \
        cloudscraper \
        transmissionrpc \
        python-telegram-bot \
        irc_bot \
        PySocks \
        rarfile &&\
    pip install --no-cache-dir flexget &&\
    apk del --purge --no-cache .build-deps 

COPY config.yml /usr/tmp/config.yml
COPY start.sh /usr/tmp/start.sh

RUN chmod +x /usr/tmp/start.sh

CMD [ "/usr/tmp/start.sh" ]
