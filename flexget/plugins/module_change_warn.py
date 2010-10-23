import logging
import os
from flexget.manager import Session
from flexget.plugin import register_plugin

log = logging.getLogger('change')
found_deprecated = False


class ChangeWarn:
    """
        Gives warning if user has deprecated / changed configuration in the root level.

        Will be replaced by root level validation in the future!

        Contains ugly hacks, better to include all deprecation warnings here during 1.0 BETA phase
    """

    def old_database(self, feed, reason=''):
        log.critical('You\'re running old database! Please see \'Upgrade Actions\' at flexget.com for necessary actions! %s' % reason)
        feed.manager.disable_feeds()
        feed.abort()

    def on_process_start(self, feed):
        found_deprecated = False
        config = feed.manager.config

        if 'torrent_size' in feed.config:
            log.critical('Plugin torrent_size is deprecated, use content_size instead')
            found_deprecated = True

        if 'nzb_size' in feed.config:
            log.critical('Plugin nzb_size is deprecated, use content_size instead')
            found_deprecated = True

        # prevent useless keywords in root level
        allow = ['feeds', 'presets', 'variables']
        for key in config.iterkeys():
            if key not in allow:
                log.critical('Keyword \'%s\' is not allowed in the root level!' % key)

        # priority (dict) was renamed to plugin_priority
        if isinstance(feed.config.get('priority', None), dict):
            log.critical('Plugin \'priority\' was renamed to \'plugin_priority\'')

        session = Session()

        # database changes
        from flexget.utils.sqlalchemy_utils import table_columns, table_exists

        columns = table_columns('imdb_movies', session)
        if not 'photo' in columns:
            self.old_database(feed, '(photo missing from imdb_movies table)')

        columns = table_columns('make_rss', session)
        if not 'rsslink' in columns:
            self.old_database(feed, '(rsslink missing from make_rss table)')

        columns = table_columns('imdb_queue', session)
        if not 'title' in columns:
            self.old_database(feed, '(title missing from imdb_queue table)')

        if table_exists('episode_qualities', session):
            self.old_database(feed, '(old series format)')

        if found_deprecated:
            feed.manager.disable_feeds()
            feed.abort()

        session.close()

register_plugin(ChangeWarn, 'change_warn', builtin=True)

# check that no old plugins are in pre-compiled form (pyc)
try:
    import sys
    import os.path
    dir = os.path.normpath(sys.path[0] + '/../flexget/plugins/')
    for name in os.listdir(dir):
        require_clean = False
        if 'resolver' in name:
            require_clean = True

        if 'filter_torrent_size' in name:
            require_clean = True

        if 'filter_nzb_size' in name:
            require_clean = True

        if 'module_priority' in name:
            require_clean = True

        if 'ignore_feed' in name:
            require_clean = True

        if 'module_manual' in name:
            require_clean = True

        if require_clean:
            log.critical('-' * 79)
            log.critical('IMPORTANT: Please remove all pre-compiled .pyc and .pyo files from')
            log.critical('           path: %s' % dir)
            log.critical('           After this FlexGet should run again normally')
            log.critical('-' * 79)
            found_deprecated = True
            break
except:
    pass
