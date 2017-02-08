from __future__ import unicode_literals, division, absolute_import
import logging
from flexget.utils.qualities import QualityComponent

log = logging.getLogger('utils.audio_qualities')

_sources = [
    QualityComponent('source', 10, 'radio'),
    QualityComponent('source', 20, 'webradio'),
    QualityComponent('source', 30, 'hdtv'),
    QualityComponent('source', 40, 'cd'),
    QualityComponent('source', 50, 'sacd')
]

_quantizers = [
    QualityComponent('signal', 10, 'PCM-16'),
    QualityComponent('signal', 20, 'PCM-20'),
    QualityComponent('signal', 30, 'PCM-24'),
    QualityComponent('signal', 40, 'PCM-32'),
    QualityComponent('signal', 50, 'DSD'),
]

_codecs = [
    QualityComponent('codec', 10, 'mp3'),
    QualityComponent('codec', 20, 'ogg'),
    QualityComponent('codec', 30, 'aac'),
    QualityComponent('codec', 90, 'flac')
]

class AudioStreamQuality:
    def __init__(self):
        self.source = None
        self.codec = None
        self.signal = None
