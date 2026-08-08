import json
import random
import time
import uuid
import zlib
from pathlib import Path

from flexget.utils.waf.crypto import encrypt


def encode_with_crc(obj):
    payload = json.dumps(obj, separators=(',', ':')).encode('utf-8')
    crc = zlib.crc32(payload) & 0xFFFFFFFF
    hex_crc = f'{crc:08x}'
    checksum = hex_crc.encode('ascii').upper()
    return checksum, checksum + b'#' + payload


gpus = json.loads(Path(__file__).with_name('webgl.json').read_text(encoding='utf-8'))


def get_fp(user_agent: str):
    ts = int(time.time() * 1000)
    gpu = random.choice(gpus)

    bins = [random.randrange(0, 40) for _ in range(256)]
    bins[0], bins[-1] = random.randrange(14473, 16573), random.randrange(14473, 16573)

    fp = {
        'metrics': {
            'fp2': 1,
            'browser': 0,
            'capabilities': 1,
            'gpu': 7,
            'dnt': 0,
            'math': 0,
            'screen': 0,
            'navigator': 0,
            'auto': 1,
            'stealth': 0,
            'subtle': 0,
            'canvas': 5,
            'formdetector': 1,
            'be': 0,
        },
        'start': ts,
        'flashVersion': None,
        'plugins': [
            {'name': 'PDF Viewer', 'str': 'PDF Viewer '},
            {'name': 'Chrome PDF Viewer', 'str': 'Chrome PDF Viewer '},
            {'name': 'Chromium PDF Viewer', 'str': 'Chromium PDF Viewer '},
            {'name': 'Microsoft Edge PDF Viewer', 'str': 'Microsoft Edge PDF Viewer '},
            {'name': 'WebKit built-in PDF', 'str': 'WebKit built-in PDF '},
        ],
        'dupedPlugins': 'PDF Viewer Chrome PDF Viewer Chromium PDF Viewer Microsoft Edge PDF Viewer WebKit built-in PDF ||1920-1080-1032-24-*-*-*',
        'screenInfo': '1920-1080-1032-24-*-*-*',
        'referrer': '',
        'userAgent': user_agent,
        'location': '',  # they probably don't check this
        'webDriver': False,
        'capabilities': {
            'css': {
                'textShadow': 1,
                'WebkitTextStroke': 1,
                'boxShadow': 1,
                'borderRadius': 1,
                'borderImage': 1,
                'opacity': 1,
                'transform': 1,
                'transition': 1,
            },
            'js': {
                'audio': True,
                'geolocation': random.choice([True, False]),
                'localStorage': 'supported',
                'touch': False,
                'video': True,
                'webWorker': random.choice([True, False]),
            },
            'elapsed': 1,
        },
        'gpu': {
            'vendor': gpu['webgl'][0]['webgl_unmasked_vendor'],
            'model': gpu['webgl_unmasked_renderer'],
            'extensions': gpu['webgl'][0]['webgl_extensions'].split(';'),
        },
        'dnt': None,
        'math': {
            'tan': '-1.4214488238747245',
            'sin': '0.8178819121159085',
            'cos': '-0.5753861119575491',
        },
        'automation': {
            'wd': {'properties': {'document': [], 'window': [], 'navigator': []}},
            'phantom': {'properties': {'window': []}},
        },
        'stealth': {'t1': 0, 't2': 0, 'i': 1, 'mte': 0, 'mtd': False},
        'crypto': {
            'crypto': 1,
            'subtle': 1,
            'encrypt': True,
            'decrypt': True,
            'wrapKey': True,
            'unwrapKey': True,
            'sign': True,
            'verify': True,
            'digest': True,
            'deriveBits': True,
            'deriveKey': True,
            'getRandomValues': True,
            'randomUUID': True,
        },
        'canvas': {
            'hash': random.randrange(645172295, 735192295),
            'emailHash': None,
            'histogramBins': bins,
        },
        'formDetected': False,
        'numForms': 0,
        'numFormElements': 0,
        'be': {'si': False},
        'end': ts + 1,
        'errors': [],
        'version': '2.4.0',
        'id': str(uuid.uuid4()),
    }
    checksum, data = encode_with_crc(fp)
    return checksum.decode(), encrypt(data)
