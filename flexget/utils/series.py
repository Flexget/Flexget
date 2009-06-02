import logging
import re

log = logging.getLogger('seriesparser')

class SeriesParser:
    qualities = ['1080p', '1080', '720p', '720', 'hr', 'dvd', 'dvdrip', 'hdtv', 'pdtv', 'dsr', 'dsrip', 'unknown']
    
    propers = ['proper', 'repack']
    
    specials = ['special']
    
    def __init__(self):
        # name of the serie
        self.name = None 
        # data to parse
        self.data = None 
        
        self.ep_regexps = ['s(\d+)e(\d+)', 's(\d+)ep(\d+)', '[^\d]([\d]{1,2})x(\d+)']
        self.id_regexps = ['(\d\d\d\d).(\d+).(\d+)', '(\d+).(\d+).(\d\d\d\d)', \
                           '(\d\d\d\d)x(\d+)\.(\d+)', '(\d\d\d)', '(\d\d)', '(\d)']
        self.name_regexps = []
        # parse produces these
        self.season = None
        self.episode = None
        self.id = None

        self.quality = 'unknown'
        # false if item does not match serie
        self.valid = False
        # optional for storing entry from which this instance is made from
        self.entry = None
        # repack / proper
        self.proper_or_repack = False
        self.special = False

    def parse(self):
        if not self.name or not self.data:
            raise Exception('SeriesParser initialization error, name: %s data: %s' % \
                            (repr(self.name), repr(self.data)))
        if not isinstance(self.name, basestring):
            raise Exception('SeriesParser name is not a string, got %s' % repr(self.name))
        if not isinstance(self.data, basestring):
            raise Exception('SeriesParser data is not a string, got %s' % repr(self.data))

        def clean(str):
            return re.sub(r'[ _.\[\]]+', ' ', str).strip().lower()

        name = clean(self.name)
        data = clean(self.data)

        def name_to_re(name):
            """Convert 'foo bar' to '^[^...]*foo[^...]*bar[^...]+"""
            # TODO: Still doesn't handle the case where the user wants
            # "Schmost" and the feed contains "Schmost at Sea".
            blank = r'[^0-9a-zA-Z]'
            res = re.sub(blank+'+', ' ', name)
            res = res.strip()
            res = re.sub(' +', blank+'*', res)
            res = '^' + (blank+'*') + res + (blank+'+')
            return res

        #log.debug('name: %s data: %s' % (name, data))
        
        data_parts = data.split(' ')

        # regexp name matching
        if self.name_regexps:
            name_matches = False
            # use all specified regexps to this data
            for name_re in self.name_regexps:
                match = re.search(name_re, self.data, re.IGNORECASE|re.UNICODE)
                if match:
                    name_matches = True
                    break
            if not name_matches:
                # leave this invalid
                #log.debug('FAIL: name regexps do not match')
                return
        else:
            # Use a regexp generated from the name as a fallback.
            name_re = name_to_re(name)
            if not re.search(name_re, self.data, re.IGNORECASE|re.UNICODE):
                #log.debug('FAIL: regexp %s does not match %s' % (name_re, self.data))
                # leave this invalid
                return
                
        # TODO: matched name should be EXCLUDED from ep and id searching!

        # search tags
        for part in data_parts:
            if part in self.qualities:
                if self.qualities.index(part) < self.qualities.index(self.quality):
                    #log.debug('%s storing quality %s' % (self.name, part))
                    self.quality = part
                else:
                    pass
                    #log.debug('%s ignoring quality tag %s because found better %s' % (self.name, part, self.quality))
            if part in self.propers:
                self.proper_or_repack = True
            if part in self.specials:
                self.special = True

        # search for season and episode number
        for ep_re in self.ep_regexps:
            match = re.search(ep_re, self.data, re.IGNORECASE|re.UNICODE)
            if match:
                #log.debug('found episode number with regexp %s' % ep_re)
                season, episode = match.groups()
                self.season = int(season)
                self.episode = int(episode)
                self.valid = True
                self.id = "S%sE%s" % (self.season, self.episode)
                return

        # search for id as last since they contain somewhat broad matches
        for id_re in self.id_regexps:
            match = re.search(id_re, self.data, re.IGNORECASE|re.UNICODE)
            if match:
                #log.debug('found id with regexp %s' % id_re)
                self.id = '-'.join(match.groups())
                if self.special:
                    self.id += '-SPECIAL'
                self.valid = True
                return

        log.debug('FAIL: unable to find any id from %s' % data)

    def identifier(self):
        """Return identifier for parsed episode"""
        if not self.valid: raise Exception('Series flagged invalid')
        return self.id

    def __str__(self):
        valid = 'INVALID'
        if self.valid:
            valid = 'OK'
        return 'series: %s, id: %s season: %s episode: %s quality: %s status: %s' % \
        (str(self.name), str(self.id), str(self.season), str(self.episode), str(self.quality), valid)
