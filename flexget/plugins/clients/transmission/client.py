from flexget import plugin

import os
from datetime import datetime
from datetime import timedelta

try:
    import transmissionrpc
    from transmissionrpc import TransmissionError
    from transmissionrpc import HTTPHandlerError
except ImportError:
    # If transmissionrpc is not found, errors will be shown later
    pass


def create_rpc_client(config):
    user, password = config.get('username'), config.get('password')

    try:
        return transmissionrpc.Client(config['host'], config['port'], user, password)
    except TransmissionError as e:
        if isinstance(e.original, HTTPHandlerError):
            if e.original.code == 111:
                raise plugin.PluginError("Cannot connect to transmission. Is it running?")
            elif e.original.code == 401:
                raise plugin.PluginError("Username/password for transmission is incorrect. Cannot connect.")
            elif e.original.code == 110:
                raise plugin.PluginError("Cannot connect to transmission: Connection timed out.")
            else:
                raise plugin.PluginError("Error connecting to transmission: %s" % e.original.message)
        else:
            raise plugin.PluginError("Error connecting to transmission: %s" % e.message)


def torrent_info(torrent, config):
    done = torrent.totalSize > 0
    vloc = None
    best = None
    for t in torrent.files().items():
        tf = t[1]
        if tf['selected']:
            if tf['size'] <= 0 or tf['completed'] < tf['size']:
                done = False
                break
            if not best or tf['size'] > best[1]:
                best = (tf['name'], tf['size'])
    if done and best and (100 * float(best[1]) / float(torrent.totalSize)) >= (config['main_file_ratio'] * 100):
        vloc = ('%s/%s' % (torrent.downloadDir, best[0])).replace('/', os.sep)
    return done, vloc


def check_seed_limits(torrent, session):
    seed_limit_ok = None  # will remain if no seed ratio defined
    idle_limit_ok = None  # will remain if no idle limit defined

    if torrent.seedRatioMode == 1:  # use torrent's own seed ratio limit
        seed_limit_ok = torrent.uploadRatio >= torrent.seedRatioLimit
    elif torrent.seedRatioMode == 0:  # use global rules
        if session.seedRatioLimited:
            seed_limit_ok = torrent.uploadRatio >= session.seedRatioLimit

    if torrent.seedIdleMode == 1:  # use torrent's own idle limit
        idle_limit_ok = torrent.date_active + timedelta(minutes=torrent.seedIdleLimit) < datetime.now()
    elif torrent.seedIdleMode == 0:  # use global rules
        if session.idle_seeding_limit_enabled:
            idle_limit_ok = torrent.date_active + timedelta(minutes=session.idle_seeding_limit) < datetime.now()

    return seed_limit_ok, idle_limit_ok
