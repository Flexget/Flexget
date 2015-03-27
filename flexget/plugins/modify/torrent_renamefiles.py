from __future__ import unicode_literals, division, absolute_import
import logging
import posixpath
import os
import re

from flexget import plugin
from flexget.event import event

from flexget.utils.template import RenderError
from flexget.plugin import get_plugin_by_name
from flexget.utils.pathscrub import pathscrub


log = logging.getLogger('torrent_frename')

class TorrentRenameFiles(object):
    """Performs renaming operations on the content_files field"""
    schema = {
        'anyOf': [
            {
                'type': 'object',
                'properties': {
                    'keep_container': {'type': 'boolean'},
                    'container_directory': {'type': 'string'},
                    'container_multiple': {'type': 'boolean'},
                    'rename_main_file_only': {'type': 'boolean'},
                    'fix_year': {'type': 'boolean'},
                },
                'additionalProperties': False
            }
        ]
    }

    def prepare_config(self, config):
        config.setdefault('keep_container', True)
        config.setdefault('container_directory', '')
        config.setdefault('container_multiple', '')
        config.setdefault('fix_year', False)
        config.setdefault('rename_main_file_only', False)
        return config

    def on_task_rename(self, entry, status, config):
        # get total torrent size
        file_ratio = status['total_size'] * config.get('main_file_ratio')
        log.debug('File ratio: %s' % file_ratio)
        log.debug('Torrent size: %s' % status['total_size'])

        entry['main_fileid'] = -1
        entry['sub_fileid'] = -1

        series_tokens = False
        if config.get('content_filename'):
            cf = config.get('content_filename')
            if cf.find('series_id') > -1 or cf.find('season') > -1 or cf.find('series_name') > -1:
                series_tokens = True

        top_levels = []
        # loop through to determine main_fileid and if there is a top-level folder
        for file in status['files']:
            # split path into directory structure
            structure = file['path'].split(os.sep)
            # if there is more than 1 directory, there is a top-level; if so, add it to the list
            if len(structure) > 1:
                top_levels.extend([structure[0]])
            # if this file is greater than main_file_ratio% of the total torrent size, it is the "main" file
            log.debug('File size: %s' % file['size'])
            if file['size'] > file_ratio:
                log.debug('Greater than file_ratio: %s' % file['index'])
                entry['main_fileid'] = file['index']
                if config['keep_subs']:
                    sub_file = None
                    sub_exts = [".srt", ".sub"]
                    for sub_file in status['files']:
                        ext = os.path.splitext(sub_file['path'])[1]
                        if ext in sub_exts:
                            entry['sub_fileid'] = sub_file['index']
                            break
        top_level = False
        if len(set(top_levels)) == 1:
            # the top level of every item's path is the same, therefore there's a container directory
            top_level = True
        if entry['main_fileid'] < 0:
            # if main_fileid wasn't set in the prior loop, no file is greater than
            # main_file_ratio% of the total size, therefore this is likely a season pack
            if config.get('rename_main_file_only'):
                log.warning('No files in %s are > 90%% of content size, no files renamed.' % entry['title'])

        log.debug('main_fileid: %s' % entry['main_fileid'])

        new_filenames = []
        files = {}
        os_sep = os.sep
        do_container = False
        if (config.get('container_multiple') and len(status['files']) > 1) or not config.get('container_multiple'):
            do_container = True
        for file in status['files']:
            original_pathfile = file['path']
            cur_path = os.path.split(file['path'])[0]
            original_path = cur_path
            log.debug('Current path: %s', cur_path)
            cur_filename = os.path.split(file['path'])[1]
            original_filename = cur_filename
            log.debug('Current filename: %s', cur_filename)

            try:
                entry.pop('series_id')
                entry.pop('season')
                entry.pop('series_name')
            except:
                pass

            if series_tokens:
                parser = get_plugin_by_name('parsing').instance.parse_series(data=cur_filename)
                if parser and parser.valid:
                    entry['series_name'] = parser.name
                if re.search(r'\d{4}', entry['series_name'][-4:]) is not None and config['fix_year']:
                    entry['series_name'] = ''.join([entry['series_name'][0:-4], '(',
                                                   entry['series_name'][-4:], ')'])
                log.verbose(entry['series_name'])
                log.debug('ID type: ' + parser.id_type)
                if parser.id_type == 'ep':
                    entry['season'] = parser.season
                    entry['series_id'] = 'S' + str(parser.season).rjust(2, str('0')) + 'E'
                    entry['series_id'] += str(parser.episode).rjust(2, str('0'))
                elif parser.id_type == 'sequence':
                    entry['series_id'] = parser.episode
                elif parser.id_type and parser.id:
                    entry['series_id'] = parser.id

            if not config.get('keep_container') and top_level:# and len(cur_path) > 1:
                cur_path = os_sep.join(cur_path.split(os.sep)[1:])
                log.debug('Removed container directory. New path: %s', cur_path)
                removed_container = True

            if config.get('container_directory') and do_container:
                try:
                    container_directory = pathscrub(entry.render(config.get('container_directory')))
                    cur_path = os.path.join(container_directory, cur_path)
                    log.debug('Added container directory. New path: %s', cur_path)
                except RenderError as e:
                    log.error('Error rendering container_directory for %s: %s' % (cur_file, e))

            if config.get('content_filename') and (not config.get('rename_main_file_only') or
                (config.get('rename_main_file_only') and file['index'] == entry['main_fileid']) or
                (config.get('keep_subs') and file['index'] == entry['sub_fileid'])):

                try:
                    cur_filename = pathscrub(entry.render(config.get('content_filename')))
                    log.debug('Rendered filename: %s', cur_filename + os.path.splitext(original_filename)[1])
                except RenderError as e:
                    log.error('Error rendering content_filename for %s: %s' % (original_filename, e))
                cur_withext = cur_filename + os.path.splitext(original_filename)[1]
                if cur_withext in new_filenames:
                    # if this exact filename has been used before, append -# to it
                    cur_filename = ''.join(cur_filename, '-', str(new_filenames.count(cur_filename)), os.path.splitext(original_filename)[1])
                else:
                    cur_filename = cur_withext

            # hide sparse files
            if config.get('main_file_only') and file['index'] != entry['main_fileid'] and config.get('hide_sparse_files'):
                if not config.get('keep_subs') or (config.get('keep_subs') and entry['sub_fileid'] != file['index']):
                    if cur_filename:
                        add_path = cur_filename
                    elif container_directory:
                        add_path = container_directory
                    else:
                        add_path = ''
                    cur_path = os.path.join('._' + add_path, cur_path)

            if original_pathfile != os.path.join(cur_path, cur_filename):
                files[file['index']] = os.path.join(cur_path, cur_filename)
            if cur_filename != original_filename:
                new_filenames.append(cur_filename)

        return files


@event('plugin.register')
def register_plugin():
    plugin.register(TorrentRenameFiles, 'torrent_frename', api_ver=2)