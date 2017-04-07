from __future__ import unicode_literals, division, absolute_import
from builtins import *  # noqa pylint: disable=unused-import, redefined-builtin

import os
import shutil
import logging
import time

from flexget import plugin
from flexget.event import event
from flexget.config_schema import one_or_more
from flexget.utils.template import RenderError
from flexget.utils.pathscrub import pathscrub


def get_directory_size(directory):
    """
    :param directory: Path
    :return: Size in bytes (recursively)
    """
    dir_size = 0
    for (path, _, files) in os.walk(directory):
        for file in files:
            filename = os.path.join(path, file)
            dir_size += os.path.getsize(filename)
    return dir_size


def get_siblings(ext, main_file_no_ext, main_file_ext, abs_path):
    siblings = {}
    files = os.listdir(abs_path)

    for filename in files:
        # skip the main file
        if filename == main_file_no_ext + main_file_ext:
            continue
        filename_lower = filename.lower()
        if not filename_lower.startswith(main_file_no_ext.lower()) or not filename_lower.endswith(ext.lower()):
            continue
        # we have to use the length of the main file (no ext) to extract the rest of the filename
        # for the future renaming
        file_ext = filename[len(main_file_no_ext):]
        file_path = os.path.join(abs_path, filename)
        if os.path.exists(file_path):
            siblings[file_path] = file_ext
    return siblings


class BaseFileOps(object):
    # Defined by subclasses
    log = None
    along = {
        'type': 'object',
        'properties': {
            'extensions': one_or_more({'type': 'string'}),
            'subdirs': one_or_more({'type': 'string'})
        },
        'additionalProperties': False,
        'required': ['extensions']
    }

    def prepare_config(self, config):
        if config is True:
            return {}
        elif config is False:
            return

        if 'along' not in config:
            return config

        extensions = config['along'].get('extensions')
        subdirs = config['along'].get('subdirs')

        if extensions and not isinstance(extensions, list):
            config['along']['extensions'] = [extensions]
        if subdirs and not isinstance(subdirs, list):
            config['along']['subdirs'] = [subdirs]

        return config

    def on_task_output(self, task, config):
        config = self.prepare_config(config)
        if config is None:
            return
        for entry in task.accepted:
            if 'location' not in entry:
                self.log.verbose('Cannot handle %s because it does not have the field location.', entry['title'])
                continue
            src = entry['location']
            src_isdir = os.path.isdir(src)
            try:
                # check location
                if not os.path.exists(src):
                    self.log.warning('location `%s` does not exists (anymore).' % src)
                    continue
                if src_isdir:
                    if not config.get('allow_dir'):
                        self.log.warning('location `%s` is a directory.' % src)
                        continue
                elif not os.path.isfile(src):
                    self.log.warning('location `%s` is not a file.' % src)
                    continue
                # search for namesakes
                siblings = {}  # dict of (path=ext) pairs
                if not src_isdir and 'along' in config:
                    parent = os.path.dirname(src)
                    filename_no_ext, filename_ext = os.path.splitext(os.path.basename(src))
                    for ext in config['along']['extensions']:
                        siblings.update(get_siblings(ext, filename_no_ext, filename_ext, parent))

                    files = os.listdir(parent)
                    files_lower = list(map(str.lower, files))
                    for subdir in config['along'].get('subdirs', []):
                        try:
                            idx = files_lower.index(subdir)
                        except ValueError:
                            continue
                        subdir_path = os.path.join(parent, files[idx])
                        if not os.path.isdir(subdir_path):
                            continue
                        for ext in config['along']['extensions']:
                            siblings.update(get_siblings(ext, filename_no_ext, filename_ext, subdir_path))
                # execute action in subclasses
                self.handle_entry(task, config, entry, siblings)
            except (OSError, IOError) as err:
                entry.fail(str(err))
                continue

    def clean_source(self, task, config, entry):
        min_size = entry.get('clean_source', config.get('clean_source', -1))
        if min_size < 0:
            return
        base_path = os.path.split(entry.get('old_location', entry['location']))[0]
        # everything here happens after a successful execution of the main action: the entry has been moved in a
        # different location, or it does not exists anymore. so from here we can just log warnings and move on.
        if not os.path.isdir(base_path):
            self.log.warning('Cannot delete path `%s` because it does not exists (anymore).', base_path)
            return
        dir_size = get_directory_size(base_path) / 1024 / 1024
        if dir_size >= min_size:
            self.log.info('Path `%s` left because it exceeds safety value set in clean_source option.', base_path)
            return
        if task.options.test:
            self.log.info('Would delete `%s` and everything under it.', base_path)
            return
        try:
            shutil.rmtree(base_path)
            self.log.info('Path `%s` has been deleted because was less than clean_source safe value.', base_path)
        except Exception as err:
            self.log.warning('Unable to delete path `%s`: %s', base_path, err)

    def handle_entry(self, task, config, entry, siblings):
        raise NotImplementedError()


