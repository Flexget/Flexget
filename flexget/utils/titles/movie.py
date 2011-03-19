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
        self.proper_count = 0
        TitleParser.__init__(self)

    def __str__(self):
        return "<MovieParser(name=%s,year=%s,quality=%s)>" % (self.name, self.year, self.quality)

    def parse(self):
        """Parse movie name, returns name, year"""
        data = self.data

        for char in '[]()_,.':
            data = data.replace(char, ' ')

        # if there are no spaces
        if data.find(' ') == -1:
            data = data.replace('-', ' ')

        # remove unwanted words (imax, ..)
        self.remove_words(data, self.remove)

        data = self.strip_spaces(data)

        # split to parts
        parts = data.split(' ')
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
            # check for propers
            if part.lower() in self.propers:
                self.proper_count += 1

        # make cut
        data = ' '.join(parts[:cut_pos])

        # save results
        self.name = data

        if year:
            if year.isdigit():
                self.year = int(year)
