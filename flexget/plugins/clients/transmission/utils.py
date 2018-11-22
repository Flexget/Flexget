import os
from datetime import datetime
from datetime import timedelta
from future.utils import text_to_native_str

from flexget.utils.pathscrub import pathscrub
from flexget.utils.template import RenderError

from .transmission import log


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


OVERRIDABLE_KEYS = ('path', 'addpaused', 'honourlimits', 'bandwidthpriority', 'maxconnections', 'maxupspeed',
                    'maxdownspeed', 'ratio', 'main_file_only', 'main_file_ratio', 'magnetization_timeout',
                    'include_subs', 'content_filename', 'include_files', 'skip_files', 'rename_like_files',
                    'queue_position')


def create_torrent_options(config, entry):
    opt_dic = {}

    for opt_key in OVERRIDABLE_KEYS:
        # Values do not merge config with task
        # Task takes priority then config is used
        if opt_key in entry:
            opt_dic[opt_key] = entry[opt_key]
        elif opt_key in config:
            opt_dic[opt_key] = config[opt_key]

    torrent_options = {'add': {}, 'change': {}, 'post': {}}

    add = torrent_options['add']
    if opt_dic.get('path'):
        try:
            path = os.path.expanduser(entry.render(opt_dic['path']))
            add['download_dir'] = text_to_native_str(pathscrub(path), 'utf-8')
        except RenderError as e:
            log.error('Error setting path for %s: %s' % (entry['title'], e))
    if 'bandwidthpriority' in opt_dic:
        add['bandwidthPriority'] = opt_dic['bandwidthpriority']
    if 'maxconnections' in opt_dic:
        add['peer_limit'] = opt_dic['maxconnections']
    # make sure we add it paused, will modify status after adding
    add['paused'] = True

    change = torrent_options['change']
    if 'honourlimits' in opt_dic and not opt_dic['honourlimits']:
        change['honorsSessionLimits'] = False
    if 'maxupspeed' in opt_dic:
        change['uploadLimit'] = opt_dic['maxupspeed']
        change['uploadLimited'] = True
    if 'maxdownspeed' in opt_dic:
        change['downloadLimit'] = opt_dic['maxdownspeed']
        change['downloadLimited'] = True

    if 'ratio' in opt_dic:
        change['seedRatioLimit'] = opt_dic['ratio']
        if opt_dic['ratio'] == -1:
            # seedRatioMode:
            # 0 follow the global settings
            # 1 override the global settings, seeding until a certain ratio
            # 2 override the global settings, seeding regardless of ratio
            change['seedRatioMode'] = 2
        else:
            change['seedRatioMode'] = 1

    if 'queue_position' in opt_dic:
        change['queuePosition'] = opt_dic['queue_position']

    post = torrent_options['post']
    # set to modify paused status after
    if 'addpaused' in opt_dic:
        post['paused'] = opt_dic['addpaused']
    if 'main_file_only' in opt_dic:
        post['main_file_only'] = opt_dic['main_file_only']
    if 'main_file_ratio' in opt_dic:
        post['main_file_ratio'] = opt_dic['main_file_ratio']
    if 'magnetization_timeout' in opt_dic:
        post['magnetization_timeout'] = opt_dic['magnetization_timeout']
    if 'include_subs' in opt_dic:
        post['include_subs'] = opt_dic['include_subs']
    if 'content_filename' in opt_dic:
        try:
            post['content_filename'] = entry.render(opt_dic['content_filename'])
        except RenderError as e:
            log.error('Unable to render content_filename %s: %s' % (entry['title'], e))
    if 'skip_files' in opt_dic:
        post['skip_files'] = opt_dic['skip_files']
    if 'include_files' in opt_dic:
        post['include_files'] = opt_dic['include_files']
    if 'rename_like_files' in opt_dic:
        post['rename_like_files'] = opt_dic['rename_like_files']
    return torrent_options
