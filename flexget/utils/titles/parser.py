import re


class ParseWarning(Warning):

    def __init__(self, value, **kwargs):
        self.value = value
        self.kwargs = kwargs


class TitleParser(object):

    propers = ['proper', 'repack', 'rerip', 'real', 'final']

    specials = ['special']

    editions = ['dc', 'extended', 'uncut', 'remastered', 'unrated', 'theatrical', 'chrono', 'se']

    cutoffs = ['limited', 'xvid', 'h264', 'x264', 'h.264', 'x.264', 'screener', 'unrated', '3d', 'extended',
               'directors', 'multisubs'] + propers + specials + editions

    remove = ['imax']

    codecs = ['x264', 'x.264', 'h264', 'h.264', 'XViD']

    sounds = ['AC3', 'DD5.1', 'DTS']

    @staticmethod
    def re_not_in_word(regexp):
        return r'(?<![^\W_])' + regexp + r'(?![^\W_])'

    def strip_spaces(self, text):
        """Removes all unnecessary duplicate spaces from a text"""
        return ' '.join(text.split())

    def remove_words(self, text, words, not_in_word=False):
        """Clean all given :words: from :text: case insensitively"""
        for word in words:
            text = self.ireplace(text, word, '', not_in_word=not_in_word)
        # remove duplicate spaces
        text = ' '.join(text.split())
        return text

    def ireplace(self, data, old, new, count=0, not_in_word=False):
        """Case insensitive string replace"""
        old = re.escape(old)
        if not_in_word:
            old = self.re_not_in_word(old)
        pattern = re.compile(old, re.I)
        return re.sub(pattern, new, data, count)
