from __future__ import unicode_literals, division, absolute_import
import os
import shutil
import logging
import time

from flexget import plugin
from flexget.event import event
from flexget.utils.template import RenderError
from flexget.utils.pathscrub import pathscrub


def get_directory_size(directory):
    """
    :param directory: Path
    :return: Size in bytes (recursively)
    """
    dir_size = 0
    for (path, dirs, files) in os.walk(directory):
        for file in files:
            filename = os.path.join(path, file)
            dir_size += os.path.getsize(filename)
    return dir_size


class BaseFileOps(object):
    
    # Defined by subclasses
    log = None
    
    def on_task_output(self, task, config):
        if config is True:
            config = {}
        elif config is False:
            return
        
        sexts = []
        if 'along' in config:
            sexts = [('.' + s).replace('..', '.').lower() for s in config['along']]
        
        for entry in task.accepted:
            if not 'location' in entry:
                self.log.verbose('Cannot handle %s because it does not have the field location.' % entry['title'])
                continue
            
            # check location
            src = entry['location']
            src_isdir = os.path.isdir(src)
            try:
                if not os.path.exists(src):
                    raise Exception('does not exists (anymore).')
                if src_isdir:
                    if not config.get('allow_dir'):
                        raise Exception('is a directory.')
                elif not os.path.isfile(src):
                    raise Exception('is not a file.')
            except Exception as err:
                self.log.warning('Cannot handle %s because location `%s` %s' % (entry['title'], src, err))
                continue
            
            # search for namesakes
            siblings = []
            if not src_isdir and 'along' in config:
                src_file, src_ext = os.path.splitext(src)
                for ext in sexts:
                    if ext != src_ext.lower() and os.path.exists(src_file + ext):
                        siblings.append(src_file + ext)
            
            # execute action in subclasses
            self.handle_entry(task, config, entry, siblings)
    
    def clean_source(self, task, config, entry):
        min_size = entry.get('clean_source', config.get('clean_source', -1))
        if min_size < 0:
            return
        base_path = os.path.split(entry['location'])[0]
        if not os.path.isdir(base_path):
            self.log.warning('Cannot delete path `%s` because it does not exists (anymore).' % base_path)
            return
        dir_size = get_directory_size(base_path) / 1024 / 1024
        if dir_size >= min_size:
            self.log.info('Path `%s` left because it exceeds safety value set in clean_source option.' % base_path)
            return
        if task.options.test:
            self.log.info('Would delete `%s` and everything under it.' % base_path)
            return
        try:
            shutil.rmtree(base_path)
            self.log.info('Path `%s` has been deleted because was less than clean_source safe value.' % base_path)
        except Exception as err:
            self.log.warning('Unable to delete path `%s`: %s' % (base_path, err))


