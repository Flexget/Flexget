from __future__ import unicode_literals, division, absolute_import

import logging
import re
from builtins import *  # noqa pylint: disable=unused-import, redefined-builtin
from collections import MutableSet

from flexget import plugin
from flexget.db_schema import with_session
from flexget.event import event
from flexget.manager import Session
from . import db

log = logging.getLogger('regexp_list')


class RegexpList(MutableSet):
    schema = {'type': 'string'}

    def _db_list(self, session):
        return (
            session.query(db.RegexpListList).filter(db.RegexpListList.name == self.config).first()
        )

    def _from_iterable(self, it):
        # TODO: is this the right answer? the returned object won't have our custom __contains__ logic
        return set(it)

    @with_session
    def __init__(self, config, session=None):
        self.config = config
        db_list = self._db_list(session)
        if not db_list:
            session.add(db.RegexpListList(name=self.config))

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
            db_regexp = db.RegexListRegexp()
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
            res = (
                self._db_list(session)
                .regexps.filter(db.RegexListRegexp.regexp == entry.get('regexp', entry['title']))
                .first()
            )
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


@event('plugin.register')
def register_plugin():
    plugin.register(PluginRegexpList, 'regexp_list', api_ver=2, interfaces=['task', 'list'])
