from __future__ import unicode_literals, division, absolute_import
import re


class TitleParser(object):

    propers = ['proper', 'repack', 'rerip', 'real', 'final']

    specials = ['special', 'bonus', 'extra', 'omake', 'ova']

    editions = ['dc', 'extended', 'uncut', 'remastered', 'unrated', 'theatrical', 'chrono', 'se']

    # TODO: All of the quality related keywords can probably be removed from here, as the quality module handles them
    codecs = ['x264', 'x.264', 'h264', 'h.264', 'XViD']

    # lowercase required
    cutoffs = ['limited', 'xvid', 'h264', 'x264', 'h.264', 'x.264', 'screener', 'unrated', '3d', 'extended',
               'directors', 'director\'s', 'multisubs', 'dubbed', 'subbed', 'multi'] + propers + specials + editions

    remove = ['imax']

    sounds = ['AC3', 'DD5.1', 'DTS']

    @staticmethod
    def re_not_in_word(regexp):
        return r'(?<![^\W_])' + regexp + r'(?![^\W_])'

    @staticmethod
    def strip_spaces(text):
        """Removes all unnecessary duplicate spaces from a text"""
        return ' '.join(text.split())

    @staticmethod
    def remove_words(text, words, not_in_word=False):
        """Clean all given :words: from :text: case insensitively"""
        for word in words:
            text = TitleParser.ireplace(text, word, '', not_in_word=not_in_word)
        # remove duplicate spaces
        text = ' '.join(text.split())
        return text

    @staticmethod
    def ireplace(data, old, new, count=0, not_in_word=False):
        """Case insensitive string replace"""
        old = re.escape(old)
        if not_in_word:
            old = TitleParser.re_not_in_word(old)
        pattern = re.compile(old, re.I)
        return re.sub(pattern, new, data, count)
