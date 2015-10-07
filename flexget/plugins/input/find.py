from __future__ import unicode_literals, division, absolute_import
from datetime import datetime
import logging
import re
import sys
import os

from path import Path

from flexget import plugin
from flexget.config_schema import one_or_more
from flexget.event import event
from flexget.entry import Entry

log = logging.getLogger('find')


class InputFind(object):
    """
    Uses local path content as an input, recurses through directories and creates entries for files that match mask.

    You can specify either the mask key, in shell file matching format, (see python fnmatch module,) or regexp key.

    Example::

      find:
        path: /storage/movies/
        mask: *.avi

    Example::

      find:
        path:
          - /storage/movies/
          - /storage/tv/
        regexp: .*\.(avi|mkv)$

    """
    retrieval_options = ['files', 'dirs', 'symlinks']

    schema = {
        'type': 'object',
        'properties': {
            'path': one_or_more({'type': 'string', 'format': 'path'}, unique_items=True),
            'mask': {'type': 'string'},
            'regexp': {'type': 'string', 'format': 'regex'},
            'recursive': {'type': 'boolean'},
            'recursion_depth': {'type': 'number'},
            'retrieve': one_or_more({'type': 'string', 'enum': retrieval_options}, unique_items=True)
        },
        'required': ['path'],
        'additionalProperties': False
    }

    def create_entry(self, filepath, test_mode, type=None):
        """
        Creates a single entry using a filepath and a type (file/dir)
        """
        entry = Entry()
        filepath = Path(filepath)

        entry['location'] = filepath
        entry['url'] = 'file://{}'.format(filepath)
        entry['filename'] = filepath.name
        if not type:
            entry['title'] = filepath.namebase
        else:
            entry['title'] = filepath.name
        try:
            entry['timestamp'] = os.path.getmtime(filepath)
        except Exception as e:
            log.debug('Error setting timestamp for %s: %s' % (filepath, e))
            entry['timestamp'] = None
        if entry.isvalid():
            if test_mode:
                log.info("Test mode. Entry includes:")
                log.info("    Title: %s" % entry["title"])
                log.info("    URL: %s" % entry["url"])
                log.info("    Filename: %s" % entry["filename"])
                log.info("    Location: %s" % entry["location"])
                log.info("    Timestamp: %s" % entry["timestamp"])
            return entry
        else:
            log.error('Non valid entry created: {}'.format(entry))
            return

    def prepare_config(self, config):
        config = config
        from fnmatch import translate
        # If only a single path is passed turn it into a 1 element list
        if isinstance(config['path'], basestring):
            config['path'] = [config['path']]
        config.setdefault('recursive', False)
        # If mask was specified, turn it in to a regexp
        if config.get('mask'):
            config['regexp'] = translate(config['mask'])
        # If no mask or regexp specified, accept all files
        config.setdefault('regexp', '.')
        # Sets the default retrieval option to files
        config.setdefault('retrieve', self.retrieval_options)
        # Sets default recursion level to all levels
        config.setdefault('recursion_depth', -1)

        return config

    def get_entries_from_dir_recursively(self, folder, match, recursion_depth, test_mode, get_files, get_dirs,
                                         get_symlinks):
        entries = []

        log.debug('Starting to work on a recursive folder {0}.'.format(folder))
        for root, dirs, files in os.walk(folder, followlinks=get_symlinks):
            current_depth = str(root).replace(str(folder), '').count(os.path.sep)
            if recursion_depth == -1 or current_depth <= recursion_depth:
                if get_files:
                    for file in files:
                        if match(file):
                            fullpath = str(root) + os.path.sep + str(file)
                            entry = self.create_entry(fullpath, test_mode)
                            if entry:
                                entries.append(entry)
                if get_dirs:
                    for dir in dirs:
                        if match(dir):
                            fullpath = str(root) + os.path.sep + str(dir)
                            entry = self.create_entry(fullpath, test_mode, type='dir')
                            if entry:
                                entries.append(entry)
        return entries

    def get_entries_from_dir(self, folder, match, test_mode, get_files, get_dirs, get_symlinks):
        entries = []

        log.debug('Starting to work on a non-recursive folder {0}.'.format(folder))
        try:
            dir_files = folder.listdir()
        except OSError as e:
            log.error('Path %s could not be accessed: %s' % (folder, e.strerror))
            return []
        for filepath in dir_files:
            entry = None
            try:
                filepath.exists()
            except UnicodeError:
                log.error('File %s not decodable with filesystem encoding' % filepath)
                continue
            if match(filepath):
                if filepath.isdir() and get_dirs:
                    entry = self.create_entry(filepath, test_mode, type='dir')
                elif filepath.islink() and get_symlinks:
                    entry = self.create_entry(filepath, test_mode, type='dir')
                elif filepath.isfile() and get_files:
                    entry = self.create_entry(filepath, test_mode)
                if entry:
                    entries.append(entry)

        return entries

    def get_entries_from_path(self, folder, match, recursion, recursion_depth, test_mode, get_files, get_dirs,
                              get_symlinks):
        if recursion:
            return self.get_entries_from_dir_recursively(folder, match, recursion_depth, test_mode, get_files, get_dirs,
                                                         get_symlinks)
        else:
            return self.get_entries_from_dir(folder, match, test_mode, get_files, get_dirs, get_symlinks)

    def on_task_input(self, task, config):
        config = self.prepare_config(config)
        entries = []

        test_mode = task.options.test
        match = re.compile(config['regexp'], re.IGNORECASE).match
        recursion = config['recursive']
        depth = config['recursion_depth']
        get_files = 'files' in config['retrieve']
        get_dirs = 'dirs' in config['retrieve']
        get_symlinks = 'symlinks' in config['retrieve']

        for folder in config['path']:
            folder = Path(folder).expanduser()
            log.debug('Scanning %s' % folder)
            entries = self.get_entries_from_path(folder, match, recursion, depth, test_mode, get_files, get_dirs,
                                                 get_symlinks)
        return entries


@event('plugin.register')
def register_plugin():
    plugin.register(InputFind, 'find', api_ver=2)
