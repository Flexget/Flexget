from __future__ import unicode_literals, division, absolute_import
from builtins import *  # pylint: disable=unused-import, redefined-builtin

import logging
from datetime import datetime

from sqlalchemy import Column, Integer, String, Unicode, DateTime
from sqlalchemy.schema import Index
from sqlalchemy.sql.expression import desc

from flexget import plugin
from flexget.event import fire_event, event
from flexget.manager import Base
from flexget.utils.log import log_once
from flexget.plugin import get_plugin_by_name
from flexget.utils.tools import parse_timedelta

log = logging.getLogger('proper_movies')


class ProperMovie(Base):

    __tablename__ = 'proper_movies'

    id = Column(Integer, primary_key=True)
    title = Column(Unicode)
    task = Column('feed', Unicode)
    imdb_id = Column(String, index=True)
    quality = Column(String)
    proper_count = Column(Integer)
    added = Column(DateTime)

    def __init__(self):
        self.added = datetime.now()

    def __repr__(self):
        return '<ProperMovie(title=%s,task=%s,imdb_id=%s,quality=%s,proper_count=%s,added=%s)>' % \
            (self.title, self.task, self.imdb_id, self.quality, self.proper_count, self.added)


# create index
columns = Base.metadata.tables['proper_movies'].c
Index('proper_movies_imdb_id_quality_proper', columns.imdb_id, columns.quality, columns.proper_count)


class FilterProperMovies(object):
    """
        Automatically download proper movies.

        Configuration:

            proper_movies: n <minutes|hours|days|weeks>

        or permanently:

            proper_movies: yes

        Value no will disable plugin.
    """

    schema = {
        'oneOf': [
            {'type': 'boolean'},
            {'type': 'string', 'format': 'interval'}
        ]
    }

    def on_task_filter(self, task, config):
        log.debug('check for enforcing')

        # parse config
        if isinstance(config, bool):
            # configured a boolean false, disable plugin
            if not config:
                return
            # configured a boolean true, disable timeframe
            timeframe = None
        else:
            # parse time window
            log.debug('interval: %s' % config)
            try:
                timeframe = parse_timedelta(config)
            except ValueError:
                raise plugin.PluginError('Invalid time format', log)

        # throws DependencyError if not present aborting task
        imdb_lookup = plugin.get_plugin_by_name('imdb_lookup').instance

        for entry in task.entries:
            parser = get_plugin_by_name('parsing').instance.parse_movie(entry['title'])

            # if we have imdb_id already evaluated
            if entry.get('imdb_id', None, eval_lazy=False) is None:
                try:
                    # TODO: fix imdb_id_lookup, cumbersome that it returns None and or throws exception
                    # Also it's crappy name!
                    imdb_id = imdb_lookup.imdb_id_lookup(movie_title=parser.name, raw_title=entry['title'])
                    if imdb_id is None:
                        continue
                    entry['imdb_id'] = imdb_id
                except plugin.PluginError as pe:
                    log_once(pe.value)
                    continue

            quality = parser.quality.name

            log.debug('quality: %s' % quality)
            log.debug('imdb_id: %s' % entry['imdb_id'])
            log.debug('current proper count: %s' % parser.proper_count)

            proper_movie = task.session.query(ProperMovie).\
                filter(ProperMovie.imdb_id == entry['imdb_id']).\
                filter(ProperMovie.quality == quality).\
                order_by(desc(ProperMovie.proper_count)).first()

            if not proper_movie:
                log.debug('no previous download recorded for %s' % entry['imdb_id'])
                continue

            highest_proper_count = proper_movie.proper_count
            log.debug('highest_proper_count: %i' % highest_proper_count)

            accept_proper = False
            if parser.proper_count > highest_proper_count:
                log.debug('proper detected: %s ' % proper_movie)

                if timeframe is None:
                    accept_proper = True
                else:
                    expires = proper_movie.added + timeframe
                    log.debug('propers timeframe: %s' % timeframe)
                    log.debug('added: %s' % proper_movie.added)
                    log.debug('propers ignore after: %s' % str(expires))
                    if datetime.now() < expires:
                        accept_proper = True
                    else:
                        log.verbose('Proper `%s` has past it\'s expiration time' % entry['title'])

            if accept_proper:
                log.info('Accepting proper version previously downloaded movie `%s`' % entry['title'])
                # TODO: does this need to be called?
                # fire_event('forget', entry['imdb_url'])
                fire_event('forget', entry['imdb_id'])
                entry.accept('proper version of previously downloaded movie')

    def on_task_learn(self, task, config):
        """Add downloaded movies to the database"""
        log.debug('check for learning')
        for entry in task.accepted:
            if 'imdb_id' not in entry:
                log.debug('`%s` does not have imdb_id' % entry['title'])
                continue

            parser = get_plugin_by_name('parsing').instance.parse_movie(entry['title'])

            quality = parser.quality.name

            log.debug('quality: %s' % quality)
            log.debug('imdb_id: %s' % entry['imdb_id'])
            log.debug('proper count: %s' % parser.proper_count)

            proper_movie = task.session.query(ProperMovie).\
                filter(ProperMovie.imdb_id == entry['imdb_id']).\
                filter(ProperMovie.quality == quality).\
                filter(ProperMovie.proper_count == parser.proper_count).first()

            if not proper_movie:
                pm = ProperMovie()
                pm.title = entry['title']
                pm.task = task.name
                pm.imdb_id = entry['imdb_id']
                pm.quality = quality
                pm.proper_count = parser.proper_count
                task.session.add(pm)
                log.debug('added %s' % pm)
            else:
                log.debug('%s already exists' % proper_movie)


@event('plugin.register')
def register_plugin():
    plugin.register(FilterProperMovies, 'proper_movies', api_ver=2)
