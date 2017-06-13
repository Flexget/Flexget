from __future__ import unicode_literals, division, absolute_import
from builtins import *  # noqa pylint: disable=unused-import, redefined-builtin
from future.utils import native

import logging
import posixpath
import os
import re
from copy import copy

from flexget import plugin
from flexget.event import event

from flexget.utils.template import RenderError
from flexget.plugin import get_plugin_by_name
from flexget.utils.pathscrub import pathscrub
from flexget.plugins.filter.series import populate_entry_fields

log = logging.getLogger('modify_content_files')


class ModifyContentFiles(object):
    """
    Performs renaming operations on `content_files`.

    Hierarchy:
      keep_subs overrides rename_main_file_only
      rename_main_file_only overrides filetypes
      filetypes override unlisted_filetype_default
    """
    schema = {
        'type': 'object',
        'properties': {
            'main_file_only': {'type': 'boolean'},
            'main_file_ratio': {'type': 'number'},
            'keep_subs': {'type': 'boolean'},
            'keep_container': {'type': 'boolean'},
            'container_directory': {'type': 'string'},
            'container_only_for_multi': {'type': 'boolean'},
            'content_filename': {'type': 'string'},
            'rename_main_file_only': {'type': 'boolean'},
            'fix_year': {'type': 'boolean'},
            'unlisted_filetype_default': {
                'oneOf': [
                    {'type': 'boolean'},
                    {
                        'type': 'object',
                        'properties': {
                            'rename': {'type': 'boolean'},
                            'content_filename': {'type': 'string'},
                            'download': {'type': 'integer'},
                            'priority': {'type': 'integer'}
                        },
                        'additionalProperties': False
                    }
                ]
            },
            'filetypes': {
                'type': 'object',
                'additionalProperties': {
                    'oneOf': [
                        {'type': 'boolean'},
                        {
                            'type': 'object',
                            'properties': {
                                'rename': {'type': 'boolean'},
                                'content_filename': {'type': 'string'},
                                'download': {'type': 'integer'},
                                'priority': {'type': 'integer'}
                            },
                            'additionalProperties': False
                        }
                    ]
                }
            }
        },
        'additionalProperties': False
    }

    def prepare_config(self, config):
        config.setdefault('main_file_only', False)
        config.setdefault('main_file_ratio', 0.90)
        config.setdefault('keep_container', True)
        config.setdefault('container_directory', '')
        config.setdefault('container_only_for_multi', True)
        config.setdefault('fix_year', False)
        config.setdefault('rename_main_file_only', False)
        config.setdefault('unlisted_filetype_default', True)
        config.setdefault('filetypes', {})
        return config

    @plugin.priority(128)
    def on_task_modify(self, task, config):
        config = self.prepare_config(config)
        for entry in task.accepted:
            modified_content_files = []
            if entry.get('content_files'):
                content_files = entry['content_files']
            else:
                entry.fail('`content_files` not present in entry')
            if entry.get('content_size'):
                total_size = entry['content_size'] * 1024 * 1024
            else:
                entry.fail('Unable to determine content total size')

            file_ratio = total_size * config['main_file_ratio']
            log.debug('Torrent size: %s, main file size minimum: %s', total_size, file_ratio)

            main_fileid = -1
            subs_fileid = -1
            top_levels = []
            # loop through to determine main_fileid and if there is a top-level folder
            for count, file_info in enumerate(content_files):
                # split path into directory structure
                structure = (file_info['new_path'].split(os.sep) if file_info.get('new_path')
                             else file_info['path'].split(os.sep))
                # if there is more than 1 directory, there is a top-level; if so, add it to the list
                if len(structure) > 1:
                    top_levels.extend([structure[0]])
                # if this file is greater than main_file_ratio% of the total torrent size, it is the "main" file
                log.trace('File size is %s for file `%s`', file_info['content_size'],
                          file_info['new_path'] if file_info.get('new_path') else file_info['path'])
                if content_file_sizes[count] > file_ratio:
                    log.trace('--> Greater than main_file_ratio')
                    main_fileid = count
                    if not config.get('keep_subs') or subs_fileid:
                        break
                if config.get('keep_subs'):
                    sub_exts = [".srt", ".sub"]
                    if os.path.splitext(t_file)[1] in sub_exts:
                        log.trace('--> Subs file is `%s`', t_file)
                        subs_fileid = count
                        if main_fileid:
                            break

            top_level = False
            if len(set(top_levels)) == 1:
                top_level = True
                log.trace('Common top level folder detected.')
            if main_fileid < 0:
                if config.get('rename_main_file_only'):
                    log.verbose('No files in `%s` are > %s%% of content size. No files will be renamed.',
                                entry['title'], config.get('main_file_ratio')*100)
            else:
                log.trace('main_fileid: %s', main_fileid)

            series_tokens = False
            if config.get('content_filename') and 'series_' in config['content_filename']:
                series_tokens = True
                log.trace('Series token(s) present, obtaining parser')
                search_title = entry['title']
                # no point in finding/creating a parser now if it's a season pack, since in that case it has to be run
                # for each file
                if not entry.get('season_pack') and not entry.get('season_pack_lookup'):
                    if entry.get('series_parser'):
                        log.debug('Copying entry parser')
                        tokens_title_parser = copy(entry['series_parser'])
                    elif entry.get('series_name'):
                        log.debug('Creating parser with series name')
                        tokens_title_parser = \
                            get_plugin_by_name('parsing').instance.parse_series(data=search_title,
                                                                                name=entry['series_name'])
                    else:
                        log.debug('Creating parser without series name')
                        tokens_title_parser = get_plugin_by_name('parsing').instance.parse_series(data=search_title)

            new_filenames = []
            os_sep = os.sep
            do_container = False
            if ((config.get('container_only_for_multi') and len(content_files) > 1)
                 or not config.get('container_only_for_multi')):
                do_container = True
            for count, file_info in enumerate(content_files):
                entry_copy = copy(entry)
                original_pathfile = t_file
                log.debug('Current file: %s', original_pathfile)

                original_path = cur_path = os.path.split(t_file)[0]
                original_filename = cur_filename = os.path.split(t_file)[1]
                original_ext = os.path.splitext(original_filename)[1][1:]

                content_filename = ''
                if config.get('keep_subs') and count == subs_fileid:
                    log.debug('This is subs file, renaming it.')
                    file_settings.update({'subs_file': True, 'rename': True, 'download': 1})
                if config.get('rename_main_file_only') and count == main_fileid:
                    log.debug('This is main file, renaming it.')
                    file_settings.update({'main_file': True, 'rename': True, 'download': 1})
                if original_ext in config.get('filetypes') or config.get('unlisted_filetype_default'):
                    this_filetype = (config['filetypes'][original_ext] if original_ext in config.get('filetypes')
                                     else config['unlisted_filetype_default'])
                    if isinstance(this_filetype, dict):
                        log.trace('Settings or default settings present for this filetype.')
                        file_settings.update({'rename': True if this_filetype.get('rename') else False,
                                              'download': True if this_filetype.get('download') else False,
                                              'priority': this_filetype['priority'] if
                                              this_filetype.get('priority') else 0})
                        if this_filetype.get('content_filename'):
                            file_settings.update({'content_filename': this_filetype.get['content_filename']})
                    else:
                        file_settings = {'rename': True, 'download': 1, 'priority': 1}
                if file_settings.get('rename') and not file_settings.get('content_filename'):
                    if entry.get('content_filename', config.get('content_filename')):
                        log.debug('Using content_filename for renaming template.')
                        file_settings.update({'content_filename': entry.get('content_filename',
                                                                            config.get('content_filename'))})
                    else:
                        file_settings.update({'rename': False})
                        log.error('Settings indicate to rename file, but content_filename template was not provided.')

                removed_container = ''
                if series_tokens and (config.get('container_directory') or content_filename):
                    if entry_copy.get('season_pack') or entry_copy.get('season_pack_lookup'):
                        # season pack - must run new parser for each file
                        parser = get_plugin_by_name('parsing').instance.parse_series(data=cur_filename,
                                                                                     name=entry_copy['series_name'])
                    elif not entry_copy.get('series_parser') or not entry_copy['series_parser'].valid:
                        log.trace('Using new parser')
                        if 'series_name' in entry_copy:
                            parser = get_plugin_by_name('parsing').instance.parse_series(data=cur_filename,
                                                                                         name=entry_copy['series_name'])
                        else:
                            parser = get_plugin_by_name('parsing').instance.parse_series(data=cur_filename)
                    else:
                        parser = entry_copy['series_parser']

                    if parser and parser.valid:
                        populate_entry_fields(entry_copy, parser, False)
                        if entry.get('season_pack'):
                            # if the original entry is a season pack, flag individual file as well for jinja purposes
                            entry_copy['season_pack'] = True
                        if config.get('fix_year') and re.search(r'\d{4}', entry_copy['series_name'][-4:]):
                            entry_copy['series_name'] = ''.join([entry_copy['series_name'][0:-4], '(',
                                                           entry_copy['series_name'][-4:], ')'])

                if not config.get('keep_container') and top_level:
                    log.debug('Existing path: %s', cur_path)
                    removed_container_path = cur_path.split(os.sep)[0]
                    log.debug('Removed container: %s', removed_container_path)
                    cur_path = os_sep.join(cur_path.split(os.sep)[1:])
                    log.debug('New path: %s', cur_path)
                    removed_container = True

                if config.get('container_directory') and do_container:
                    try:
                        container_directory = pathscrub(entry_copy.render(config.get('container_directory')))
                        cur_path = os.path.join(container_directory, cur_path)
                        log.debug('Added container directory. New path: %s', cur_path)
                    except RenderError as e:
                        log.error('Error rendering container_directory for `%s`: %s', cur_filename, e)
                        if removed_container:
                            # this seems silly but it's reversing the change by putting the value
                            # of container_directory back to what it was
                            container_directory = removed_container_path
                            cur_path = os.path.join(container_directory, cur_path)
                            log.debug('Due to failure to add container, readding removed container to path. '
                                      'New path: %s', cur_path)

                if file_settings.get('content_filename') and file_settings.get('rename'):
                    try:
                        cur_filename = pathscrub(entry_copy.render(content_filename))
                        log.debug('Rendered filename: %s', cur_filename)
                    except RenderError as e:
                        log.error('Error rendering content_filename for `%s`: %s', original_filename, e)

                    if cur_filename[-len(original_ext):] != original_ext:
                        log.trace('Appending extension to `%s`', cur_filename)
                        cur_filename = ''.join([cur_filename, '.', original_ext])
                    if new_filenames.count(os.path.join(cur_path, cur_filename)) > 0:
                        entry.fail('Duplicate filenames would result from renaming')
                    if cur_filename != original_filename:
                        new_filenames.append(os.path.join(cur_path, cur_filename))
                        log.verbose('File `%s` will be renamed to `%s`', original_pathfile,
                                    os.path.join(cur_path, cur_filename))
                    else:
                        log.debug('New and old filenames matched, no action will be taken')

                # hide sparse files
                if config.get('main_file_only') and not main_file and config.get('hide_sparse_files'):
                    if not config.get('keep_subs') or not subs_file:
                        top_dir = cur_path.split(os.sep)[0] if len(cur_path.split(os.sep)) > 1 else ''
                        cur_path = os.path.join(top_dir, '.sparse_files' + add_path, cur_path)
                        log.trace('Moved file into sparse_file directory: `%s`', cur_path)
                        file_settings.update({'download': 0})

                for key in ['download', 'priority']:
                    if file_settings.get(key):
                        content_files[count].update({key: file_settings[key]})
                if cur_filename != original_filename:
                    content_files[count].update({'new_path': os.path.join(cur_path, cur_filename)})

            entry['content_files'] = content_files


@event('plugin.register')
def register_plugin():
    plugin.register(ModifyContentFiles, 'modify_content_files', api_ver=2)
