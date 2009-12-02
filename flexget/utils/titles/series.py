import logging
import re
from flexget.utils.titles.parser import TitleParser, ParseWarning

log = logging.getLogger('seriesparser')

# Forced to INFO !
# switch to logging.DEBUG if you want to debug this class (produces quite a bit info ..)
log.setLevel(logging.INFO)


class SeriesParser(TitleParser):

    """

    Parse series.

    :name: series name
    :data: data to parse
    :expect_ep: expect series to be in season, ep format

    """

    def __init__(self):
        # parser settings
        self.name = None
        self.data = None
        self.expect_ep = False
        # if set to true, episode or id must follow immediattely after name
        self.strict_name = False

        self.ep_regexps = ['s(\d+)e(\d+)', 's(\d+)ep(\d+)', 's(\d+).e(\d+)', '[^\d]([\d]{1,2})[\s]?x[\s]?(\d+)']
        self.id_regexps = ['(\d\d\d\d).(\d+).(\d+)', '(\d+).(\d+).(\d\d\d\d)', \
                           '(\d\d\d\d)x(\d+)\.(\d+)', '[^s\d](\d{1,3})[^p\d]']
        self.clean_regexps = ['\[.*?\]', '\(.*?\)']
        self.name_regexps = []

        # parse produces these
        self.season = None
        self.episode = None
        self.id = None
        self.quality = 'unknown'
        self.proper_or_repack = False
        self.special = False

        # false if item does not match series
        self.valid = False

    def parse(self):
        if not self.name or not self.data:
            raise Exception('SeriesParser initialization error, name: %s data: %s' % \
               (repr(self.name), repr(self.data)))
        if not isinstance(self.name, basestring):
            raise Exception('SeriesParser name is not a string, got %s' % repr(self.name))
        if not isinstance(self.data, basestring):
            raise Exception('SeriesParser data is not a string, got %s' % repr(self.data))

        data = self.data

        # perform data cleaner regexps
        for clean_re in self.clean_regexps:
            matches = re.findall(clean_re, data, re.IGNORECASE | re.UNICODE)
            # remove all matches from data, unless they happen to contain relevant information
            if matches:
                for match in matches:
                    # TODO: check if match contain valid episode number ?
                    log.log(5, 'match: %s' % match)
                    safe = True
                    for quality in self.qualities:
                        if quality.lower() in match.lower():
                            safe = False
                            break
                    for proper in self.propers:
                        if proper.lower() in match.lower():
                            safe = False
                            break
                    if not safe:
                        break
                    else:
                        data = data.replace(match, '').strip()

        log.log(5, 'data after cleaners: %s' % data)

        def clean(str):
            """Helper, just replace crap with spaces"""
            return re.sub(r'[-_.\[\]\(\)]+', ' ', str).strip().lower()

        name = clean(self.name)
        data = clean(data)
        # remove duplicate spaces
        data = ' '.join(data.split())

        log.log(5, 'data fully-cleaned: %s' % data)

        def name_to_re(name):
            """Convert 'foo bar' to '^[^...]*foo[^...]*bar[^...]+"""
            # TODO: Still doesn't handle the case where the user wants
            # "Schmost" and the feed contains "Schmost at Sea".
            blank = r'[^0-9a-zA-Z:]'
            res = re.sub(blank + '+', ' ', name)
            res = res.strip()
            res = re.sub(' +', blank + '*', res)
            res = '^' + (blank + '*') + res + (blank + '+')
            return res

        log.debug('name: %s data: %s' % (name, data))

        data_parts = data.split(' ')

        # name end position
        name_end = 0
        # regexp name matching
        if self.name_regexps:
            name_matches = False
            # use all specified regexps to this data
            for name_re in self.name_regexps:
                match = re.search(name_re, data, re.IGNORECASE | re.UNICODE)
                if match:
                    name_end = match.end()
                    name_matches = True
                    break
            if not name_matches:
                # leave this invalid
                log.debug('FAIL: name regexps do not match')
                return
        else:
            # Use a regexp generated from the name as a fallback.
            name_re = name_to_re(name)
            match = re.search(name_re, data, re.IGNORECASE | re.UNICODE)
            if not match:
                #log.debug('FAIL: regexp %s does not match %s' % (name_re, data))
                # leave this invalid
                return
            name_end = match.end()

        # TODO: matched name should be EXCLUDED from ep and id searching!

        # search tags and quality
        for part in data_parts:
            if part in self.qualities:
                if self.qualities.index(part) < self.qualities.index(self.quality):
                    log.debug('%s storing quality %s' % (self.name, part))
                    self.quality = part
                else:
                    pass
                    #log.debug('%s ignoring quality tag %s because found better %s' % (self.name, part, self.quality))
            if part in self.propers:
                self.proper_or_repack = True
            if part in self.specials:
                self.special = True

        # remove unwanted words (qualities and such) from data for ep / id parsing
        data = self.remove_words(data, self.remove + self.qualities + self.codecs)

        # search for season and episode number
        for ep_re in self.ep_regexps:
            match = re.search(ep_re, data, re.IGNORECASE | re.UNICODE)
            if match:
                # strict_name
                if self.strict_name:
                    if match.start() - name_end >= 2:
                        return

                log.debug('found episode number with regexp %s' % ep_re)
                season, episode = match.groups()
                self.season = int(season)
                self.episode = int(episode)
                self.valid = True
                return

        # search for id as last since they contain somewhat broad matches
        if not self.expect_ep:
            for id_re in self.id_regexps:
                match = re.search(id_re, data, re.IGNORECASE | re.UNICODE)
                if match:
                    # strict_name
                    if self.strict_name:
                        if match.start() - name_end >= 2:
                            return

                    log.debug('found id with regexp %s' % id_re)
                    self.id = '-'.join(match.groups())
                    if self.special:
                        self.id += '-SPECIAL'
                    self.valid = True
                    return
        else:
            # we should be getting season, ep !
            # try to look up idiotic numberin scheme 101,102,103,201,202
            # ressu: Added matching for 0101, 0102... It will fail on
            #        season 11 though
            log.debug('expect_ep enabled')
            match = re.search('(0?\d)(\d\d)', data, re.IGNORECASE | re.UNICODE)
            if match:
                # strict_name
                if self.strict_name:
                    if match.start() - name_end >= 2:
                        return

                self.season = int(match.group(1))
                self.episode = int(match.group(2))
                log.debug(self)
                self.valid = True
                return
            log.debug('-> no luck with the expect_ep')

        raise ParseWarning('%s looks like series %s but I cannot find any episode or id numbering!' % (data, self.name))

    @property
    def identifier(self):
        """Return identifier for parsed episode"""
        if not self.valid:
            raise Exception('Series flagged invalid')
        if isinstance(self.season, int) and isinstance(self.episode, int):
            return 'S%sE%s' % (str(self.season).zfill(2), str(self.episode).zfill(2))
        elif self.id is None:
            raise Exception('Series is missing identifier')
        else:
            return self.id

    @property            
    def proper(self):
        return self.proper_or_repack 

    def __str__(self):
        valid = 'INVALID'
        if self.valid:
            valid = 'OK'
        return '<SeriesParser(data=%s,name=%s,id=%s,season=%s,episode=%s,quality=%s,proper=%s,status=%s)>' % \
            (str(self.data), str(self.name), str(self.id), str(self.season), str(self.episode), \
             str(self.quality), str(self.proper_or_repack), valid)

    def __cmp__(self, other):
        """
        me = (self.qualities.index(self.quality), self.name)
        other = (self.qualities.index(other.quality), other.name)
        return cmp(me, other)
        """
        return cmp(self.qualities.index(self.quality), self.qualities.index(other.quality))

    def __eq__(self, other):
        return self is other
