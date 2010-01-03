import logging
from flexget.manager import Session
from flexget.plugin import *

log = logging.getLogger('change')


class ChangeWarn:
    """
        Gives warning if user has deprecated / changed configuration in the root level.

        Will be replaced by root level validation in the future!
    """

    def old_database(self, feed, reason=''):
        log.critical('Running old database! Please see bleeding edge news! %s' % reason)
        feed.manager.disable_feeds()
        feed.abort()

    def on_process_start(self, feed):
        config = feed.manager.config

        # prevent useless keywords in root level
        allow = ['feeds', 'preset']
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

        session.close()

register_plugin(ChangeWarn, 'change_warn', builtin=True)
