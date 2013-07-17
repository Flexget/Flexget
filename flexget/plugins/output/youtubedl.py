# -*- coding: utf-8 -*-

from __future__ import unicode_literals, division, absolute_import
from logging import getLogger
from flexget.plugin import register_plugin, PluginError

import subprocess
import sys

log = getLogger('youtubedl')


class PluginYoutubeDl(object):
    """
    Uses Youtube-Dl to download embedded videos from over over 70 different hosters

    Example::

      youtubedl:
        quiet: no
        output_template: '%(title)s ____BY____ %(uploader)s.%(ext)s'
        restrict_filenames: yes
        write:
          - thumbnail
          - info-json
          - description
          - sub
          - auto-sub
        extract_audio: yes
        audio_format: best
        audio_quality: '3'
        keep_video: yes

    Default values for the config elements::

      youtubedl:
        username:
        password:
        video_password:
        user_agent: 'Mozilla/5.0 (Windows NT 6.1; rv:22.0) Gecko/20130405 Firefox/22.0'
        referer: http://www.google.com
        output_template: '(%uploader)s - (%title)s - (%id)s.(%ext)s'
        restrict_filenames: no
        quiet: yes
        extract_audio: no
        keep_video: no
    """

    __author__ = 'http://rg3.github.io/youtube-dl/'
    __version__ = '0.4'

    schema = {
        'oneOf': [
            {'type': 'boolean'},
            {
                'type': 'object',
                'properties': {
                    'quiet': {'type': 'boolean'},
                    'restrict_filenames': {'type': 'boolean'},
                    'extract_audio': {'type': 'boolean'},
                    'keep_video': {'type': 'boolean'},
                    'username': {'type': 'string'},
                    'password': {'type': 'string'},
                    'video_password': {'type': 'string'},
                    'user_agent': {'type': 'string'},
                    'referer': {'type': 'string'},
                    'output_template': {'type': 'string'},
                    'write': 
                    {
                        'type': 'array',
                        'items': {'type': 'string'}
                    },
                    'audio_format': {'type': 'string'},
                    'audio_quality': {'type': 'string'},
                    'allow_background': {'type': 'boolean'}
                },
                'additionalProperties': False
            }
        ]
    }

    def prepare_config(self, config):
        if isinstance(config, bool) and config:
            config = {}
        
        config.setdefault('user_agent', 'Mozilla/5.0 (Windows NT 6.1; rv:22.0) Gecko/20130405 Firefox/22.0')
        config.setdefault('referer', 'http://www.google.com')
        config.setdefault('output_template', '%(uploader)s - %(title)s - %(id)s.%(ext)s')
        config.setdefault('restrict_filenames', False)
        config.setdefault('quiet', False)
        config.setdefault('extract_audio', False)
        config.setdefault('keep_video', False)
        config.setdefault('username', '')
        config.setdefault('password', '')
        config.setdefault('video_password', '')
        config.setdefault('write', [])
        config.setdefault('keep_video', False)
        config.setdefault('allow_background', False)
   
        return config

    def on_task_output(self, task, config):
        if not task.accepted:
            return

        config = self.prepare_config(config)
        self.download_entries(task, config)        

    def download_entries(self, task, config):
        """Downloads the accepted entries"""

        for entry in task.accepted:
            try:
                self.download_entry(entry, config)
            except PluginError:
                raise
            except Exception as e:
                raise PluginError('Unknown error: %s' % str(e), log)

    def download_entry(self, entry, config):
        if 'path' in entry.task.config['set']:
            config['path'] = entry.task.config['set'].get('path', '') # TODO this might fail in the future
        else:
            config['path'] = ''

        # TODO this whole thing is ugly, maybe something like "for (index, item) in enumerate(config)"?
        auth = '--video-password "%s"' % (config['video_password']) if (config['video_password']) else ''

        # we need both username and password, otherwise youtube-dl will ask at STDIN
        # also the defaults are empty strings, so we can't just add it all together
        username = config['username']
        password = config['password']
        auth += ' --username "%s" --password "%s"' % (username, password) if (username and password) else ''

        general = ' --user-agent "%(user_agent)s" --referer "%(referer)s" -o "%(path)s%(output_template)s"' % config

        bools = ' --restrict-filenames' if (config['restrict_filenames']) else ''
        bools += ' --quiet' if (config['quiet']) else ''
        bools += ' --extract-audio' if (config['extract_audio']) else ''
        bools += ' --keep-video' if (config['keep_video']) else ''
        
        if(config['extract_audio']):
            audio = ' --audio-format "%s"' % (config['audio_format']) if (config['audio_format']) else ''
            audio += ' --audio-quality "%s"' % (config['audio_quality']) if (config['audio_quality']) else ''

        extras = ' --write-' + ' --write-'.join(config['write']) if config['write'] else ''

        url = '"%s"' % (entry['url'])

        cmd = ' '.join(['youtube-dl', auth, general, bools, audio, extras, url])
                
        if entry.task.manager.options.test:
            log.info('Would start youtubedl with "%s"', cmd)
            return
        
        log.debug('Starting Youtube-Dl with "%s"', cmd)

        # from exec plugin
        proc = subprocess.Popen(cmd.encode(sys.getfilesystemencoding()), 
                             shell=True, stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                             stderr=subprocess.STDOUT, close_fds=False)
        
        if not config['allow_background']:
            (read, write) = (proc.stdout, proc.stdin)
            response = read.read()
            read.close()
            write.close()
            if response:
                log.info('YoutubeDl Stdout: %s', response)

        return proc.wait()
        

register_plugin(PluginYoutubeDl, 'youtubedl', api_ver=2)
