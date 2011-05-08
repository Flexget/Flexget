import os
from flexget.feed import Entry
from flexget.plugin import register_plugin, register_parser_option, get_plugin_by_name, DependencyError, PluginError
from flexget.utils.cached_input import cached
import re
import logging
import sys

log = logging.getLogger('tail')


class ResetTail(object):
    """Adds --tail-reset"""

    def on_process_start(self, feed):
        if not feed.manager.options.tail_reset:
            return

        feed.manager.disable_feeds()

        from flexget.utils.simple_persistence import SimpleKeyValue
        from flexget.manager import Session

        session = Session()
        try:
            poses = session.query(SimpleKeyValue).filter(SimpleKeyValue.key == feed.manager.options.tail_reset).all()
            if not poses:
                print 'No position stored for file %s' % feed.manager.options.tail_reset
                print 'Note that file must give in same format as in config, ie. ~/logs/log can not be given as /home/user/logs/log'
            for pos in poses:
                if pos.value == 0:
                    print 'Feed %s tail position is already zero' % pos.feed
                else:
                    print 'Feed %s tail position (%s) reseted to zero' % (pos.feed, pos.value)
                    pos.value = 0
            session.commit()
        finally:
            session.close()


class InputTail(object):

    """
    Parse any text for entries using regular expression.

    file: <file>
    entry:
      <field>: <regexp to match value>
    format:
      <field>: <python string formatting>

    Note: each entry must have atleast two fields, title and url

    You may wish to specify encoding used by file so file can be properly
    decoded. List of encodings
    at http://docs.python.org/library/codecs.html#standard-encodings.

    Example:

    tail:
      file: ~/irclogs/some/log
      entry:
        title: 'TITLE: (.*) URL:'
        url: 'URL: (.*)'
      encoding: utf8
    """

    def validator(self):
        from flexget import validator
        root = validator.factory('dict')
        root.accept('file', key='file', required=True)
        root.accept('text', key='encoding')
        entry = root.accept('dict', key='entry', required=True)
        entry.accept('regexp', key='url', required=True)
        entry.accept('regexp', key='title', required=True)
        entry.accept_any_key('regexp')
        format = root.accept('dict', key='format')
        format.accept_any_key('text')
        return root

    def format_entry(self, entry, d):
        for k, v in d.iteritems():
            entry[k] = v % entry

    @cached('tail', 'file')
    def on_feed_input(self, feed):

        try:
            # details plugin will complain if no entries are created, with this we disable that
            details = get_plugin_by_name('details').instance
            if feed.name not in details.no_entries_ok:
                log.debug('appending %s to details plugin no_entries_ok' % feed.name)
                details.no_entries_ok.append(feed.name)
        except DependencyError:
            log.debug('unable to get details plugin')

        filename = os.path.expanduser(feed.config['tail']['file'])
        encoding = feed.config['tail'].get('encoding', None)
        file = open(filename, 'r')

        last_pos = feed.simple_persistence.setdefault(filename, 0)
        if os.path.getsize(filename) < last_pos:
            log.info('File size is smaller than in previous execution, reseting to beginning of the file')
            last_pos = 0

        file.seek(last_pos)

        log.debug('continuing from last position %s' % last_pos)

        entry_config = feed.config['tail'].get('entry')
        format_config = feed.config['tail'].get('format', {})

        # keep track what fields have been found
        used = {}
        entry = Entry()

        # now parse text

        while True:
            line = file.readline()
            if encoding:
                try:
                    line = line.decode(encoding)
                except UnicodeError:
                    raise PluginError('Failed to decode file using %s. Check encoding.' % encoding)

            if not line:
                feed.simple_persistence[filename] = file.tell()
                break

            for field, regexp in entry_config.iteritems():
                #log.debug('search field: %s regexp: %s' % (field, regexp))
                match = re.search(regexp, line)
                if match:
                    # check if used field detected, in such case start with new entry
                    if used.has_key(field):
                        if entry.isvalid():
                            log.info('Found field %s again before entry was completed. \
                                      Adding current incomplete, but valid entry and moving to next.' % field)
                            self.format_entry(entry, format_config)
                            feed.entries.append(entry)
                        else:
                            log.info('Invalid data, entry field %s is already found once. Ignoring entry.' % field)
                        # start new entry
                        entry = Entry()
                        used = {}

                    # add field to entry
                    entry[field] = match.group(1)
                    used[field] = True
                    log.debug('found field: %s value: %s' % (field, entry[field]))

                # if all fields have been found
                if len(used) == len(entry_config):
                    # check that entry has at least title and url
                    if not entry.isvalid():
                        log.info('Invalid data, constructed entry is missing mandatory fields (title or url)')
                    else:
                        self.format_entry(entry, format_config)
                        feed.entries.append(entry)
                        log.debug('Added entry %s' % entry)
                        # start new entry
                        entry = Entry()
                        used = {}

register_plugin(InputTail, 'tail')
register_plugin(ResetTail, '--tail-reset', builtin=True)
register_parser_option('--tail-reset', action='store', dest='tail_reset', default=False, metavar='FILE',
    help='Reset tail position for a file.')