class DeleteFiles(BaseFileOps):
    """Delete all accepted files."""

    schema = {
        'oneOf': [
            {'type': 'boolean'},
            {
                'type': 'object',
                'properties': {
                    'allow_dir': {'type': 'boolean'},
                    'along': BaseFileOps.along,
                    'clean_source': {'type': 'number'}
                },
                'additionalProperties': False
            }
        ]
    }

    log = logging.getLogger('delete')

    def handle_entry(self, task, config, entry, siblings):
        src = entry['location']
        src_isdir = os.path.isdir(src)
        if task.options.test:
            if src_isdir:
                self.log.info('Would delete `%s` and all its content.', src)
            else:
                self.log.info('Would delete `%s`', src)
                for s, _ in siblings.items():
                    self.log.info('Would also delete `%s`', s)
            return
        # IO errors will have the entry mark failed in the base class
        if src_isdir:
            shutil.rmtree(src)
            self.log.info('`%s` and all its content has been deleted.', src)
        else:
            os.remove(src)
            self.log.info('`%s` has been deleted.', src)
        # further errors will not have any effect (the entry does not exists anymore)
        for s, _ in siblings.items():
            try:
                os.remove(s)
                self.log.info('`%s` has been deleted as well.', s)
            except Exception as err:
                self.log.warning(str(err))
        if not src_isdir:
            self.clean_source(task, config, entry)


