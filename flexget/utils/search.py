""" Common tools used by plugins implementing search plugin api """
from __future__ import unicode_literals, division, absolute_import
import re
from difflib import SequenceMatcher
from unicodedata import normalize
from flexget.utils.titles.parser import TitleParser
from flexget.utils.titles.movie import MovieParser
from flexget.utils import qualities


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


class AnyComparator(object):
    """Comparator that does no comparison. Used to return all results from a search plugin without filtering."""

    def __init__(self):
        self.a = ''
        self.b = ''

    def ratio(self):
        return 1.0

    def set_seq1(self, a):
        self.a = a

    def set_seq2(self, b):
        self.b = b

    def matches(self, other=None):
        return True

    def search_string(self):
        """Return a cleaned string based on seq1 that can be used for searching."""

        if isinstance(self.a, unicode):
            # Convert to combined form for better search results
            return normalize('NFC', self.a)
        return self.a


class StringComparator(SequenceMatcher, object):
    """Compares two strings for similarity. Runs a cleaner function on strings before comparison.
    Cutoff similarity is configurable."""

    def __init__(self, cutoff=0.9, cleaner=clean_symbols):
        """
        :param cutoff: Minimum similarity to be considered a match.
        :param cleaner: Cleaning function to pass strings through before comparison.
        """
        self.cutoff = cutoff
        self.cleaner = cleaner
        SequenceMatcher.__init__(self)

    def set_seq1(self, a):
        """Set first string for comparison."""
        SequenceMatcher.set_seq1(self, self.cleaner(a))

    def set_seq2(self, b):
        """Set second string for comparison."""
        SequenceMatcher.set_seq2(self, self.cleaner(b))

    def matches(self, other=None):
        """Compare the two strings, return True if match is close enough.

        :param other: String to compare against. If not specified, last specified string will be used.
        :return: True if match is close enough.
        """
        if other is not None:
            self.set_seq2(other)
        return self.ratio() > self.cutoff

    def search_string(self):
        """Return a cleaned string based on seq1 that can be used for searching."""

        if isinstance(self.a, unicode):
            # Convert to combined form for better search results
            return normalize('NFC', self.a)
        return self.a


class MovieComparator(StringComparator):
    """Compares two strings for similarity based on extracted movie title, year and quality."""

    def __init__(self):
        self.a_year, self.b_year = None, None
        self.a_quality, self.b_quality = qualities.Quality(), qualities.Quality()
        self.parser = MovieParser()
        super(MovieComparator, self).__init__(cutoff=0.9)

    def set_seq1(self, a):
        """Set first string for comparison."""
        self.parser.parse(a)
        super(MovieComparator, self).set_seq1(self.parser.name)
        self.a_year = self.parser.year
        self.a_quality = self.parser.quality

    def set_seq2(self, b):
        """Set second string for comparison."""
        self.parser.parse(b)
        super(MovieComparator, self).set_seq2(self.parser.name)
        self.b_year = self.parser.year
        self.b_quality = self.parser.quality

    def matches(self, other=None):
        """Compare the two strings, return True if they appear to be the same movie.

        :param other: String to compare against. If not specified, last specified string will be used.
        :return: True if match is close enough.
        """
        result = super(MovieComparator, self).matches(other)
        if self.a_quality:
            if self.a_quality != self.b_quality:
                return False
        if self.a_year and self.b_year:
            if self.a_year != self.b_year:
                # TODO: Make this fuzzier? tmdb and imdb years do not always match
                return False
        return result

    def search_string(self):
        """Return a cleaned string based on seq1 that can be used for searching."""
        result = self.a
        if isinstance(result, unicode):
            # Convert to combined form for better search results
            result = normalize('NFC', result)
        if self.a_year:
            result += ' %s' % self.a_year
        if self.a_quality:
            # Shorten some quality strings in search because of multiple acceptable forms
            if '720p' in self.a_quality.name:
                result += ' 720p'
            elif '1080p' in self.a_quality.name:
                result += ' 1080p'
            else:
                result += ' %s' % self.a_quality
        return result


def torrent_availability(seeds, leeches):
    """Returns a rating based on seeds and leeches for a given torrent.

    :param seeds: Number of seeds on the torrent
    :param leeches: Number of leeches on the torrent
    :return: A numeric rating
    """

    return seeds * 2 + leeches
