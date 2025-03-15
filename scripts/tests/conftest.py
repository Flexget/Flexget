import os
from http import client
from pathlib import Path

import pytest
from vcr import VCR
from vcr.stubs import VCRHTTPConnection, VCRHTTPSConnection

VCR_CASSETTE_DIR = Path(__file__).parent / 'cassettes'
VCR_RECORD_MODE = os.environ.get('VCR_RECORD_MODE', 'once')

vcr = VCR(
    cassette_library_dir=str(VCR_CASSETTE_DIR),
    record_mode=VCR_RECORD_MODE,
    custom_patches=(
        (client, 'HTTPSConnection', VCRHTTPSConnection),
        (client, 'HTTPConnection', VCRHTTPConnection),
    ),
)


@pytest.fixture
def online(request, monkeypatch):
    """Be applied automatically to any test using the `online` mark.

    It will record and playback network sessions using VCR.

    The record mode of VCR can be set using the VCR_RECORD_MODE environment variable when running tests.
    """
    if VCR_RECORD_MODE == 'off':
        yield None
    else:
        module = request.module.__name__.split('tests.')[-1]
        class_name = request.cls.__name__
        cassette_name = f'{module}.{class_name}.{request.function.__name__}'
        cassette_path = VCR_CASSETTE_DIR / cassette_name
        with vcr.use_cassette(path=str(cassette_path)) as cassette:
            yield cassette
