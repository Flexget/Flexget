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
    """Performs renaming operations on files passed via status parameter. Expects Deluge status dict."""
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
                    'unlisted_filetype_default': {'type': 'boolean'},
                    'filetypes': {
                        'type': 'object',
                        'additionalProperties': {
                            'oneOf': [
                                {'type': 'string'},
                                {'type': 'boolean'},
                            ]
                        }
                    }
                },
                'additionalProperties': False
            }
        ]
    }

    # Hierarchy:
    #   keep_subs overrides rename_main_file_only
    #   rename_main_file_only overrides filetypes
    #   filetypes overrides unlisted_filetype_default
    def prepare_config(self, config):
        config.setdefault('keep_container', True)
        config.setdefault('container_directory', '')
        config.setdefault('container_multiple', '')
        config.setdefault('fix_year', False)
        config.setdefault('rename_main_file_only', False)
        config.setdefault('unlisted_filetype_default', True)
        config.setdefault('filetypes', {})
        return config

    def rename_files(self, entry, status, config):
        # get total torrent size
        file_ratio = status['total_size'] * config.get('main_file_ratio')
        log.debug('Torrent size: %s' % status['total_size'])
        log.debug('Main file ratio size: %s' % file_ratio)

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
            log.debug('File size is %s for file %d: %s' % (file['size'], file['index'], file['path']))
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
            log.debug('Common top level folder detected.')
        if entry['main_fileid'] < 0:
            # if main_fileid wasn't set in the prior loop, no file is greater than
            # main_file_ratio% of the total size, therefore this is likely a season pack
            if config.get('rename_main_file_only'):
                log.warning('No files in %s are > %s%% of content size, no files renamed.' % entry['title'], config.get('main_file_ratio')*100)

        log.debug('main_fileid: %s' % entry['main_fileid'])

        if series_tokens:
            tokens_title_parser = get_plugin_by_name('parsing').instance.parse_series(data=entry['title'])

        new_filenames = []
        files = {}
        os_sep = os.sep
        do_container = False
        if (config.get('container_multiple') and len(status['files']) > 1) or not config.get('container_multiple'):
            do_container = True
        for file in status['files']:
            original_pathfile = file['path']
            log.debug('Current file: %s', original_pathfile)

            cur_path = os.path.split(file['path'])[0]
            original_path = cur_path

            cur_filename = os.path.split(file['path'])[1]
            original_filename = cur_filename

            original_ext = os.path.splitext(original_filename)[1][1:]

            subs_file = False
            main_file = False
            rename_file = False
            content_filename = ''
            if config.get('keep_subs') and file['index'] == entry['sub_fileid']:
                log.debug('This is subs file, renaming it.')
                subs_file = True
                rename_file = True
            if config.get('rename_main_file_only') and file['index'] == entry['main_fileid']:
                log.debug('This is main file, renaming it.')
                main_file = True
                rename_file = True
            if original_ext in config.get('filetypes'):
                if isinstance(config.get('filetypes')[original_ext], basestring):
                    log.debug('Custom template present for this filetype.')
                    content_filename = config.get('filetypes')[original_ext]
                    rename_file = True
                elif config.get('filetypes')[original_ext]:
                    log.debug('Using content_filename to rename this filetype.')
                    rename_file = True
            elif config.get('unlisted_filetype_default'):
                log.debug('Filetype is unlisted, but default is to rename all files.')
                rename_file = True
            if rename_file and not content_filename:
                if config.get('content_filename'):
                    log.debug('Using content_filename for renaming template.')
                    content_filename = config.get('content_filename')
                else:
                    rename_file = False
                    log.error('Settings indicate to rename file, but content_filename template was not provided.')

            removed_container = ''

            if series_tokens and (config.get('container_directory') or content_filename):
                parser = get_plugin_by_name('parsing').instance.parse_series(data=cur_filename)
                if not parser or not parser.valid:
                    parser = tokens_title_parser
                if parser and parser.valid:
                    try:
                        entry.pop('series_id')
                        entry.pop('season')
                        entry.pop('series_name')
                    except:
                        pass

                    entry['series_name'] = parser.name
                    if re.search(r'\d{4}', entry['series_name'][-4:]) is not None and config['fix_year']:
                        entry['series_name'] = ''.join([entry['series_name'][0:-4], '(',
                                                       entry['series_name'][-4:], ')'])
                    log.verbose('Series: ' + entry['series_name'])
                    log.debug('ID type: ' + parser.id_type)
                    entry['season'] = ''
                    if parser.id_type == 'ep':
                        entry['season'] = parser.season
                        entry['series_id'] = 'S' + str(parser.season).rjust(2, str('0')) + 'E'
                        entry['series_id'] += str(parser.episode).rjust(2, str('0'))
                    elif parser.id_type == 'sequence':
                        entry['series_id'] = parser.episode
                    elif parser.id_type and parser.id:
                        entry['series_id'] = parser.id

            if not config.get('keep_container') and top_level:
                removed_container = cur_path.split(os.sep)[0]
                cur_path = os_sep.join(cur_path.split(os.sep)[1:])
                log.debug('Removed container directory. New path: %s', cur_path)
                removed_container = True

            if config.get('container_directory') and do_container:
                try:
                    container_directory = pathscrub(entry.render(config.get('container_directory')))
                    cur_path = os.path.join(container_directory, cur_path)
                    log.debug('Added container directory. New path: %s', cur_path)
                except RenderError as e:
                    log.error('Error rendering container_directory for %s: %s' % (cur_filename, e))
                    if removed_container:
                        container_directory = removed_container
                        cur_path = os.path.join(container_directory, cur_path)
                        log.debug('Due to failure to add container, readding removed container to path. New path: %s', cur_path)

            if content_filename and rename_file:
                try:
                    cur_filename = pathscrub(entry.render(content_filename))
                    log.debug('Rendered filename: %s', cur_filename + os.path.splitext(original_filename)[1])
                except RenderError as e:
                    log.error('Error rendering content_filename for %s: %s' % (original_filename, e))
                cur_withext = cur_filename + os.path.splitext(original_filename)[1]
                if cur_filename != original_filename:
                    new_filenames.append(os.path.join(cur_path, cur_withext))
                if new_filenames.count(os.path.join(cur_path, cur_withext)) > 1:
                    # if this exact path & filename has been used before, append -# to it
                    cur_filename = ''.join([cur_filename, '-', str(new_filenames.count(cur_withext)), os.path.splitext(original_filename)[1]])
                elif cur_filename[-len(original_ext):] != original_ext:
                    cur_filename = cur_withext

            # hide sparse files
            if config.get('main_file_only') and not main_file and config.get('hide_sparse_files'):
                if not config.get('keep_subs') or not subs_file:
                    if container_directory:
                        add_path = container_directory
                    elif cur_filename:
                        add_path = cur_filename
                    else:
                        add_path = ''
                    cur_path = os.path.join(['._' + add_path, cur_path])

            if original_pathfile != os.path.join(cur_path, cur_filename):
                files[file['index']] = os.path.join(cur_path, cur_filename)

        return files


@event('plugin.register')
def register_plugin():
    plugin.register(TorrentRenameFiles, 'torrent_frename', api_ver=2)