class DeleteFiles(BaseFileOps):
    """Delete all accepted files."""

    schema = {
        'oneOf': [
            {'type': 'boolean'},
            {
                'type': 'object',
                'properties': {
                    'allow_dir': {'type': 'boolean'},
                    'along': {'type': 'array', 'items': {'type': 'string'}},
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
                self.log.info('Would delete `%s` and all its content.' % src)
            else:
                self.log.info('Would delete `%s`' % src)
                for s in siblings:
                    self.log.info('Would also delete `%s`' % s)
            return
        
        try:
            if src_isdir:
                shutil.rmtree(src)
                self.log.info('`%s` and all its content has been deleted.' % src)
            else:
                os.remove(src)
                self.log.info('`%s` has been deleted.' % src)
        except Exception as err:
            entry.fail('delete error: %s' % err)
            return
        
        for s in siblings:
            try:
                os.remove(s)
                self.log.info('`%s` has been deleted as well.' % s)
            except Exception as err:
                # the target file has been successfully deleted, we cannot mark the entry as failed anymore. 
                self.log.warning('Unable to delete `%s`: %s' % (s, err))
        
        if not src_isdir:
            self.clean_source(task, config, entry)


class TransformingOps(BaseFileOps):
    
    # Defined by subclasses
    move = None
    
    def handle_entry(self, task, config, entry, siblings):
        src = entry['location']
        src_isdir = os.path.isdir(src)
        src_path, src_name = os.path.split(src)
        
        # get proper value in order of: entry, config, above split
        dst_path = entry.get('path', config.get('to', src_path))
        dst_name = entry.get('filename', config.get('filename', src_name))
        
        try:
            dst_path = entry.render(dst_path)
        except RenderError as err:
            self.log.warning('Path value replacement `%s` failed for %s: %s' % (dst_path, entry['title'], err))
            return
        try:
            dst_name = entry.render(dst_name)
        except RenderError as err:
            self.log.warning('Filename value replacement `%s` failed for %s: %s' % (dst_name, entry['title'], err))
            return
        
        # Clean invalid characters with pathscrub plugin
        dst_path = os.path.expanduser(dst_path)
        dst_name = pathscrub(dst_name, filename=True)
        
        # Join path and filename
        dst = os.path.join(dst_path, dst_name)
        if dst == entry['location']:
            self.log.warning('Cannot handle %s because source and destination are the same.' % entry['title'])
            return
        
        if not os.path.exists(dst_path):
            if task.options.test:
                self.log.info('Would create `%s`' % dst_path)
            else:
                self.log.info('Creating destination directory `%s`' % dst_path)
                os.makedirs(dst_path)
        if not os.path.isdir(dst_path) and not task.options.test:
            self.log.warning('Cannot handle %s because destination `%s` is not a directory' % (entry['title'], dst_path))
            return
        
        # unpack_safety
        if config.get('unpack_safety', entry.get('unpack_safety', True)):
            count = 0
            while True:
                if count > 60 * 30:
                    entry.fail('The task has been waiting unpacking for 30 minutes')
                    return
                size = os.path.getsize(src)
                time.sleep(1)
                new_size = os.path.getsize(src)
                if size != new_size:
                    if not count % 10:
                        self.log.verbose('File `%s` is possibly being unpacked, waiting ...' % src_name)
                else:
                    break
                count += 1
        
        src_file, src_ext = os.path.splitext(src)
        dst_file, dst_ext = os.path.splitext(dst)
        
        # Check dst contains src_ext
        if dst_ext != src_ext:
            self.log.verbose('Adding extension `%s` to dst `%s`' % (src_ext, dst))
            dst += src_ext
        
        funct_name = 'move' if self.move else 'copy'
        funct_done = 'moved' if self.move else 'copied'
        
        if task.options.test:
            self.log.info('Would %s `%s` to `%s`' % (funct_name, src, dst))
            for s in siblings:
                # we cannot rely on splitext for extensions here (subtitles may have the language code)
                d = dst_file + s[len(src_file):]
                self.log.info('Would also %s `%s` to `%s`' % (funct_name, s, d))
        else:
            try:
                if self.move:
                    shutil.move(src, dst)
                elif src_isdir:
                    shutil.copytree(src, dst)
                else:
                    shutil.copy(src, dst)
                self.log.info('`%s` has been %s to `%s`' % (src, funct_done, dst))
            except Exception as err:
                entry.fail('%s error: %s' % (funct_name, err))
                return
            for s in siblings:
                # we cannot rely on splitext for extensions here (subtitles may have the language code)
                d = dst_file + s[len(src_file):]
                try:
                    if self.move:
                        shutil.move(s, d)
                    else:
                        shutil.copy(s, d)
                    self.log.info('`%s` has been %s to `%s` as well.' % (s, funct_done, d))
                except Exception as err:
                    # the target file has been successfully handled, we cannot mark the entry as failed anymore.
                    self.log.warning('Unable to %s `%s` to `%s`: %s' % (funct_name, s, d, err))
        
        entry['output'] = dst
        
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
                    'filename': {'type': 'string'},
                    'allow_dir': {'type': 'boolean'},
                    'unpack_safety': {'type': 'boolean'},
                    'along': {'type': 'array', 'items': {'type': 'string'}}
                },
                'additionalProperties': False
            }
        ]
    }
    
    move = False
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
                    'filename': {'type': 'string'},
                    'allow_dir': {'type': 'boolean'},
                    'unpack_safety': {'type': 'boolean'},
                    'along': {'type': 'array', 'items': {'type': 'string'}},
                    'clean_source': {'type': 'number'}
                },
                'additionalProperties': False
            }
        ]
    }
    
    move = True
    log = logging.getLogger('move')


@event('plugin.register')
def register_plugin():
    plugin.register(DeleteFiles, 'delete', api_ver=2)
    plugin.register(CopyFiles, 'copy', api_ver=2)
    plugin.register(MoveFiles, 'move', api_ver=2)
