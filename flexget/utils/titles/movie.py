import logging
import re
from flexget.utils.titles.parser import TitleParser
from flexget.utils import qualities

log = logging.getLogger('movieparser')


class MovieParser(TitleParser):
    
    def __init__(self):
        self.data = None

        # parsing results
        self.name = None
        self.year = None
        self.quality = None

    def __str__(self):
        return "MovieParser(%s, %s, %s)" % (self.name, self.year, self.quality)

    def parse(self):
        """Parse movie name, returns name, year"""
        s = self.data

        for char in '[]()_,.':
            s = s.replace(char, ' ')

        # if there are no spaces
        if s.find(' ') == -1:
            s = s.replace('-', ' ')

        # remove unwanted words (imax, ..)
        self.remove_words(s, self.remove)
            
        s = self.strip_spaces(s)

        # split to parts        
        parts = s.split(' ')
        year = None
        cut_pos = 256
        self.quality = 'unknown'
        for part in parts:
            # check for year
            if part.isdigit():
                num = int(part)
                if num > 1930 and num < 2050:
                    year = part
                    if parts.index(part) < cut_pos:
                        cut_pos = parts.index(part)
            # if length > 3 and whole word in uppers, consider as cut word (most likely a group name)
            if len(part) > 3 and part.isupper() and part.isalpha():
                if parts.index(part) < cut_pos:
                    cut_pos = parts.index(part)
            # check for cutoff words
            if part.lower() in self.cutoffs:
                if parts.index(part) < cut_pos:
                    cut_pos = parts.index(part)
            # check for qualities
            if qualities.get(self.quality) < qualities.get(part):
                self.quality = qualities.common_name(part)
                if parts.index(part) < cut_pos:
                    cut_pos = parts.index(part)

        # make cut
        s = ' '.join(parts[:cut_pos])

        # save results
        self.name = s

        if year:
            if year.isdigit():
                self.year = int(year)
