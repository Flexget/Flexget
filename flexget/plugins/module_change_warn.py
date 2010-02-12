import logging
import os
from flexget.manager import Session
from flexget.plugin import *

log = logging.getLogger('change')
found_deprecated = False


class ChangeWarn:
    """
        Gives warning if user has deprecated / changed configuration in the root level.

        Will be replaced by root level validation in the future!

        Contains ugly hacks, better to include all deprecation warnings here during 1.0 BETA phase
    """

    def old_database(self, feed, reason=''):
        log.critical('You\'re running old database! Please see bleeding edge news for necessary actions! %s' % reason)
        feed.manager.disable_feeds()
        feed.abort()

    def on_process_start(self, feed):
        config = feed.manager.config

        # prevent useless keywords in root level
        allow = ['feeds', 'presets', 'variables']
        for key in config.iterkeys():
            if key not in allow:
                log.critical('Keyword \'%s\' is not allowed in the root level!' % key)

        session = Session()

        # database changes
        from flexget.utils.sqlalchemy_utils import table_columns, table_exists

        columns = table_columns('imdb_movies', session)
        if not 'photo' in columns:
            self.old_database(feed, '(photo missing from imdb_movies table)')

        columns = table_columns('make_rss', session)
        if not 'rsslink' in columns:
            self.old_database(feed, '(rsslink missing from make_rss table)')

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
    root = sys.path[0]
    for name in os.listdir(root + '/../flexget/plugins/'):
        if 'resolver' in name:
            log.critical('-'*79)
            log.critical('IMPORTANT: Please remove all pre-compiled .pyc files from flexget/plugins/')
            log.critical('           After this FlexGet should run again normally')
            log.critical('-'*79)
            found_deprecated = True
            break
except:
    pass
