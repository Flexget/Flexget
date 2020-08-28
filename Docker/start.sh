#!/bin/sh

if [ ! -d "/config" ]; then
    mkdir "/config"
fi

if [ ! -f "/config/config.yml" ]; then
    cp "/usr/tmp/config.yml" "/config/config.yml"
fi

if [ ! -f "/config/flexget" ]; then
    ln -s "/usr/local/bin/flexget" "/config/flexget"
fi

if [ -f "/config/.config-lock" ]; then
    rm -f /config/.config-lock
fi

if [ ! -z $PIP_PGKS ]; then
    pip install --no-cache-dir $PIP_PGKS
fi

if [ ! -z $APK_PKGS ]; then
    apk install --no-cache $APK_PKGS
fi

chown -R ${PUID:-1000}:${PGID:-1000} "/config"

if [ ! -z $WEBUI_PASSWD ]; then
    su-exec $PUID:$PGID /config/flexget -c "config/config.yml" web passwd $WEBUI_PASSWD
fi

echo "${TZ:-UTC}" > /etc/timezone
LOGFILE="--logfile ${LOG_FILE:-/config/flexget.log}"
LOGLEVEL="--loglevel ${LOG_LEVEL:-info}"

su-exec ${PUID:-1000}:${PGID:-1000} /config/flexget -c "config/config.yml" $LOGFILE $LOGLEVEL daemon start --autoreload-config