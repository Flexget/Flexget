from __future__ import unicode_literals, division, absolute_import
from builtins import *  # noqa pylint: disable=unused-import, redefined-builtin

import logging
import os

from flexget import plugin
from flexget.event import event
from flexget.plugin import get_plugin_by_name, PluginError

log = logging.getLogger('torrent_match')


class TorrentMatch(object):
    """TODO"""

    schema = {
        'type': 'object',
        'properties': {
            'what': {'type': 'array', 'items': {
                'allOf': [{'$ref': '/schema/plugins?phase=input'}, {'maxProperties': 1, 'minProperties': 1}]
            }},
            'allowed_size_difference': {'type': 'string', 'format': 'percent'}
        },
        'required': ['what'],
        'additionalProperties': False
    }

    def execute_inputs(self, config, task):
        """
        :param config: TorrentMatch config
        :param task: Current task
        :return: List of pseudo entries created by inputs under `what` configuration
        """
        entries = set()
        entry_urls = set()
        # run inputs
        for item in config['what']:
            for input_name, input_config in item.items():
                input = get_plugin_by_name(input_name)
                if input.api_ver == 1:
                    raise PluginError('Plugin %s does not support API v2' % input_name)
                method = input.phase_handlers['input']
                try:
                    result = method(task, input_config)
                except PluginError as e:
                    log.warning('Error during input plugin %s: %s', input_name, e)
                    continue
                if not result:
                    log.warning('Input %s did not return anything', input_name)
                    continue

                for entry in result:
                    urls = ([entry['url']] if entry.get('url') else []) + entry.get('urls', [])
                    if any(url in entry_urls for url in urls):
                        log.debug('URL for `%s` already in entry list, skipping.', entry['title'])
                        continue

                    entries.add(entry)
                    entry_urls.update(urls)
        return entries

    def get_content_files(self, config, task):
        cwd = os.getcwd()
        entries = self.execute_inputs(config, task)
        for entry in entries:
            location = entry.get('location')
            if not location or not os.path.exists(location):
                log.warning('%s is not a local file. Skipping.', entry['title'])
                entry.reject('not a local file')

            if os.path.isfile(location):
                entry['files_root'] = ''
                entry['files']([{
                    'path': os.path.basename(location),
                    'size': os.path.getsize(location)
                }])
            elif os.path.isdir(location):
                # change working dir to make things simpler
                os.chdir(location)
                entry['files_root'] = os.path.basename(location)
                entry['files'] = []
                # traverse the file tree
                for root, _, files in os.walk('.'):
                    stripped_root = root.lstrip('.')  # remove the dot
                    for f in files:
                        file_path = os.path.join(stripped_root, f)
                        entry['files'].append({
                            'path': os.path.join(entry['files_root'], file_path),
                            'size': os.path.getsize(file_path)
                        })
            else:
                log.error('Does this happen?')
            os.chdir(cwd)

        return entries

    # run first to ensure we have temp files so that torrent plugin can do its magic
    @plugin.priority(256)
    def on_task_modify(self, task, config):
        for entry in task.accepted:
            if 'torrent' not in entry and 'download' not in task.config:
                # If the download plugin is not enabled, we need to call it to get
                # our temp .torrent files
                download = plugin.get_plugin_by_name('download')
                download.instance.get_temp_files(task, handle_magnets=True, fail_html=True)

    # Run first
    @plugin.priority(255)
    def on_task_output(self, task, config):
        local_entries = self.get_content_files(config, task)

        matched_entries = set()
        for entry in task.accepted:
            if 'torrent' not in entry:
                log.debug('Skipping entry %s as it is not a torrent file', entry['title'])
                continue

            torrent_files = []
            for item in entry['torrent'].get_filelist():
                # if torrent is a multi_file, prepend the name
                path = os.path.join(item['path'], item['name'])
                if entry['torrent'].is_multi_file:
                    path = os.path.join(entry['torrent'].name, path)

                torrent_files.append({
                    'path': path,
                    'size': item['size']
                })

            for local_entry in local_entries:
                local_files = local_entry['files']

                # there should be at least as many local files as torrent files, TODO allow smaller files to be missing
                if len(torrent_files) > len(local_files):
                    log.debug('Skipping %s because it has %s files, expected at least %s', local_entry['title'],
                              len(local_files), len(torrent_files))
                    continue

                # skip root dir of the local entry if torrent is single file
                skip_root_dir = not entry['torrent'].is_multi_file and local_entry['files_root']

                matches = 0
                for f in torrent_files:
                    for local_file in local_files:
                        # if f == local_file, break out of inner loop and increment match counter
                        # TODO allow root dir to differ? Requires torrent clients have "do not add name to path"
                        local_path = local_file['path']
                        if skip_root_dir:
                            local_path = os.path.relpath(local_path, local_entry['files_root'])
                        if f['path'] == local_path and f['size'] == local_file['size']:
                            matches += 1
                            break
                # as of now, we require that the number of matches is the same as the number of files in torrent
                if matches == len(torrent_files):
                    matched_entries.add(entry)
                    if skip_root_dir:
                        entry['path'] = local_entry['location']
                    else:
                        entry['path'] = os.path.dirname(local_entry['location'])

                    log.debug('Torrent %s matched path %s', entry['title'], entry['path'])

        for entry in set(task.accepted).difference(matched_entries):
            entry.reject('No local files found.')


@event('plugin.register')
def register_plugin():
    plugin.register(TorrentMatch, 'torrent_match', api_ver=2)
