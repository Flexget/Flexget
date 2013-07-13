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

from pprint import pprint

log = getLogger('youtubedl')


class PluginYoutubeDl(object):
    """
    Uses Youtube-Dl to download embedded videos from over over 70 different hosters

    Example::

      youtubedl:
        quiet: no
        enabled: yes
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
        enabled: yes
        user_agent: 'Mozilla/5.0 (Windows NT 6.1; rv:22.0) Gecko/20130405 Firefox/22.0'
        referer: http://www.google.com
        output_template: '(%uploader)s - (%title)s - (%id)s.(%ext)s'
        restrict_filenames: no
        quiet: yes
        extract_audio: no
        keep_video: no
    """

    __author__ = 'http://rg3.github.io/youtube-dl/'
    __version__ = '0.1'

    DEFAULT_USER_AGENT = 'Mozilla/5.0 (Windows NT 6.1; rv:22.0) Gecko/20130405 Firefox/22.0'
    DEFAULT_REFERER = 'http://www.google.com'
    DEFAULT_OUTPUT_TEMPLATE = '%(uploader)s - %(title)s - %(id)s.%(ext)s'
    DEFAULT_RESTRICT_FILENAMES = False
    DEFAULT_WRITE = []
    DEFAULT_QUIET = True
    DEFAULT_EXTRACT_AUDIO = False
    DEFAULT_KEEP_VIDEO = False
    DEFAULT_USERNAME = ''
    DEFAULT_PASSWORD = ''
    DEFAULT_VIDEO_PASSWORD = ''

    def validator(self):
        """Return config validator"""
        root = validator.factory()
        root.accept('boolean')
        config = root.accept('dict')
        #Auth stuff
        config.accept('text', key='video_password')
        config.accept('text', key='username')
        config.accept('text', key='password')
        #Basics
        config.accept('boolean', key='enabled')
        config.accept('text', key='user_agent')
        config.accept('text', key='referer')
        config.accept('text', key='output_template')
        config.accept('boolean', key='restrict_filenames')
        config.accept('boolean', key='quiet')
        config.accept('list', key='write').accept('text')
        #Audio
        config.accept('boolean', key='extract_audio')
        config.accept('boolean', key='keep_video')
        config.accept('text', key='audio_format')
        config.accept('text', key='audio_quality')
        return config

    def on_task_output(self, task, config):
        if not config.get('enabled', True):
            return
        if not task.accepted:
            return
        import IPython
        IPython.embed()
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
        username = config.get('username', self.DEFAULT_USERNAME)
        password = config.get('password', self.DEFAULT_PASSWORD)
        video_password = config.get('video_password', self.DEFAULT_VIDEO_PASSWORD)
        
        user_agent = config.get('user_agent', self.DEFAULT_USER_AGENT)
        referer = config.get('referer', self.DEFAULT_REFERER)
        output_template = config.get('output_template', self.DEFAULT_OUTPUT_TEMPLATE)
        restrict_filenames = config.get('restrict_filenames', self.DEFAULT_RESTRICT_FILENAMES)
        quiet = config.get('quiet', self.DEFAULT_QUIET)
        write = config.get('write', self.DEFAULT_WRITE)
        
        extract_audio = config.get('extract_audio', self.DEFAULT_EXTRACT_AUDIO)
        keep_video = config.get('keep_video', self.DEFAULT_KEEP_VIDEO)
        audio_format = config.get('audio_format', '')
        audio_quality = config.get('audio_quality', '')

        path = ''
        if 'set' in entry.task.config:
            path = entry.task.config['set'].get('path', '')

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
