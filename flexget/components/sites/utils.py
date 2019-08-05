""" Common tools used by plugins implementing search plugin api

.. NOTE:: Try to avoid using or extending this file!

  We have normalizers in way too many places as is ...

"""
from __future__ import unicode_literals, division, absolute_import
from builtins import *  # noqa pylint: disable=unused-import, redefined-builtin

import re
from unicodedata import normalize


def normalize_unicode(text):
    if isinstance(text, str):
        # Convert to combined form for better search results
        return normalize('NFC', text)
    return text


def normalize_scene(text):
    """Normalize string according to scene standard.
    Mainly, it replace accented chars by their 'normal' couterparts
    and removes special chars.
    https://en.wikipedia.org/wiki/Standard_(warez)#Naming for more information
    """
    # Allowed chars in scene releases are:
    #     ABCDEFGHIJKLMNOPQRSTUVWXYZ
    #     abcdefghijklmnopqrstuvwxyz
    #     0123456789-._()
    text = normalize('NFKD', text).encode('ASCII', 'ignore').decode()
    return re.sub(
        r'[^a-zA-Z0-9 \-._()]', '', text.replace('...', '')
    )


def torrent_availability(seeds, leeches):
    """Returns a rating based on seeds and leeches for a given torrent.
    :param seeds: Number of seeds on the torrent
    :param leeches: Number of leeches on the torrent
    :return: A numeric rating
    """

    return seeds * 2 + leeches
