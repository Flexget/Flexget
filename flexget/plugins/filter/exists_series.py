from __future__ import unicode_literals, division, absolute_import
from builtins import *  # noqa pylint: disable=unused-import, redefined-builtin
from past.builtins import basestring

import logging

from path import Path

from flexget import plugin
from flexget.event import event
from flexget.config_schema import one_or_more
from flexget.utils.log import log_once
from flexget.utils.template import RenderError
from flexget.plugins.parsers import ParseWarning
from flexget.plugin import get_plugin_by_name

log = logging.getLogger('exists_series')


class FilterExistsSeries(object):
    """
    Intelligent series aware exists rejecting.

    Example::

      exists_series: /storage/series/
    """

    schema = {
        'anyOf': [
            one_or_more({'type': 'string', 'format': 'path'}),
            {
                'type': 'object',
                'properties': {
                    'path': one_or_more({'type': 'string', 'format': 'path'}),
                    'allow_different_qualities': {'enum': ['better', True, False], 'default': False}
                },
                'required': ['path'],
                'additionalProperties': False
            }
        ]
    }

    def prepare_config(self, config):
        # if config is not a dict, assign value to 'path' key
        if not isinstance(config, dict):
            config = {'path': config}
        # if only a single path is passed turn it into a 1 element list
        if isinstance(config['path'], basestring):
            config['path'] = [config['path']]
        return config

    @plugin.priority(-1)
    def on_task_filter(self, task, config):
        if not task.accepted:
            log.debug('Scanning not needed')
            return
        config = self.prepare_config(config)
        accepted_series = {}
        paths = set()
        for entry in task.accepted:
            if 'series_parser' in entry:
                if entry['series_parser'].valid:
                    accepted_series.setdefault(entry['series_parser'].name, []).append(entry)
                    for folder in config['path']:
                        try:
                            paths.add(entry.render(folder))
                        except RenderError as e:
                            log.error('Error rendering path `%s`: %s', folder, e)
                else:
                    log.debug('entry %s series_parser invalid', entry['title'])
        if not accepted_series:
            log.warning('No accepted entries have series information. exists_series cannot filter them')
            return

        # scan through
        # For speed, only test accepted entries since our priority should be after everything is accepted.
        for series in accepted_series:
            # make new parser from parser in entry
            series_parser = accepted_series[series][0]['series_parser']
            for folder in paths:
                folder = Path(folder).expanduser()
                if not folder.isdir():
                    log.warning('Directory %s does not exist', folder)
                    continue

                for filename in folder.walk(errors='ignore'):
                    # run parser on filename data
                    try:
                        disk_parser = get_plugin_by_name('parsing').instance.parse_series(data=filename.name,
                                                                                          name=series_parser.name)
                    except ParseWarning as pw:
                        disk_parser = pw.parsed
                        log_once(pw.value, logger=log)
                    if disk_parser.valid:
                        log.debug('name %s is same series as %s', filename.name, series)
                        log.debug('disk_parser.identifier = %s', disk_parser.identifier)
                        log.debug('disk_parser.quality = %s', disk_parser.quality)
                        log.debug('disk_parser.proper_count = %s', disk_parser.proper_count)

                        for entry in accepted_series[series]:
                            log.debug('series_parser.identifier = %s', entry['series_parser'].identifier)
                            if disk_parser.identifier != entry['series_parser'].identifier:
                                log.trace('wrong identifier')
                                continue
                            log.debug('series_parser.quality = %s', entry['series_parser'].quality)
                            if config.get('allow_different_qualities') == 'better':
                                if entry['series_parser'].quality > disk_parser.quality:
                                    log.trace('better quality')
                                    continue
                            elif config.get('allow_different_qualities'):
                                if disk_parser.quality != entry['series_parser'].quality:
                                    log.trace('wrong quality')
                                    continue
                            log.debug('entry parser.proper_count = %s', entry['series_parser'].proper_count)
                            if disk_parser.proper_count >= entry['series_parser'].proper_count:
                                entry.reject('proper already exists')
                                continue
                            else:
                                log.trace('new one is better proper, allowing')
                                continue


@event('plugin.register')
def register_plugin():
    plugin.register(FilterExistsSeries, 'exists_series', groups=['exists'], api_ver=2)
