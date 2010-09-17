import re
from flexget.utils import qualities


class ParseWarning(Warning):

    def __init__(self, value, **kwargs):
        self.value = value
        self.kwargs = kwargs

        
class TitleParser(object):

    propers = ['proper', 'repack', 'rerip', 'real']
    
    specials = ['special']
    
    cutoffs = ['limited', 'xvid', 'h264', 'x264', 'h.264', 'x.264', 'screener', 'unrated', '3d', 'extended',
               'directors', 'multisubs'] + propers + specials
    
    remove = ['imax']

    codecs = ['x264', 'x.264', 'h264', 'h.264', 'XViD']

    sounds = ['AC3', 'DD5.1']

    def strip_spaces(self, text):
        """Removes all unnecessary duplicate spaces from a text"""
        s = text.strip()
        while s.find('  ') != -1:
            s = s.replace('  ', ' ')

        return s

    def remove_words(self, text, words):
        """Clean all given :words: from :text: case insensitivively"""
        for word in words:
            text = self.ireplace(text, word, '')
        # remove duplicate spaces
        text = ' '.join(text.split())
        return text

    def ireplace(self, str, old, new, count=0):
        """Case insensitive string replace"""
        pattern = re.compile(re.escape(old), re.I)
        return re.sub(pattern, new, str, count)
