from __future__ import unicode_literals, division, absolute_import

import logging
import re
from builtins import *  # noqa pylint: disable=unused-import, redefined-builtin

from flexget import plugin
from flexget.entry import Entry
from flexget.event import event
from flexget.manager import Session
from . import db

log = logging.getLogger('archive')


class Archive(object):
    """
    Archives all new items into database where they can be later searched and injected.
    Stores the entries in the state as they are at the exit phase, this way task cleanup for title
    etc is stored into the database. This may however make injecting them back to the original task work
    wrongly.
    """

    schema = {'oneOf': [{'type': 'boolean'}, {'type': 'array', 'items': {'type': 'string'}}]}

    def on_task_learn(self, task, config):
        """Add new entries into archive. We use learn phase in case the task corrects title or url via some plugins."""

        if isinstance(config, bool):
            tag_names = []
        else:
            tag_names = config

        tags = []
        for tag_name in set(tag_names):
            tags.append(db.get_tag(tag_name, task.session))

        count = 0
        processed = []
        for entry in task.entries + task.rejected + task.failed:
            # I think entry can be in multiple of those lists .. not sure though!
            if entry in processed:
                continue
            else:
                processed.append(entry)

            ae = (
                task.session.query(db.ArchiveEntry)
                .filter(db.ArchiveEntry.title == entry['title'])
                .filter(db.ArchiveEntry.url == entry['url'])
                .first()
            )
            if ae:
                # add (missing) sources
                source = db.get_source(task.name, task.session)
                if source not in ae.sources:
                    log.debug('Adding `%s` into `%s` sources' % (task.name, ae))
                    ae.sources.append(source)
                # add (missing) tags
                for tag_name in tag_names:
                    atag = db.get_tag(tag_name, task.session)
                    if atag not in ae.tags:
                        log.debug('Adding tag %s into %s' % (tag_name, ae))
                        ae.tags.append(atag)
            else:
                # create new archive entry
                ae = db.ArchiveEntry()
                ae.title = entry['title']
                ae.url = entry['url']
                if 'description' in entry:
                    ae.description = entry['description']
                ae.task = task.name
                ae.sources.append(db.get_source(task.name, task.session))
                if tags:
                    # note, we're extending empty list
                    ae.tags.extend(tags)
                log.debug('Adding `%s` with %i tags to archive' % (ae, len(tags)))
                task.session.add(ae)
                count += 1
        if count:
            log.verbose('Added %i new entries to archive' % count)

    def on_task_abort(self, task, config):
        """
        Archive even on task abort, except if the abort has happened before session
        was started.
        """
        if task.session is not None:
            self.on_task_learn(task, config)


class UrlrewriteArchive(object):
    """
    Provides capability to rewrite urls from archive or make searches with discover.
    """

    entry_map = {'title': 'title', 'url': 'url', 'description': 'description'}

    schema = {'oneOf': [{'type': 'boolean'}, {'type': 'array', 'items': {'type': 'string'}}]}

    def search(self, task, entry, config=None):
        """Search plugin API method"""

        session = Session()
        entries = set()
        if isinstance(config, bool):
            tag_names = None
        else:
            tag_names = config
        try:
            for query in entry.get('search_strings', [entry['title']]):
                # clean some characters out of the string for better results
                query = re.sub(r'[ \(\)]+', ' ', query).strip()
                log.debug('looking for `%s` config: %s' % (query, config))
                for archive_entry in db.search(session, query, tags=tag_names, desc=True):
                    log.debug('rewrite search result: %s' % archive_entry)
                    entry = Entry()
                    entry.update_using_map(self.entry_map, archive_entry, ignore_none=True)
                    if entry.isvalid():
                        entries.add(entry)
        finally:
            session.close()
        log.debug('found %i entries' % len(entries))
        return entries


@event('plugin.register')
def register_plugin():
    plugin.register(Archive, 'archive', api_ver=2)
    plugin.register(UrlrewriteArchive, 'flexget_archive', interfaces=['search'], api_ver=2)
