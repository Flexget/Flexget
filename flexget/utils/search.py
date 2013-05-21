""" Common tools used by plugins implementing search plugin api """
from __future__ import unicode_literals, division, absolute_import
import re
from unicodedata import normalize

from flexget.utils.titles.parser import TitleParser


def clean_symbols(text):
    """Replaces common symbols with spaces. Also normalize unicode strings in decomposed form."""
    result = text
    if isinstance(result, unicode):
        result = normalize('NFKD', result)
    return re.sub('[ \(\)\-_\[\]\.]+', ' ', result).lower()


def clean_title(title):
    """Removes common codec, sound keywords, and special characters info from titles to facilitate
    loose title comparison.
    """
    result = TitleParser.remove_words(title, TitleParser.sounds + TitleParser.codecs)
    result = clean_symbols(result)
    return result


def normalize_unicode(text):
    if isinstance(text, unicode):
        # Convert to combined form for better search results
        return normalize('NFC', text)
    return text


def torrent_availability(seeds, leeches):
    """Returns a rating based on seeds and leeches for a given torrent.

    :param seeds: Number of seeds on the torrent
    :param leeches: Number of leeches on the torrent
    :return: A numeric rating
    """

    return seeds * 2 + leeches
