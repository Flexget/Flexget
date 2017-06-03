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


log = logging.getLogger('torrent_rename_files')

class TorrentRenameFiles(object):
    """
    Performs renaming operations on `content_files`, or `modified_content_files` if it exists in entry.


    Hierarchy:
      keep_subs overrides rename_main_file_only
      rename_main_file_only overrides filetypes
      filetypes overrides unlisted_filetype_default
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

    def prepare_config(self, config):
        config.setdefault('main_file_only', False)
        config.setdefault('main_file_ratio', 0.90)
        config.setdefault('keep_container', True)
        config.setdefault('container_directory', '')
        config.setdefault('container_only_for_multi', '')
        config.setdefault('fix_year', False)
        config.setdefault('rename_main_file_only', False)
        config.setdefault('unlisted_filetype_default', True)
        config.setdefault('filetypes', {})
        return config

    def on_task_modify(self, task, config):
        config = self.prepare_config(config)
        for entry in task.accepted:
            if entry.get('modified_content_files'):
                content_keys = [k for k in entry['modified_content_files'].keys()]
                content_files = [f['new_path'] for f in entry['modified_content_files']]
            else:
                content_keys = content_files = entry['content_files']
            # get total torrent size
            if entry.get('torrent'):
                total_size = entry['torrent'].size
            elif entry.get('content_size'):
                total_size = entry['content_size'] * 1024 * 1024
            else:
                entry.fail('Unable to determine torrent size')
            file_ratio = total_size * config['main_file_ratio']
            log.debug('Torrent size: %s, main file size minimum: %s', total_size, file_ratio)

            main_fileid = -1
            subs_fileid = -1
            top_levels = []
            # loop through to determine main_fileid and if there is a top-level folder
            for count, t_file in enumerate(entry['torrent'].get_filelist()):
                # split path into directory structure
                structure = t_file['path'][:-1] if t_file['path'] else t_file['name'].split(os.sep)
                # if there is more than 1 directory, there is a top-level; if so, add it to the list
                if len(structure) > 1:
                    top_levels.extend([structure[0]])
                # if this file is greater than main_file_ratio% of the total torrent size, it is the "main" file
                log.trace('File size is %s for file: %s', t_file['size'], t_file['path'])
                if t_file['size'] > file_ratio:
                    log.trace('Greater than main_file_ratio: %s', count)
                    main_fileid = count
                    if config.get('keep_subs'):
                        sub_file = None
                        sub_exts = [".srt", ".sub"]
                        for count, sub_file in enumerate(entry['content_files']):
                            if os.path.splitext(sub_file['path'])[1] in sub_exts:
                                subs_fileid = count
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
                # no point in generating a parser now if it's a season pack, since in that case it has to be run
                # for each file
                if not entry.get('season_pack') and not entry.get('season_pack_lookup'):
                    if entry.get('series_parser'):
                        log.trace('Copying entry parser')
                        tokens_title_parser = copy(entry['series_parser'])
                    elif entry.get('series_name'):
                        log.trace('Creating parser with series name')
                        tokens_title_parser = \
                            get_plugin_by_name('parsing').instance.parse_series(data=search_title,
                                                                                name=entry['series_name'])
                    else:
                        log.trace('Creating parser without series name')
                        tokens_title_parser = get_plugin_by_name('parsing').instance.parse_series(data=search_title)

            new_filenames = []
            files = {}
            os_sep = os.sep
            do_container = False
            if ((config.get('container_only_for_multi') and len(content_files) > 1)
                 or not config.get('container_only_for_multi')):
                do_container = True
            for count, t_file in enumerate(content_files):
                torrent_filename = (os.path.join(entry['torrent'].name, content_keys[count])
                                    if len(content_files) > 1 else content_keys[count])
                entry_copy = copy(entry)
                original_pathfile = t_file
                log.debug('Current file: %s', original_pathfile)

                original_path = cur_path = os.path.split(t_file)[0]
                original_filename = cur_filename = os.path.split(t_file)[1]
                original_ext = os.path.splitext(original_filename)[1][1:]

                to_download = subs_file = main_file = rename_file = False
                content_filename = ''
                if config.get('keep_subs') and count == subs_fileid:
                    log.debug('This is subs file, renaming it.')
                    subs_file = True
                    rename_file = True
                    to_download = True
                if config.get('rename_main_file_only') and count == main_fileid:
                    log.debug('This is main file, renaming it.')
                    main_file = True
                    rename_file = True
                    to_download = True
                if original_ext in config.get('filetypes'):
                    if isinstance(config.get('filetypes')[original_ext], basestring):
                        log.trace('Custom template present for this filetype.')
                        content_filename = config.get('filetypes')[original_ext]
                        rename_file = True
                        to_download = True
                    elif config.get('filetypes')[original_ext]:
                        log.trace('Using content_filename to rename this filetype.')
                        rename_file = True
                        to_download = True
                elif config.get('unlisted_filetype_default'):
                    log.trace('Filetype is unlisted, but default is to rename all files.')
                    rename_file = True
                    to_download = True
                if rename_file and not content_filename:
                    if config.get('content_filename'):
                        log.debug('Using content_filename for renaming template.')
                        content_filename = config.get('content_filename')
                    else:
                        rename_file = False
                        log.error('Settings indicate to rename file, but content_filename template was not provided.')

                removed_container = ''
                if series_tokens and (config.get('container_directory') or content_filename):
                    if entry_copy.get('season_pack') or entry_copy.get('season_pack_lookup'):
                        # season pack - must run new parser for each file
                        parser = get_plugin_by_name('parsing').instance.parse_series(data=cur_filename,
                                                                                     name=entry_copy['series_name'])
                    elif not entry_copy['series_parser'] or not entry_copy['series_parser'].valid:
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
                            entry_copy['season_pack'] = True
                        if re.search(r'\d{4}', entry_copy['series_name'][-4:]) and config.get('fix_year'):
                            entry_copy['series_name'] = ''.join([entry_copy['series_name'][0:-4], '(',
                                                           entry_copy['series_name'][-4:], ')'])

                if not config.get('keep_container') and top_level:
                    log.debug('Existing path: %s', cur_path)
                    removed_container_path = cur_path.split(os.sep)[0]
                    log.debug('Removed container: %s', removed_container)
                    cur_path = os_sep.join(cur_path.split(os.sep)[1:])
                    log.debug('New path: %s', cur_path)
                    removed_container = True

                if config.get('container_directory') and do_container:
                    try:
                        container_directory = pathscrub(entry_copy.render(config.get('container_directory')))
                        cur_path = os.path.join(container_directory, cur_path)
                        log.debug('Added container directory. New path: %s', cur_path)
                    except RenderError as e:
                        log.error('Error rendering container_directory for %s: %s', cur_filename, e)
                        if removed_container:
                            # this seems silly but it's reversing the change by putting the value
                            #   of container_directory back to what it was
                            container_directory = removed_container_path
                            cur_path = os.path.join(container_directory, cur_path)
                            log.debug('Due to failure to add container, readding removed container to path.'
                                      ' New path: %s', cur_path)

                if content_filename and rename_file:
                    try:
                        cur_filename = pathscrub(entry_copy.render(content_filename))
                        log.debug('Rendered filename: %s', cur_filename)
                    except RenderError as e:
                        log.error('Error rendering content_filename for %s: %s', original_filename, e)
                    cur_withext = cur_filename + os.path.splitext(original_filename)[1]
                    log.trace('Filename with extension: %s', cur_withext)

                    if new_filenames.count(os.path.join(cur_path, cur_withext)) > 0:
                        entry.fail('Duplicate filenames would result from renaming')
                    if cur_filename[-len(original_ext):] != original_ext:
                        cur_filename = cur_withext
                        log.trace('Appended extension to filename: %s', cur_filename)
                    if cur_filename != original_filename:
                        #cur_withext = cur_filename + original_ext
                        new_filenames.append(os.path.join(cur_path, cur_withext))
                        log.verbose('Added file to rename group: %s', os.path.join(cur_path, cur_withext))
                    #else:
                        #log.debug('New and old filenames matched, no action taken')

                # hide sparse files
                if config.get('main_file_only') and not main_file and config.get('hide_sparse_files'):
                    if not config.get('keep_subs') or not subs_file:
                        add_path = ''
                        if container_directory:
                            add_path = container_directory
                        elif cur_filename:
                            add_path = cur_filename
                        cur_path = os.path.join(['._' + add_path, cur_path])
                        log.trace('Changed cur_path: %s', cur_path)

                file_info = {'new_path': os.path.join(cur_path, cur_filename),
                             'download': 1 if to_download else 0}
                # if modified_content_files exists, we'll update it as we go. otherwise, files will put into
                # modified_content_files after all entries are processed
                if entry.get('modified_content_files'):
                    entry['modified_content_files'][torrent_filename].update(file_info)
                else:
                    files.update({torrent_filename: file_info})

            if not entry.get('modified_content_files'):
                entry['modified_content_files'] = files


@event('plugin.register')
def register_plugin():
    plugin.register(TorrentRenameFiles, 'torrent_rename_files', api_ver=2)
