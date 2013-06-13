from __future__ import unicode_literals, division, absolute_import
import logging

from sqlalchemy import Column, Boolean, String, ForeignKey, Integer, and_
from sqlalchemy.orm.exc import NoResultFound

from flexget import db_schema
from flexget.manager import Session
from flexget.utils import qualities
from flexget.utils.imdb import extract_id
from flexget.utils.database import quality_requirement_property, with_session
from flexget.utils.sqlalchemy_utils import table_exists, table_schema
from flexget.plugin import DependencyError, get_plugin_by_name, register_plugin
from flexget.event import event

try:
    from flexget.plugins.filter import queue_base
    from flexget.plugins.filter.queue_base import QueueError
except ImportError:
    raise DependencyError(issued_by='regexp_queue', missing='queue_base',
                          message='movie_queue requires the queue_base plugin')


log = logging.getLogger('regexp_queue')
Base = db_schema.versioned_base('regexp_queue', 0)


class QueuedRegexp(queue_base.QueuedItem, Base):
    __tablename__ = 'regexp_queue'
    __mapper_args__ = {'polymorphic_identity': 'regexp'}
    id = Column(Integer, ForeignKey('queue.id'), primary_key=True)
    regexp = Column(String)
    ignorecase = Column(Boolean)
    quality = Column('quality', String)
    quality_req = quality_requirement_property('quality')


class FilterRegexpQueue(queue_base.FilterQueueBase):
    def matches(self, task, config, entry):
        title = entry['title']

        # get all regexp that haven't been loaded yet
        expressions = task.session.query(QueuedRegexp).filter(QueuedRegexp.downloaded == None)

        # filter unwanted qualities
        quality = entry.get('quality', qualities.Quality())
        expressions = filter(lambda exp: exp.quality_req.allows(quality), expressions)

        # compile all the expressions and check if they match
        compile = lambda exp: re.compile(exp.regexp, re.IGNORECASE | rc.UNICODE)
        expressions = filter(lambda exp: compile(exp).matches(title), expressions)

        # all left over expressions fit the quality and match
        if len(expressions) > 0:
            return expressions[0]


@with_session
def queue_add(regexp=None, quality=None, session=None):
    """
    Add an item to the queue

    :param regexp: Regexp that should match to accept an entry
    :param quality: A QualityRequirements object defining acceptable qualities.
    :param session: Optional session to use for database updates
    """

    # check if that regexp is already known
    item = session.query(QueuedRegexp).filter(QueuedRegexp.regexp == regexp).first()

    quality = quality or qualities.Requirements('any')

    if not item:
        item = QueuedRegexp(regexp=regexp, quality=quality.text)
        session.add(item)
        log.info('Adding %s to regexp queue with quality=%s.' % (regexp, quality))
        return item # {'regexp': regexp, 'quality': quality}
    else:
        if item.downloaded:
            raise QueueError('ERROR: %s has already been queued and downloaded' % regexp)
        else:
            raise QueueError('ERROR: %s is already in the queue' % regexp)


@with_session
def queue_del(regexp=None, session=None):
    """
    Delete the given item from the queue.
    :param regexp: Regexp that should match to accept an entry
    :param session: Optional session to use for database updates
    """
    log.debug('queue_del - regexp=%s' % regexp)
    query = session.query(QueuedRegexp).filter(QueuedRegexp.regexp == regexp)
    try:
        item = query.one()
        regexp = item.regexp
        session.delete(item)
        return regexp
    except NoResultFound as e:
        raise QueueError('regexp=%s' % (regexp))


@with_session
def queue_edit(regexp, quality, session=None):
    """
    :param regexp: Regexp to edit
    :param quality: New Quality
    :param session: Optional session to use, new session used otherwise
    """
    try:
        item = session.query(QueuedRegexp).filter(QueuedRegexp.regexp == regexp).one()
        item.quality = quality

        return item.regexp
    except NoResultFound as e:
        raise QueueError('regexp=%s not found from queue' % (regexp))


@with_session
def queue_get(session, downloaded=False):
    """
    Get the current regexp queue

    :param session: New session is used if not given
    :param downloaded: Wheter or not to return only downloaded
    :return: List of QueuedRegexp (deatched from session)
    """
    if not downloaded:
        return session.query(QueuedRegexp).filter(QueueRegexp.downloaded == None).all()
    else:
        return session.query(QueuedRegexp).filter(QueueRegexp.downloaded != None).all()


register_plugin(FilterRegexpQueue, 'regexp_queue', api_ver=2)
