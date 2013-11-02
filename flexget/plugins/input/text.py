"""Plugin for text file or URL feeds via regex."""
from __future__ import unicode_literals, division, absolute_import
import re
import logging

from flexget import plugin
from flexget.entry import Entry
from flexget.event import event
from flexget.utils.cached_input import cached

log = logging.getLogger('text')


class Text(object):

    """
    Parse any text for entries using regular expression.

    Example::

      url: <url>
      entry:
        <field>: <regexp to match value>
      format:
        <field>: <python string formatting>

    Note: each entry must have atleast two fields, title and url

    Example::

      text:
        url: http://www.nbc.com/Heroes/js/novels.js
        entry:
          title: novelTitle = "(.*)"
          url: novelPrint = "(.*)"
        format:
          url: http://www.nbc.com%(url)s
    """

    def validator(self):
        from flexget import validator
        root = validator.factory('dict')
        root.accept('url', key='url')
        root.accept('file', key='url')
        root.require_key('url')
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

    @cached('text')
    @plugin.internet(log)
    def on_task_input(self, task, config):
        url = config['url']
        if '://' in url:
            lines = task.requests.get(url).iter_lines()
        else:
            lines = open(url, 'rb').readlines()

        entry_config = config.get('entry')
        format_config = config.get('format', {})

        entries = []
        # keep track what fields have been found
        used = {}
        entry = Entry()

        # now parse text
        for line in lines:
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
                    try:
                        entry[field] = match.group(1)
                    except IndexError:
                        log.error('regex for field `%s` must contain a capture group' % field)
                        raise plugin.PluginError('Your text plugin config contains errors, please correct them.')
                    used[field] = True
                    log.debug('found field: %s value: %s' % (field, entry[field]))

                # if all fields have been found
                if len(used) == len(entry_config):
                    # check that entry has atleast title and url
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
    plugin.register(Text, 'text', api_ver=2)
