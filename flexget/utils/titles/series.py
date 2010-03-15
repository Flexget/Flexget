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
        self.name = ''
        self.data = ''
        self.expect_ep = False

        # if set to true, episode or id must follow immediately after name
        self.strict_name = False

        self.ep_regexps = ['s(\d+)e(\d+)', 's(\d+)ep(\d+)', 's(\d+).e(\d+)', \
                           '[^\d]([\d]{1,2})[\s]?x[\s]?(\d+)']
        self.id_regexps = ['(\d\d\d\d).(\d+).(\d+)', '(\d+).(\d+).(\d\d\d\d)', \
                           '(\d\d\d\d)x(\d+)\.(\d+)', \
                           '(pt|part)\s?(\d+|IX|IV|V?I{0,3})', \
                           '[^s\d](\d{1,3})[^p\d]']
        self.clean_regexps = ['\[.*?\]', '\(.*?\)']
        self.name_regexps = []

        self.field = None

        # parse produces these
        self.season = None
        self.episode = None
        self.id = None
        self.quality = 'unknown'
        self.proper_or_repack = False
        self.special = False

        # false if item does not match series
        self.valid = False

    def __setattr__(self, name, value):
        """Convert name and data to unicode transparently"""
        if name == 'name' or name == 'data':
            if isinstance(value, str):
                object.__setattr__(self, name, unicode(value))
                return
            elif not isinstance(value, unicode):
                raise Exception('%s cannot be %s' % (name, repr(value)))
        object.__setattr__(self, name, value)

    def clean(self, data):
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

        log.log(5, 'cleaned data: %s' % data)

        return data

    def parse(self):
        if not self.name or not self.data:
            raise Exception('SeriesParser initialization error, name: %s data: %s' % \
               (repr(self.name), repr(self.data)))

        data = self.clean(self.data)

        def remove_dirt(str):
            """Helper, just replace crap with spaces"""
            return re.sub(r'[-_.\[\]\(\)]+', ' ', str).strip().lower()

        name = remove_dirt(self.name)
        data = remove_dirt(data)
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
        name_start = 0
        name_end = 0

        # regexp name matching
        if self.name_regexps:
            name_matches = False
            # use all specified regexps to this data
            for name_re in self.name_regexps:
                match = re.search(name_re, data, re.IGNORECASE | re.UNICODE)
                if match:
                    name_start = match.start()
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
            name_start = match.start()
            name_end = match.end()

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

        # Remove unwanted words (qualities and such) from data for ep / id
        # parsing need to remove them from the original string, as they
        # might not match to cleaned string.
        # Ensure the series name isn't accidentally munged.
        pre_data = ''
        if name_start:
            pre_data = self.remove_words(self.data[0:name_start-1], self.remove + self.qualities + self.codecs + self.sounds)
            pre_data = self.clean(pre_data)
            pre_data = remove_dirt(pre_data)
            name_start -= len(pre_data)
        post_data = ''
        if name_end < len(self.data) - 1:
            post_data = self.remove_words(self.data[name_end:], self.remove + self.qualities + self.codecs + self.sounds)
            post_data = self.clean(post_data)
            post_data = remove_dirt(post_data)
            name_end -= len(pre_data)

        # remove series name from the data
        # TODO: stripping leading space from this will cause unit tests to fail -> investigate
        data = ' '.join([pre_data, post_data])

        log.debug("data for id/ep parsing '%s'" % data)

        # search for season and episode number

        for ep_re in self.ep_regexps:
            match = re.search(ep_re, data, re.IGNORECASE | re.UNICODE)
            if match:
                # strict_name
                if self.strict_name:
                    if match.start() > 1:
                        return

                log.debug('found episode number with regexp %s' % ep_re)
                season, episode = match.groups()
                self.season = int(season)
                self.episode = int(episode)
                self.valid = True
                return

        # search for ids later as last since they contain somewhat broad matches

        if self.expect_ep:
            # we should be getting season, ep !
            # try to look up idiotic numbering scheme 101,102,103,201,202
            # ressu: Added matching for 0101, 0102... It will fail on
            #        season 11 though
            log.debug('expect_ep enabled')
            match = re.search('\D(0?\d)(\d\d)\D', data, re.IGNORECASE | re.UNICODE)
            if match:
                # strict_name
                if self.strict_name:
                    if match.start() > 1:
                        return

                self.season = int(match.group(1))
                self.episode = int(match.group(2))
                log.debug(self)
                self.valid = True
                return
            log.debug('-> no luck with the expect_ep')
        else:
            for id_re in self.id_regexps:
                match = re.search(id_re, data, re.IGNORECASE | re.UNICODE)
                if match:
                    # strict_name
                    if self.strict_name:
                        if match.start() - name_end >= 2:
                            return

                    self.id = '-'.join(match.groups())
                    if self.special:
                        self.id += '-SPECIAL'
                    self.valid = True
                    log.debug('found id \'%s\' with regexp \'%s\'' % (self.id, id_re))
                    return

        raise ParseWarning('\'%s\' looks like series \'%s\' but I cannot find any episode or id numbering!' % (self.data, self.name))

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
        # for some fucking reason it's impossible to print self.field here, if someone figures out why please
        # tell me!
        valid = 'INVALID'
        if self.valid:
            valid = 'OK'
        return '<SeriesParser(data=%s,name=%s,id=%s,season=%s,episode=%s,quality=%s,proper=%s,status=%s)>' % \
            (self.data, self.name, str(self.id), self.season, self.episode, \
             self.quality, self.proper_or_repack, valid)

    def __cmp__(self, other):
        """
        me = (self.qualities.index(self.quality), self.name)
        other = (self.qualities.index(other.quality), other.name)
        return cmp(me, other)
        """
        return cmp(self.qualities.index(self.quality), self.qualities.index(other.quality))

    def __eq__(self, other):
        return self is other
