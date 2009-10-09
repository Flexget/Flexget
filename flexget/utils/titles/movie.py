import logging
import re

from flexget.utils.titles.parser import TitleParser, ParseWarning

log = logging.getLogger('movieparser')

class MovieParser(TitleParser):
    
    # TODO: refactor SeriesParser and this into common nice API


    def _ireplace(self, str, old, new, count=0):
        """Case insensitive string replace"""
        pattern = re.compile(re.escape(old), re.I)
        return re.sub(pattern, new, str, count)

    def parse(self, s):
        """Parse movie name, returns name, year"""
        for char in ['[', ']', '_', '(', ')', ',']:
            s = s.replace(char, ' ')
        # if there are no spaces, start making begining from dots
        if s.find(' ') == -1:
            s = s.replace('.', ' ')
        if s.find(' ') == -1:
            s = s.replace('-', ' ')

        # remove unwanted words
        for word in self.remove:
            s = self._ireplace(s, word, '')
            
        # remove extra and duplicate spaces!
        s = s.strip()
        while s.find('  ') != -1:
            s = s.replace('  ', ' ')

        # split to parts        
        parts = s.split(' ')
        year = None
        cut_pos = 256
        for part in parts:
            # check for year
            if part.isdigit():
                n = int(part)
                if n>1930 and n<2050:
                    year = part
                    if parts.index(part) < cut_pos:
                        cut_pos = parts.index(part)
            # if length > 3 and whole word in uppers, consider as cutword (most likelly a group name)
            if len(part) > 3 and part.isupper() and part.isalpha():
                if parts.index(part) < cut_pos:
                    cut_pos = parts.index(part)
            # check for cutoff words
            if part.lower() in self.cutoffs:
                if parts.index(part) < cut_pos:
                    cut_pos = parts.index(part)
        # make cut
        s = ' '.join(parts[:cut_pos])
        return s, year

