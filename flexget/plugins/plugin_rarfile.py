from __future__ import unicode_literals, division, absolute_import
import logging
import os
import re

from flexget import plugin
from flexget.entry import Entry
from flexget.event import event
from flexget.utils.template import render_from_entry, RenderError

try:
    import rarfile
except ImportError:
    pass

log = logging.getLogger('rarfile')


class RarExtract(object):
    """
    Extracts files from RAR archives. By default this plugin will extract to the same directory as 
    the source archive, preserving directory structure from the archive.

    This plugin requires the unrar command line utility to extract compressed archives.

    Configuration:

    to:             Destination path; supports Jinja2 templating on the input entry. Fields such
                    as series_name must be populated prior to input into this plugin using
                    metainfo_series or similar. If no path is specified, RAR contents will be
                    extraced in the same directory as the RAR itself.
    keep_dirs:      [yes|no] (default: yes) Indicates whether to preserve the directory 
                    structure from within the RAR in the destination path.
    mask:           Shell-style file mask; any matching files will be extracted. When used, this
                    field will override regexp.
    regexp:         Regular expression pattern; any matching files will be extracted. Overriden
                    by mask if specified.
    unrar_tool:     Specifies the path of the unrar tool. Only necessary if its location is not
                    defined in the operating system's PATH environment variable.
    delete_rar:     [yes|no] (default: no) Delete this RAR after extraction is completed.


    Example:

      rar_extract:
        to: '/Volumes/External/TV/{{series_name}}/Season {{series_season}}/'
        keep_dirs: yes
        regexp: '.*s\d{1,2}e\d{1,2}.*\.mkv'
    """

    schema = {
        'anyOf': [
            {'type': 'boolean'},
            {
                'type': 'object',
                'properties': {
                    'to': {'type': 'string'},
                    'keep_dirs': {'type': 'boolean'},
                    'mask': {'type': 'string'},
                    'regexp': {'type': 'string', 'format': 'regex'},
                    'unrar_tool': {'type': 'string'},
                    'delete_rar': {'type': 'boolean'}
                },
                'additionalProperties': False
            }
        ]
    }


    def prepare_config(self, config):
        if not isinstance(config, dict):
            config = {}

        config.setdefault('to', '')
        config.setdefault('keep_dirs', True)
        config.setdefault('fail_entries', False)
        config.setdefault('unrar_tool', '')
        config.setdefault('delete_rar', False)

        # If mask was specified, turn it in to a regexp
        if 'mask' in config:
            config['regexp'] = translate(config['mask'])
        # If no mask or regexp specified, accept all files
        if 'regexp' not in config:
            config['regexp'] = '.'

        return config

    def handle_entry(self, entry, config):
        """
        Extract matching files into the directory specified

        Optionally delete the original RAR if config.delete_rar is True
        """

        match = re.compile(config['regexp'], re.IGNORECASE).match
        rar_path = entry['location']
        rar_dir = os.path.dirname(rar_path)
        rar_file = os.path.basename(rar_path)

        if not os.path.exists(rar_path):
            log.warn('File no longer exists: %s' % rar_path)
            return
        
        try:
            rar = rarfile.RarFile(rarfile=rar_path)
            log.debug('Successfully opened RAR: %s' % rar_path)
        except rarfile.RarWarning as e:
            log.warn('Nonfatal error: %s (%s)' % (rar_path, e))
        except rarfile.NeedFirstVolume:
            log.error('Not the first volume: %s' % rar_path)
            return
        except rarfile.NotRarFile:
            log.error('Not a RAR file: %s' % rar_path)
            return
        except Exception as e:
            log.error('Failed to open RAR: %s (%s)' (rar_path, e))
            entry.fail(e)
            return

        to = config['to']
        if to:
            try:
                to = render_from_entry(to, entry)
            except RenderError as e:
                log.error('Could not render path: %s' % to)
                entry.fail(e)
                return
        else:
            to = rar_dir

        for info in rar.infolist():
            path = info.filename
            filename = os.path.basename(path)


            if not match(path):
                log.debug('File did not match regexp: %s' % path)
                continue

            log.debug('Found matching file: %s' %path)

            
            if config['keep_dirs']:
                path_suffix = path
            else:
                path_suffix = filename
            destination = os.path.join(to, path_suffix)
            dest_dir = os.path.dirname(destination)

            if not os.path.exists(dest_dir):
                log.debug('Creating path: %s' % dest_dir)
                os.makedirs(dest_dir)

            if not os.path.exists(destination):
                log.debug('Attempting to extract: %s to %s' % (rar_file, dest_dir))
                try:
                    rar.extract(path, dest_dir)
                    log.verbose('Extracted: %s' % path )
                except Exception as e:
                    log.error('Failed to extract file: %s in %s (%s)' % (path, rar_path, e))

                    if os.path.exists(destination):
                        log.debug('Cleaning up partially extracted file: %s' % destination)
                        os.remove(destination)
                    continue
            else:
                log.verbose('File already exists: %s' % destination)

        if config['delete_rar']:
            volumes = rar.volumelist()
            rar.close()

            for volume in volumes:
                log.debug('Deleting volume: %s' % volume)
                os.remove(volume)

            log.verbose('Deleted RAR: %s' % rar_file)
        else:
            rar.close()

    def on_task_output(self, task, config):
        """Task handler for rar_extract"""
        if isinstance(config, bool) and not config:
            return

        # Slightly silly hack so dependency error only throws at execution time
        try:
            repr(rarfile)
        except:
            raise plugin.DependencyError(issued_by='rar_extract', 
                             missing='rarfile', 
                             message='rarfile plugin requires the rarfile Python\
                                      module.')


        config = self.prepare_config(config)

        # Set the path of the unrar tool if it's not specified in PATH
        unrar_tool = config['unrar_tool']
        if unrar_tool:
            rarfile.UNRAR_TOOL = unrar_tool
            log.debug('Set RarFile.unrar_tool to: %s' % unrar_tool)

        for entry in task.accepted:
            self.handle_entry(entry, config)     


@event('plugin.register')
def register_plugin():
    plugin.register(RarExtract, 'rar_extract', api_ver=2)
