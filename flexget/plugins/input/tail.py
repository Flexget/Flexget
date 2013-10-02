from __future__ import unicode_literals, division, absolute_import
import os
import re
import logging

from flexget import options, plugin
from flexget.entry import Entry
from flexget.event import event
from flexget.utils.cached_input import cached

log = logging.getLogger('tail')


class InputTail(object):

    """
    Parse any text for entries using regular expression.

    ::

      file: <file>
      entry:
        <field>: <regexp to match value>
      format:
        <field>: <python string formatting>

    Note: each entry must have atleast two fields, title and url

    You may wish to specify encoding used by file so file can be properly
    decoded. List of encodings
    at http://docs.python.org/library/codecs.html#standard-encodings.

    Example::

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

    @cached('tail')
    def on_task_input(self, task, config):

        # Let details plugin know that it is ok if this task doesn't produce any entries
        task.no_entries_ok = True

        filename = os.path.expanduser(config['file'])
        encoding = config.get('encoding', None)
        with open(filename, 'r') as file:
            last_pos = task.simple_persistence.setdefault(filename, 0)
            if task.options.tail_reset == filename or task.options.tail_reset == task.name:
                if last_pos == 0:
                    log.info('Task %s tail position is already zero' % task.name)
                else:
                    log.info('Task %s tail position (%s) reset to zero' % (task.name, last_pos))
                    last_pos = 0

            if os.path.getsize(filename) < last_pos:
                log.info('File size is smaller than in previous execution, reseting to beginning of the file')
                last_pos = 0

            file.seek(last_pos)

            log.debug('continuing from last position %s' % last_pos)

            entry_config = config.get('entry')
            format_config = config.get('format', {})

            # keep track what fields have been found
            used = {}
            entries = []
            entry = Entry()

            # now parse text

            while True:
                line = file.readline()
                if encoding:
                    try:
                        line = line.decode(encoding)
                    except UnicodeError:
                        raise plugin.PluginError('Failed to decode file using %s. Check encoding.' % encoding)

                if not line:
                    task.simple_persistence[filename] = file.tell()
                    break

                for field, regexp in entry_config.iteritems():
                    #log.debug('search field: %s regexp: %s' % (field, regexp))
                    match = re.search(regexp, line)
                    if match:
                        # check if used field detected, in such case start with new entry
                        if field in used:
                            if entry.isvalid():
                                log.info('Found field %s again before entry was completed. \
                                          Adding current incomplete, but valid entry and moving to next.' % field)
                                self.format_entry(entry, format_config)
                                entries.append(entry)
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
                            entries.append(entry)
                            log.debug('Added entry %s' % entry)
                            # start new entry
                            entry = Entry()
                            used = {}
        return entries


@event('plugin.register')
def register_plugin():
    plugin.register(InputTail, 'tail', api_ver=2)


@event('options.register')
def register_parser_arguments():
    options.get_parser('execute').add_argument('--tail-reset', action='store', dest='tail_reset', default=False,
                                               metavar='FILE|TASK', help='reset tail position for a file')
