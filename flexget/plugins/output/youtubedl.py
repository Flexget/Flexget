# -*- coding: utf-8 -*-

from __future__ import unicode_literals, division, absolute_import
from urllib import urlencode, quote
from urllib2 import urlopen, URLError, HTTPError
from logging import getLogger
from flexget.utils import json
from flexget.plugin import register_plugin, PluginError
from flexget import validator

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
    __version__ = '0.2'

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
                    'keep_video': {'type': 'boolean'}
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
            except URLError:
                raise PluginError('Invalid URL', log)
            except PluginError:
                raise
            except Exception as e:
                raise PluginError('Unknown error: %s' % str(e), log)

    def download_entry(self, entry, config):
        username = config['username']
        password = config['password']
        video_password = config['video_password']
        
        user_agent = config['user_agent']
        referer = config['referer']
        output_template = config['output_template']
        restrict_filenames = config['restrict_filenames']
        quiet = config['quiet']
        write = config['write']
        
        extract_audio = config['extract_audio']
        keep_video = config['keep_video']
        audio_format = config['audio_format']
        audio_quality = config['audio_quality']

        path = ''
        if 'set' in entry.task.config:
            path = entry.task.config['set'].get('path', '') # TODO this might fail in the future, needs a test

        # TODO this is ugly
        # we need both username and password, otherwise youtube-dl will ask at STDIN
        # also the defaults are empty strings, so we can't just add it all together
        auth1 = '--video-password "%s"' % (video_password) if (video_password) else ''
        auth2 = '--username "%s" --password "%s"' % (username, password) if (username and password) else ''

        general = '--user-agent "%(user_agent)s" --referer "%(referer)s" -o "%(path)s%(output_template)s"' % locals()

        bools1 = '--restrict-filenames' if (restrict_filenames) else ''
        bools2 = '--quiet' if (quiet) else ''
        bools3 = '--extract-audio' if (extract_audio) else ''
        bools4 = '--keep-video' if (keep_video) else ''
        
        if(extract_audio):
            audio1 = '--audio-format "%s"' % (audio_format) if (audio_format) else ''
            audio2 = '--audio-quality "%s"' % (audio_quality) if (audio_quality) else ''

        extras = ' --write-' + ' --write-'.join(write) if write else ''

        url = '"%s"' % (entry['url'])

        args = ' '.join([auth1, auth2, general, bools1, bools2, bools3, bools4, audio1, audio2, extras, url])
        
        cmd = 'youtube-dl %s' % (args)
                
        if entry.task.manager.options.test:
            log.info('Would start youtubedl with "%s"' % cmd)
            return
        
        log.debug('Starting Youtube-Dl with "%s"' % cmd)

        # 'borrowed' from exec plugin
        p = subprocess.Popen(cmd.encode(sys.getfilesystemencoding()), 
                             shell=True, stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                             stderr=subprocess.STDOUT, close_fds=False)
        
        # TODO allow background
        (r, w) = (p.stdout, p.stdin)
        response = r.read()
        r.close()
        w.close()
        if response:
            log.info('YoutubeDl Stdout: %s' % response)
        return p.wait()
        

register_plugin(PluginYoutubeDl, 'youtubedl', api_ver=2)
