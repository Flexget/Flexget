import logging
from flexget.utils.titles.parser import TitleParser
from flexget.utils import qualities

log = logging.getLogger('movieparser')


def diff_pos(string1, string2):
    """Returns first position where string1 and string2 differ."""
    for (count, c) in enumerate(string1):
        if len(string2) <= count:
            return count
        if string2[count] != c:
            return count


class MovieParser(TitleParser):

    def __init__(self):
        self.data = None
        self.reset()
        TitleParser.__init__(self)

    def reset(self):
        # parsing results
        self.name = None
        self.year = None
        self.quality = qualities.UNKNOWN
        self.proper_count = 0

    def __str__(self):
        return "<MovieParser(name=%s,year=%s,quality=%s)>" % (self.name, self.year, self.quality)

    def parse(self, data=None):
        """Parse movie name. Populates name, year, quality and proper_count attributes"""

        # Reset before parsing, so the parser can be reused.
        self.reset()

        if data is None:
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
        cut_part = 256
        for part_pos, part in enumerate(parts):
            cut = False
            # Don't let the first word be cutoff word
            if part_pos < 1:
                continue
            # check for year
            if part.isdigit():
                num = int(part)
                if 1930 < num < 2050:
                    year = part
                    cut = True
            # if length > 3 and whole word in uppers, consider as cut word (most likely a group name)
            if len(part) > 3 and part.isupper() and part.isalpha() and part_pos > 0:
                cut = True
            # check for cutoff words
            if part.lower() in self.cutoffs:
                cut = True
            # check for propers
            if part.lower() in self.propers:
                self.proper_count += 1
                cut = True
            # update cut position
            if cut and parts.index(part) < cut_part:
                cut_part = part_pos

        if cut_part != 256:
            log.debug('parts: %s, cut is: %s' % (parts, parts[cut_part]))

        # calculate cut positon from cut_part
        abs_cut = len(' '.join(parts[:cut_part]))

        log.debug('after parts check, cut data would be: `%s` abs_cut: %i' % (data[:abs_cut], abs_cut))

        # parse quality
        quality, remaining = qualities.quality_match(data)
        if quality:
            self.quality = quality
            # remaining string is same as data but quality information removed
            # find out position where there is first difference, this is earliest
            # quality bit, anything after that has no relevance to the movie name
            dp = diff_pos(data, remaining)
            if dp is not None:
                log.debug('quality start: %s' % dp)
                if dp < abs_cut:
                    log.debug('quality cut is even shorter')
                    abs_cut = dp

        # make cut
        data = data[:abs_cut].strip()
        log.debug('data cut to `%s` - this will be the name' % data)

        # save results
        self.name = data

        if year:
            if year.isdigit():
                self.year = int(year)