class TransformingOps(BaseFileOps):
    # Defined by subclasses
    move = None
    destination_field = None

    def handle_entry(self, task, config, entry, siblings):
        src = entry['location']
        src_isdir = os.path.isdir(src)
        src_path, src_name = os.path.split(src)

        # get the proper path and name in order of: entry, config, above split
        dst_path = entry.get(self.destination_field, config.get('to', src_path))
        if config.get('rename'):
            dst_name = config['rename']
        elif entry.get('filename') and entry['filename'] != src_name:
            # entry specifies different filename than what was split from the path
            # since some inputs fill in filename it must be different in order to be used
            dst_name = entry['filename']
        else:
            dst_name = src_name

        try:
            dst_path = entry.render(dst_path)
        except RenderError as err:
            raise plugin.PluginError('Path value replacement `%s` failed: %s' % (dst_path, err.args[0]))
        try:
            dst_name = entry.render(dst_name)
        except RenderError as err:
            raise plugin.PluginError('Filename value replacement `%s` failed: %s' % (dst_name, err.args[0]))

        # Clean invalid characters with pathscrub plugin
        dst_path = pathscrub(os.path.expanduser(dst_path))
        dst_name = pathscrub(dst_name, filename=True)

        # Join path and filename
        dst = os.path.join(dst_path, dst_name)
        if dst == entry['location']:
            raise plugin.PluginWarning('source and destination are the same.')

        if not os.path.exists(dst_path):
            if task.options.test:
                self.log.info('Would create `%s`', dst_path)
            else:
                self.log.info('Creating destination directory `%s`', dst_path)
                os.makedirs(dst_path)
        if not os.path.isdir(dst_path) and not task.options.test:
            raise plugin.PluginWarning('destination `%s` is not a directory.' % dst_path)

        # unpack_safety
        if config.get('unpack_safety', entry.get('unpack_safety', True)):
            count = 0
            while True:
                if count > 60 * 30:
                    raise plugin.PluginWarning('The task has been waiting unpacking for 30 minutes')
                size = os.path.getsize(src)
                time.sleep(1)
                new_size = os.path.getsize(src)
                if size != new_size:
                    if not count % 10:
                        self.log.verbose('File `%s` is possibly being unpacked, waiting ...', src_name)
                else:
                    break
                count += 1

        src_file, src_ext = os.path.splitext(src)
        dst_file, dst_ext = os.path.splitext(dst)

        # Check dst contains src_ext
        if config.get('keep_extension', entry.get('keep_extension', True)):
            if not src_isdir and dst_ext != src_ext:
                self.log.verbose('Adding extension `%s` to dst `%s`', src_ext, dst)
                dst += src_ext
                dst_file += dst_ext  # this is used for sibling files. dst_ext turns out not to be an extension!

        funct_name = 'move' if self.move else 'copy'
        funct_done = 'moved' if self.move else 'copied'

        if task.options.test:
            self.log.info('Would %s `%s` to `%s`', funct_name, src, dst)
            for s, ext in siblings.items():
                # we cannot rely on splitext for extensions here (subtitles may have the language code)
                d = dst_file + ext
                self.log.info('Would also %s `%s` to `%s`', funct_name, s, d)
        else:
            # IO errors will have the entry mark failed in the base class
            if self.move:
                shutil.move(src, dst)
            elif src_isdir:
                shutil.copytree(src, dst)
            else:
                shutil.copy(src, dst)
            self.log.info('`%s` has been %s to `%s`', src, funct_done, dst)
            # further errors will not have any effect (the entry has been successfully moved or copied out)
            for s, ext in siblings.items():
                # we cannot rely on splitext for extensions here (subtitles may have the language code)
                d = dst_file + ext
                try:
                    if self.move:
                        shutil.move(s, d)
                    else:
                        shutil.copy(s, d)
                    self.log.info('`%s` has been %s to `%s` as well.', s, funct_done, d)
                except Exception as err:
                    self.log.warning(str(err))
        entry['old_location'] = entry['location']
        entry['location'] = dst
        if self.move and not src_isdir:
            self.clean_source(task, config, entry)


class CopyFiles(TransformingOps):
    """Copy all accepted files."""

    schema = {
        'oneOf': [
            {'type': 'boolean'},
            {
                'type': 'object',
                'properties': {
                    'to': {'type': 'string', 'format': 'path'},
                    'rename': {'type': 'string'},
                    'allow_dir': {'type': 'boolean'},
                    'unpack_safety': {'type': 'boolean'},
                    'keep_extension': {'type': 'boolean'},
                    'along': TransformingOps.along
                },
                'additionalProperties': False
            }
        ]
    }

    move = False
    destination_field = 'copy_to'
    log = logging.getLogger('copy')


class MoveFiles(TransformingOps):
    """Move all accepted files."""

    schema = {
        'oneOf': [
            {'type': 'boolean'},
            {
                'type': 'object',
                'properties': {
                    'to': {'type': 'string', 'format': 'path'},
                    'rename': {'type': 'string'},
                    'allow_dir': {'type': 'boolean'},
                    'unpack_safety': {'type': 'boolean'},
                    'keep_extension': {'type': 'boolean'},
                    'along': TransformingOps.along,
                    'clean_source': {'type': 'number'}
                },
                'additionalProperties': False
            }
        ]
    }

    move = True
    destination_field = 'move_to'
    log = logging.getLogger('move')


@event('plugin.register')
def register_plugin():
    plugin.register(DeleteFiles, 'delete', api_ver=2)
    plugin.register(CopyFiles, 'copy', api_ver=2)
    plugin.register(MoveFiles, 'move', api_ver=2)
