from __future__ import unicode_literals, division, absolute_import
from builtins import *  # noqa pylint: disable=unused-import, redefined-builtin

import logging
import re
from collections import MutableSet
from datetime import datetime

from sqlalchemy import Column, Unicode, Integer, ForeignKey, DateTime, func, and_
from sqlalchemy.orm import relationship

from flexget import plugin
from flexget.manager import Session
from flexget.db_schema import versioned_base, with_session
from flexget.entry import Entry
from flexget.event import event

log = logging.getLogger('regexp_list')
Base = versioned_base('regexp_list', 1)


class RegexpListList(Base):
    __tablename__ = 'regexp_list_lists'
    id = Column(Integer, primary_key=True)
    name = Column(Unicode, unique=True)
    added = Column(DateTime, default=datetime.now)
    regexps = relationship('RegexListRegexp', backref='list', cascade='all, delete, delete-orphan', lazy='dynamic')

    def __repr__(self):
        return '<RegexpListList name=%s,id=%d>' % (self.name, self.id)

    def to_dict(self):
        return {
            'id': self.id,
            'name': self.name,
            'added_on': self.added
        }


class RegexListRegexp(Base):
    __tablename__ = 'regexp_list_regexps'
    id = Column(Integer, primary_key=True)
    added = Column(DateTime, default=datetime.now)
    regexp = Column(Unicode)
    list_id = Column(Integer, ForeignKey(RegexpListList.id), nullable=False)

    def __repr__(self):
        return '<RegexListRegexp regexp=%s,list_name=%s>' % (self.regexp, self.list.name)

    def to_entry(self):
        entry = Entry()
        entry['title'] = entry['regexp'] = self.regexp
        entry['url'] = 'mock://localhost/regexp_list/%d' % self.id
        return entry

    def to_dict(self):
        return {
            'id': self.id,
            'added_on': self.added,
            'regexp': self.regexp
        }


class RegexpList(MutableSet):
    schema = {'type': 'string'}

    def _db_list(self, session):
        return session.query(RegexpListList).filter(RegexpListList.name == self.config).first()

    def _from_iterable(self, it):
        # TODO: is this the right answer? the returned object won't have our custom __contains__ logic
        return set(it)

    @with_session
    def __init__(self, config, session=None):
        self.config = config
        db_list = self._db_list(session)
        if not db_list:
            session.add(RegexpListList(name=self.config))

    def __iter__(self):
        with Session() as session:
            return iter([regexp.to_entry() for regexp in self._db_list(session).regexps])

    def __len__(self):
        with Session() as session:
            return self._db_list(session).regexps.count()

    def add(self, entry):
        with Session() as session:
            # Check if this is already in the list, refresh info if so
            db_list = self._db_list(session=session)
            db_regexp = self._find_entry(entry, session=session)
            # Just delete and re-create to refresh
            if db_regexp:
                session.delete(db_regexp)
            db_regexp = RegexListRegexp()
            db_regexp.regexp = entry.get('regexp', entry['title'])
            db_list.regexps.append(db_regexp)
            session.commit()
            return db_regexp.to_entry()

    def discard(self, entry):
        with Session() as session:
            for match_regexp in [False, True]:
                db_regexp = self._find_entry(entry, match_regexp=match_regexp, session=session)
                if db_regexp:
                    log.debug('deleting file %s', db_regexp)
                    session.delete(db_regexp)

    def __contains__(self, entry):
        return self._find_entry(entry, match_regexp=True) is not None

    @with_session
    def _find_entry(self, entry, match_regexp=False, session=None):
        """Finds `SubtitleListFile` corresponding to this entry, if it exists."""
        res = None
        if match_regexp:
            for regexp in self._db_list(session).regexps:
                if re.search(regexp.regexp, entry['title'], re.IGNORECASE):
                    res = regexp
        else:
            res = self._db_list(session).regexps.filter(RegexListRegexp.regexp ==
                                                        entry.get('regexp', entry['title'])).first()
        return res

    @property
    def immutable(self):
        return False

    @property
    def online(self):
        """ Set the online status of the plugin, online plugin should be treated differently in certain situations,
        like test mode"""
        return False

    @with_session
    def get(self, entry, session):
        match = self._find_entry(entry=entry, match_regexp=True, session=session)
        return match.to_entry() if match else None


class PluginRegexpList(object):
    """Subtitle list"""
    schema = RegexpList.schema

    @staticmethod
    def get_list(config):
        return RegexpList(config)

    def on_task_input(self, task, config):
        regexp_list = RegexpList(config)

        return list(regexp_list)


# The following are some nice-to-have API methods

@with_session
def get_regexp_lists(name=None, session=None):
    log.debug('retrieving regexp lists')
    query = session.query(RegexpListList)
    if name:
        log.debug('filtering by name %s', name)
        query = query.filter(RegexpListList.name.contains(name))
    return query.all()


@with_session
def get_list_by_exact_name(name, session=None):
    log.debug('returning list with name %s', name)
    return session.query(RegexpListList).filter(func.lower(RegexpListList.name) == name.lower()).one_or_none()


@with_session
def get_regexps_by_list_id(list_id, count=False, start=None, stop=None, order_by='added', descending=False,
                          session=None):
    query = session.query(RegexListRegexp).filter(RegexListRegexp.list_id == list_id)
    if count:
        return query.count()
    query = query.slice(start, stop).from_self()
    if descending:
        query = query.order_by(getattr(RegexListRegexp, order_by).desc())
    else:
        query = query.order_by(getattr(RegexListRegexp, order_by))
    return query.all()


@with_session
def get_list_by_id(list_id, session=None):
    log.debug('fetching list with id %d', list_id)
    return session.query(RegexpListList).filter(RegexpListList.id == list_id).one_or_none()


@with_session
def get_regexp(list_id, regexp, session=None):
    regexp_list = get_list_by_id(list_id=list_id, session=session)
    if regexp_list:
        log.debug('searching for regexp %s in list %d', regexp, list_id)
        return session.query(RegexListRegexp).filter(
            and_(
                func.lower(RegexListRegexp.regexp) == regexp.lower(),
                RegexListRegexp.list_id == list_id)
        ).first()


@with_session
def create_list(list_name, session=None):
    """
    Only creates the list if it doesn't exist.

    :param str list_name: Name of the list
    :param Session session:
    :return: regex list with name list_name
    """
    regexp_list = get_list_by_exact_name(list_name, session=session)
    if not regexp_list:
        regexp_list = RegexpListList(name=list_name)
        session.merge(regexp_list)
        session.commit()
    return regexp_list


@with_session
def add_to_list_by_name(list_name, regexp, session=None):
    regexp_list = create_list(list_name, session=session)
    existing_regexp = get_regexp(regexp_list.id, regexp, session=session)
    if not existing_regexp:
        new_regexp = RegexListRegexp(regexp=regexp, list_id=regexp_list.id)
        session.merge(new_regexp)
        session.commit()


@event('plugin.register')
def register_plugin():
    plugin.register(PluginRegexpList, 'regexp_list', api_ver=2, interfaces=['task', 'list'])
