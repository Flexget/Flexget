from __future__ import unicode_literals, division, absolute_import
from flexget.plugin import DependencyError

try:
    import youtube_dl
except ImportError:
    raise DependencyError(issued_by='youtubedl', missing='ext lib `youtube_dl`', silent=True)

from flexget.plugin import register_plugin, PluginError
from logging import getLogger
import os

log = getLogger('youtubedl')


class PluginYoutubeDl(object):
    """
    Uses Youtube-Dl to download embedded videos from over 70 different hosters

    Example::

      youtubedl:
        quiet: no
        output_template: '%(title)s by %(uploader)s.%(ext)s'
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
    """

    __author__ = 'http://rg3.github.io/youtube-dl/'
    __version__ = '0.5'

    # based on commit 085bea451346956aaa0d981fe5b413aaec49e63f/youtube_dl/__init__.py
    schema = {
        'oneOf': [
            {'type': 'string', 
             'format': 'path', 
             'title': 'download path', 
             'description': 'save downloaded files using the default naming scheme: "/path/%id.%ext"'},
            {
                'type': 'object',
                'properties': {
                    'ignore-errors': {'type': 'boolean', 
                                      'default': False,
                                      'description': 'continue on download errors'},
                    'user-agent': {'type': 'string',
                                   'description': 'specify a custom user agent'},
                    'referer': {'type': 'string',
                                'default': '',
                                'description': ('specify a custom referer, use if the video'
                                                'access is restricted to one domain')},
                    'proxy': {'type': 'string',
                              'default': '',
                              'description': 'Use the specified HTTP/HTTPS proxy'},
                    'no-check-certificate': {'type': 'boolean',
                                             'default': False,
                                             'description': 'Suppress HTTPS certificate validation.'},
                    'playlist-start': {'type': 'integer', 
                                       'description': 'playlist video to start at (default is 1)',
                                       'default': 1},
                    'playlist-end': {'type': 'integer',
                                     'description': 'playlist video to end at (default is last)',
                                     'default': -1},
                    'match-title': {'type': 'string',
                                    'format': 'regex', 
                                    'description': 'download only matching titles (regex or caseless sub-string)'},
                    'reject-title': {'type': 'string',
                                     'format': 'regex', 
                                     'description': ('skip download for matching titles '
                                                     '(regex or caseless sub-string)')},
                    'max-downloads': {'type': 'integer', 
                                      'description': 'Abort after downloading NUMBER files'},
                    'min-filesize': {'type': 'string',
                                     'description': "Do not download any videos smaller than SIZE (e.g. 50k or 44.6m)",
                                     'default': ''},
                    'max-filesize': {'type': 'string',
                                     'description': "Do not download any videos larger than SIZE (e.g. 50k or 44.6m)",
                                     'default': ''},
                    'date': {'type': 'string',
                             'description': 'download only videos uploaded in this date',
                             'default': ''},
                    'datebefore': {'type': 'string',
                                   'description': 'download only videos uploaded before this date',
                                   'default': ''},
                    'dateafter': {'type': 'string',
                                  'description': 'download only videos uploaded after this date',
                                  'default': ''},
                    'username': {'type': 'string', 
                                 'description': 'account username'},
                    'password': {'type': 'string', 
                                 'description': 'account password'},
                    'usenetrc': {'type': 'boolean',
                                 'description': 'use .netrc authentication data',
                                 'default': False},
                    'video-password': {'type': 'string', 
                                       'description': 'video password (vimeo only)'},
                    'format': {'type': 'string', 
                               'description': ('video format code, specifiy the order of preference using'
                                               'slashes: "-f 22/17/18". "-f mp4" and "-f flv" are also supported.'
                                               ' Set to "all" to download all available formats.')},
                    'prefer-free-formats': {'type': 'boolean',
                                            'description': ('prefer free video formats '
                                                            'unless a specific one is requested'),
                                            'default': False},
                    'max-quality': {'type': 'string', 
                                    'description': 'highest quality format to download'},
                    'write-sub': {'type': 'boolean',
                                  'description': 'write subtitle file (currently youtube only)',
                                  'default': False},
                    'write-auto-sub': {'type': 'boolean',
                                       'description': 'write automatic subtitle file (currently youtube only)',
                                       'default': False},
                    'all-subs': {'type': 'boolean',
                                 'description': 'downloads all the available subtitles of the video',
                                 'default': False},
                    'sub-format': {'type': 'string',
                                   'description': 'subtitle format (default is srt) ([sbv/vtt] youtube only)',
                                   'default': 'srt'},
                    'sub-lang': {'type': 'string',
                                 'description': ('languages of the subtitles to download (optional), '
                                                 'use IETF language tags like \'en\' or \'pt\'')},
                    'rate-limit': {'type': 'string',
                                   'description': 'maximum download rate (e.g. 50k or 44.6m)'},
                    'retries': {'type': 'integer',
                                'description': 'number of retries (default is 10)',
                                'default': 10},
                    'buffer-size': {'type': 'string',
                                    'description': 'size of download buffer (e.g. 1024 or 16k) (default is 1024)',
                                    'default': "1024"},
                    'no-resize-buffer': {'type': 'boolean',
                                         'description': ('do not automatically adjust the buffer size. By default, '
                                         'the buffer size is automatically resized from an initial value of SIZE.'),
                                         'default': False},
                    # debug stuff
                    'quiet': {'type': 'boolean', 
                              'description': 'activates quiet mode', 
                              'default': False},
                    'simulate': {'type': 'boolean', 
                                 'description': 'do not download the video and do not write anything to disk',
                                 'default': False},
                    'skip-download': {'type': 'boolean',
                                      'description': 'do not download the video',
                                      'default': False},
                    'get-url': {'type': 'boolean',
                                'description': 'simulate, quiet but print URL',
                                'default': False},
                    'get-title': {'type': 'boolean',
                                  'description': 'simulate, quiet but print title',
                                  'default': False},
                    'get-id': {'type': 'boolean',
                               'description': 'simulate, quiet but print id',
                               'default': False},
                    'get-thumbnail': {'type': 'boolean',
                                      'description': 'simulate, quiet but print thumbnail URL',
                                      'default': False},
                    'get-description': {'type': 'boolean',
                                        'description': 'simulate, quiet but print video description',
                                        'default': False},
                    'get-filename': {'type': 'boolean',
                                     'description': 'simulate, quiet but print output filename',
                                     'default': False},
                    'get-format': {'type': 'boolean',
                                   'description': 'simulate, quiet but print output format',
                                   'default': False},
                    # end debug stuff
                    'newline': {'type': 'boolean', 
                                'description': 'output progress bar as new lines', 
                                'default': False},
                    'no-progress': {'type': 'boolean', 
                                    'description': 'do not print progress bar',
                                    'default': False},
                    'verbose': {'type': 'boolean',
                                'description': 'print various debugging information',
                                'default': False},
                    'dump-intermediate-pages': {'type': 'boolean',
                                                'description': ('print downloaded pages to '
                                                                'debug problems(very verbose)'),
                                                'default': False},
                    'title': {'type': 'boolean',
                              'description': 'use title in file name (default)',
                              'default': False},
                    'id': {'type': 'boolean', 
                           'description': 'use only video ID in file name',
                           'default': False},
                    'auto-number': {'type': 'boolean',
                                    'description': 'number downloaded files starting from 00000', 
                                    'default': False},
                    'output': {'type': 'string',
                               'description': ('output filename template. Use %(title)s to get the title, '
                                  '%(uploader)s for the uploader name, '
                                  '%(uploader_id)s for the uploader nickname if different, '
                                  '%(autonumber)s to get an automatically incremented number, '
                                  '%(ext)s for the filename extension, '
                                  '%(upload_date)s for the upload date (YYYYMMDD), '
                                  '%(extractor)s for the provider (youtube, metacafe, etc), '
                                  '%(id)s for the video id , %(playlist)s for the playlist the video is in, '
                                  '%(playlist_index)s for the position in the playlist and %% for a literal percent. '
                                  'Use - to output to stdout. Can also be used to download to a different directory, '
                                  'for example with -o \'/my/downloads/%(uploader)s/%(title)s-%(id)s.%(ext)s\' .')},
                    'autonumber-size': {'type': 'integer',
                                        'description': ('Specifies the number of digits in %(autonumber)s '
                                                        'when it is present in output filename template '
                                                        'or --autonumber option is given')},
                    'restrict-filenames': {'type': 'boolean', 
                                           'description': ('Restrict filenames to only ASCII characters, and avoid '
                                                           '"&" and spaces in filenames'),
                                           'default': False},
                    'batch-file': {'type': 'string',
                                   'format': 'file',
                                   'description': 'file containing URLs to download'},
                    'no-overwrites': {'type': 'boolean',
                                      'description': 'do not overwrite files',
                                      'default': False},
                    'continue': {'type': 'boolean',
                                 'description': 'resume partially downloaded files',
                                 'default': True},
                    'cookies': {'type': 'string',
                                'description': 'file to read cookies from and dump cookie jar in'},
                    'no-part': {'type': 'boolean',
                                'description': 'do not use .part files', 
                                'default': False},
                    'no-mtime': {'type': 'boolean', 
                                 'description': ('do not use the Last-modified header '
                                                 'to set the file modification time'),
                                 'default': True},
                    'write-description': {'type': 'boolean', 
                                          'description': 'write video description to a .description file',
                                          'default': False},
                    'write-info-json': {'type': 'boolean', 
                                        'description': 'write video metadata to a .info.json file',
                                        'default': False},
                    'write-thumbnail': {'type': 'boolean',
                                        'description': 'write thumbnail image to disk', 
                                        'default': False},
                    'extract-audio': {'type': 'boolean',
                                      'default': False,
                                      'description': ('convert video files to audio-only files '
                                                      '(requires ffmpeg or avconv and ffprobe or avprobe)')},
                    'audio-format': {'type': 'string',
                                     'default': 'best',
                                     'description': ('"best", "aac", "vorbis", "mp3", "m4a", "opus", or "wav"; '
                                                     'best by default')},
                    'audio-quality': {'type': 'string',
                                      'default': '5',
                                      'description': ('ffmpeg/avconv audio quality specification, '
                                                      'insert a value between 0 (better) and 9 (worse) for VBR '
                                                      'or a specific bitrate like 128K (default 5)')},
                    'recode-video': {'type': 'string',
                                     'default': '',
                                     'description': ('Encode the video to another format if necessary '
                                                     '(currently supported: mp4|flv|ogg|webm)')},
                    'keep-video': {'type': 'boolean', 
                                   'description': ('keeps the video file on disk after the post-processing; '
                                                   'the video is erased by default'), 'default': False},
                    'no-post-overwrites': {'type': 'boolean',
                                           'description': ('do not overwrite post-processed files; the post-processed '
                                                           'files are overwritten by default'), 'default': False},
                    'embed-subs': {'type': 'boolean', 
                                   'default': False,
                                   'description': 'embed subtitles in the video (only for mp4 videos)'}
                },
                'additionalProperties': False
            }
        ]
    }

    def prepare_config(self, config):
        if isinstance(config, basestring) and config:
            config = {'ytdl-config': ['--output', os.path.join(config, '%(id)s.%(ext)s')]}
        elif isinstance(config, dict):
            ytdl_config = []
            for key, value in config.iteritems():
                if not value:
                    continue

                ytdl_config.append('--' + key)
                if not isinstance(value, bool):
                    ytdl_config.append(str(value))
            config['ytdl-config'] = ytdl_config

        return config

    def on_task_output(self, task, config):
        if not task.accepted:
            return

        config = self.prepare_config(config)

        self.download_entries(task, config)

    def download_entries(self, task, config):
        """Downloads the accepted entries
        
        Raises:
            PluginError
        """
        
        for entry in task.accepted:
            try:
                self.download_entry(entry, config)
            except PluginError:
                raise
            except Exception as e:
                raise PluginError('Unknown error: %s' % str(e), log)

    def download_entry(self, entry, config):
        """Calls Youtube-Dl with new config and fails the entry on error

        Raises:
            PluginError if operation fails
        """

        # video URLs have to be the last items in the list
        entry_config = list(config['ytdl-config'])
        entry_config.append(entry['url'])

        if entry.task.manager.options.test:
            log.info('Would start Youtube-Dl with "%s"', entry_config)
            return

        log.debug('Starting Youtube-Dl with "%s"', entry_config)
        
        try:
            youtube_dl.main(entry_config)
        except SystemExit as e:
            if e.code != 0:
                entry.fail('Youtube-Dl returned error code: %s' % str(e))
        except Exception as e:
            raise PluginError('Unknown error: %s' % str(e), log)

        return
                    

register_plugin(PluginYoutubeDl, 'youtubedl', api_ver=2)
