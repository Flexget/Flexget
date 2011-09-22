""" Common tools used by plugins implementing search plugin api """
import re
from difflib import SequenceMatcher
from flexget.utils.titles.parser import TitleParser


def clean_title(title):
    """Removes common codec, sound keywords, and special characters info from titles to facilitate
    loose title comparison.
    """
    result = title.lower()
    result = TitleParser.remove_words(result, TitleParser.sounds + TitleParser.codecs)
    result = re.sub('[ \(\)\-_\[\]\.]+', ' ', result)
    return result


def loose_comparator(title):
    """Create a SequenceMatcher instance with compare_with method for loose matching."""
    sm = SequenceMatcher(a=clean_title(title))

    def compare_with(other):
        sm.set_seq2(clean_title(other))
        return sm.ratio()
    sm.compare_with = compare_with
    return sm


def exact_comparator(title):
    """Create a SequenceMatcher instance with compare_with method for more exact matching."""
    sm = SequenceMatcher(a=title)

    def compare_with(other):
        sm.set_seq2(other)
        return sm.ratio()
    sm.compare_with = compare_with
    return sm


def torrent_availability(seeds, leeches):
    """Returns a rating based on seeds and leeches for a given torrent.

    :param seeds: Number of seeds on the torrent
    :param leeches: Number of leeches on the torrent
    :return: A numeric rating
    """
    
    return seeds * 2 + leeches
