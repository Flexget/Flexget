import urllib
import urllib2
import logging
import re
import string
import difflib
from manager import ModuleWarning

# this way we don't force users to install bs incase they do not want to use this module
soup_present = True

try:
    from BeautifulSoup import BeautifulSoup
except:
    soup_present = False

__pychecker__ = 'unusednames=parser'

log = logging.getLogger('imdb')

class ImdbSearch:

    def __init__(self):
        # depriorize aka matches a bit
        self.aka_weight = 0.9
        # priorize popular matches a bit
        self.unpopular_weight = 0.95
        self.min_match = 0.5
        self.min_diff = 0.01
        self.debug = False
        self.cutoffs = ['dvdrip', 'dvdscr', 'cam', 'r5', 'limited',
                        'xvid', 'h264', 'x264', 'h.264', 'x.264', 
                        'dvd', 'screener', 'unrated', 'repack', 
                        'rerip', 'proper', '720p', '1080p', '1080i',
                        'bluray']
        self.remove = ['imax']
        
        self.ignore_types = ['VG']
        
    def ireplace(self, str, old, new, count=0):
        """Case insensitive string replace"""
        pattern = re.compile(re.escape(old), re.I)
        return re.sub(pattern, new, str, count)

    def parse_name(self, s):
        """Sanitizes movie name from all kinds of crap"""
        for char in ['[', ']', '_']:
            s = s.replace(char, ' ')
        # if there are no spaces, start making begining from dots
        if s.find(' ') == -1:
            s = s.replace('.', ' ')
        if s.find(' ') == -1:
            s = s.replace('-', ' ')

        # remove unwanted words
        for word in self.remove:
            s = self.ireplace(s, word, '')
            
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
        s = string.join(parts[:cut_pos], ' ')
        return s, year

    def smart_match(self, raw_name):
        """Accepts messy name, cleans it and uses information available to make smartest and best match"""
        name, year = self.parse_name(raw_name)
        if name=='':
            log.critical('Failed to parse name from %s' % raw_name)
            return None
        log.debug('smart_match name=%s year=%s' % (name, str(year)))
        return self.best_match(name, year)

    def best_match(self, name, year=None):
        """Return single movie that best matches name criteria or None"""
        movies = self.search(name)

        # remove all movies below min_match, and different year
        for movie in movies[:]:
            if year and movie.get('year'):
                if movie['year'] != str(year):
                    log.debug('best_match removing %s - %s (wrong year: %s)' % (movie['name'], movie['url'], str(movie['year'])))
                    movies.remove(movie)
                    continue
            if movie['match'] < self.min_match:
                log.debug('best_match removing %s (min_match)' % movie['name'])
                movies.remove(movie)
                continue
            if movie.get('type', None) in self.ignore_types:
                log.debug('best_match removing %s (ignored type)' % movie['name'])
                movies.remove(movie)
                continue

        if len(movies) == 0:
            log.debug('no movies remain')
            return None
        
        # if only one remains ..        
        if len(movies) == 1:
            log.debug('only one movie remains')
            return movies[0]

        # check min difference between best two hits
        diff = movies[0]['match'] - movies[1]['match']
        if diff < self.min_diff:
            log.debug('unable to determine correct movie, min_diff too small')
            for m in movies:
                log.debug('remain: %s (match: %s) %s' % (m['name'], m['match'], m['url']))
            return None
        else:
            return movies[0]

    def search(self, name):
        """Return array of movie details (dict)"""
        log.debug('Searching: %s' % name)
        url = "http://www.imdb.com/find?" + urllib.urlencode({'q':name, 's':'all'})
        log.debug('Serch query: %s' % url)
        page = urllib2.urlopen(url)
        actual_url = page.geturl()

        movies = []
        # incase we got redirected to movie page (perfect match)
        re_m = re.match('.*\.imdb\.com\/title\/tt\d+\/', actual_url)
        if re_m:
            actual_url = re_m.group(0)
            log.debug('Perfect hit. Search got redirected to %s' % actual_url)
            movie = {}
            movie['match'] = 1.0
            movie['name'] = name
            movie['url'] = actual_url
            movie['year'] = None # skips year check
            movies.append(movie)
            return movies

        soup = BeautifulSoup(page)

        sections = ['Popular Titles', 'Titles (Exact Matches)',
                    'Titles (Partial Matches)', 'Titles (Approx Matches)']

        for section in sections:
            section_tag = soup.find('b', text=section)
            if not section_tag:
                continue
            try:
                section_p = section_tag.parent.parent
            except AttributeError:
                log.debug('Section % does not have parent?' % section)
                continue
            
            links = section_p.findAll('a', attrs={'href': re.compile('\/title\/tt')})
            for link in links:
                # skip links with javascript (not movies)
                if link.has_key('onclick'): continue
                # skip links with div as a parent (not movies, somewhat rare links in additional details)
                if link.parent.name==u'div': continue
                
                movie = {}
                additional = re.findall('\((.*?)\)', link.next.next)
                if len(additional) > 0:
                    movie['year'] = filter(unicode.isdigit, additional[0]) # strip non numbers ie. 2008/I
                if len(additional) > 1:
                    movie['type'] = additional[1]
                
                movie['name'] = link.string
                movie['url'] = "http://www.imdb.com" + link.get('href')
                log.debug('processing %s - %s' % (movie['name'], movie['url']))
                # calc & set best matching ratio
                seq = difflib.SequenceMatcher(lambda x: x==' ', movie['name'], name)
                ratio = seq.ratio()
                # check if some of the akas have better ratio
                for aka in link.parent.findAll('em', text=re.compile('".*"')):
                    aka = aka.replace('"', '')
                    seq = difflib.SequenceMatcher(lambda x: x==' ', aka.lower(), name.lower())
                    aka_ratio = seq.ratio() * self.aka_weight
                    if aka_ratio > ratio:
                        log.debug('- aka %s has better ratio %s' % (aka, aka_ratio))
                        ratio = aka_ratio
                # priorize popular titles
                if section!=sections[0]:
                    ratio = ratio * self.unpopular_weight
                else:
                    log.debug('- priorizing popular title')
                # store ratio
                movie['match'] = ratio
                movies.append(movie)

        def cmp_movie(m1, m2):
            return cmp (m2['match'], m1['match'])
        movies.sort(cmp_movie)
        return movies

class ImdbParser:
    """Quick-hack to parse relevant imdb details"""

    yaml_serialized = ['genres', 'languages', 'score', 'votes', 'year', 'plot_outline', 'name']
    
    def __init__(self):
        self.genres = []
        self.languages = []
        self.score = 0.0
        self.votes = 0
        self.year = 0
        self.plot_outline = None
        self.name = None

    def to_yaml(self):
        """Serializes imdb details into yaml compatible structure"""
        d = {}
        for n in self.yaml_serialized:
            d[n] = getattr(self, n)
        return d

    def from_yaml(self, yaml):
        """Builds object from yaml serialized data"""
        undefined = object()
        for n in self.yaml_serialized:
            # undefined check allows adding new fields without breaking things ..
            value = yaml.get(n, undefined)
            if value is undefined: continue
            setattr(self, n, value)

    def parse(self, url):
        try:
            page = urllib2.urlopen(url)
        except ValueError:
            raise ValueError('Invalid url %s' % url)
            
        soup = BeautifulSoup(page)

        # get name
        tag_name = soup.find('h1')
        if tag_name:
            if tag_name.next:
                self.name = tag_name.next.string.strip()
                log.debug('Detected name: %s' % self.name)
        else:
            log.warning('Unable to get name for %s, module needs update?' % url)
            
        # get votes
        tag_votes = soup.find('b', text=re.compile('\d votes'))
        if tag_votes:
            str_votes = ''.join(c for c in tag_votes.string if c.isdigit())
            self.votes = int(str_votes)
            log.debug('Detected votes: %s' % self.votes)
        else:
            log.warning('Unable to get votes for %s, module needs update?' % url)

        # get score
        tag_score = soup.find('b', text=re.compile('\d.\d/10'))
        if tag_score:
            str_score = tag_score.string
            re_score = re.compile("(\d.\d)\/10")
            match = re_score.search(str_score)
            if match:
                str_score = match.group(1)
                self.score = float(str_score)
                log.debug('Detected score: %s' % self.score)
        else:
            log.warning('Unable to get score for %s, module needs update?' % url)

        # get genres
        for link in soup.findAll('a', attrs={'href': re.compile('^/Sections/Genres/')}):
            # skip links that have javascipr onclick (not in genrelist)
            if link.has_key('onclick'): continue
            self.genres.append(link.string.lower())

        # get languages
        for link in soup.findAll('a', attrs={'href': re.compile('^/Sections/Languages/')}):
            lang = link.string.lower()
            if not lang in self.languages:
                self.languages.append(lang.strip())

        # get year
        tag_year = soup.find('a', attrs={'href': re.compile('^/Sections/Years/\d*')})
        if tag_year:
            self.year = int(tag_year.string)
            log.debug('Detected year: %s' % self.year)
        else:
            log.warning('Unable to get year for %s, module needs update?' % url)

        # get plot outline
        tag_outline = soup.find('h5', text=re.compile('Plot.*:'))
        if tag_outline:
            if tag_outline.next:
                self.plot_outline = tag_outline.next.string.strip()
                log.debug('Detected plot outline: %s' % self.plot_outline)

        log.debug('Detected genres: %s' % self.genres)
        log.debug('Detected languages: %s' % self.languages)

class FilterImdb:

    """
        This module allows filtering based on IMDB score, votes and genres etc.

        Configuration:
        
            Note: All parameters are optional. Some are mutually exclusive.
        
            min_score: <num>
            min_votes: <num>
            min_year: <num>

            # reject if genre contains any of these
            reject_genres:
                - genre1
                - genre2

            # reject if language contain any of these
            reject_languages:
                - language1

            # accept only this language
            accept_languages:
                - language1

            # filter all entries which are not imdb-compatible
            # this has default value (True) even when key not present
            filter_invalid: True / False

        Entry fields (module developers):
        
            All fields are optional, but lack of required fields will
            result in filtering usually in default configuration (see reject_invalid).
        
            imdb_url       : Most important field, should point to imdb-movie-page (string)
            imdb_score     : Pre-parsed score/rating value (float)
            imdb_votes     : Pre-parsed number of votes (int)
            imdb_year      : Pre-parsed production year (int)
            imdb_genres    : Pre-parsed genrelist (array)
            imdb_languages : Pre-parsed languagelist (array)
            
            Supplying pre-parsed values may avoid checking and parsing from imdb_url.
            So supply them in your input-module if it's practical!
    """

    def register(self, manager, parser):
        manager.register('imdb')

    def validate(self, config):
        """Validate given configuration"""
        from validator import DictValidator
        imdb = DictValidator()
        imdb.accept('min_year', int)
        imdb.accept('min_votes', int)
        imdb.accept('min_score', float)
        imdb.accept('min_score', int)
        imdb.accept('reject_genres', list).accept(str)
        imdb.accept('reject_languages', list).accept(str)
        imdb.accept('filter_invalid', bool)
        imdb.validate(config)
        return imdb.errors.messages

    def imdb_required(self, entry, config):
        """Return True if config contains conditions that are not available in preparsed fields"""
        # TODO: make dict (mapping min_votes <->imdb_votes) and loop it
        # check that entry values are VALID (None is considered as having value, this is a small bug!)
        if config.has_key('min_votes') and not entry.has_key('imdb_votes'): return True
        if config.has_key('min_score') and not entry.has_key('imdb_score'): return True
        if config.has_key('min_year') and not entry.has_key('imdb_year'): return True
        if config.has_key('reject_genres') and not entry.has_key('imdb_genres'): return True
        if config.has_key('reject_languages') and not entry.has_key('imdb_languages'): return True
        if config.has_key('accept_languages') and not entry.has_key('imdb_languages'): return True
        return False
        
    def clean_url(self, url):
        """Cleans imdb url, returns valid clean url or False"""
        m = re.search('(http://.*imdb\.com\/title\/tt\d*\/)', url)
        if m:
            return m.group()
        return False

    def feed_filter(self, feed):
        if not soup_present: raise ModuleWarning("Module filter_imdb requires BeautifulSoup. Please install it from http://www.crummy.com/software/BeautifulSoup/ or from your distribution repository.", log)
        config = feed.config['imdb']
        for entry in feed.entries:
        
            # make sure imdb url is valid
            if entry.has_key('imdb_url'):
                clean = self.clean_url(entry['imdb_url'])
                if not clean:
                    del(entry['imdb_url'])
                else:
                    entry['imdb_url'] = clean

            # if no url for this entry, look from cache and try to use imdb search
            if not entry.get('imdb_url'):
                cached = feed.shared_cache.get(entry['title'])
                if cached == 'WILL_FAIL':
                    # this movie cannot be found, not worth trying again ...
                    log.debug('%s will fail search, filtering' % entry['title'])
                    feed.filter(entry)
                    continue
                if cached:
                    log.debug('Setting imdb url for %s from cache' % entry['title'])
                    entry['imdb_url'] = cached

            if not entry.get('imdb_url') and self.imdb_required(entry, config):
                # try searching from imdb
                feed.verbose_progress('Searching from imdb %s' % entry['title'])
                search = ImdbSearch()
                movie = search.smart_match(entry['title'])
                if movie:
                    log.debug('Imdb search was success')
                    entry['imdb_url'] = movie['url']
                    # store url for this movie, so we don't have to search on every run
                    feed.shared_cache.store(entry['title'], entry['imdb_url'])
                else:
                    feed.log_once('Imdb search failed for %s' % entry['title'], log)
                    # store FAIL for this title
                    feed.shared_cache.store(entry['title'], 'WILL_FAIL')
                    # act depending configuration
                    if config.get('filter_invalid', True):
                        feed.log_once('Filtering %s because of undeterminable imdb url' % entry['title'], log)
                        feed.filter(entry)
                    else:
                        log.debug('Unable to check %s due missing imdb url, configured to pass (filter_invalid is False)' % entry['title'])
                    continue

            imdb = ImdbParser()
            if self.imdb_required(entry, config):
                # check if this imdb page has been parsed & cached
                cached = feed.shared_cache.get(entry['imdb_url'])
                if not cached:
                    feed.verbose_progress('Parsing from imdb %s' % entry['title'])
                    try:
                        imdb.parse(entry['imdb_url'])
                    except UnicodeDecodeError:
                        log.error('Unable to determine encoding for %s. Installing chardet library may help.' % entry['imdb_url'])
                        feed.filter(entry)
                        # store cache so this will be skipped
                        feed.shared_cache.store(entry['imdb_url'], imdb.to_yaml())
                        continue # next entry
                    except ValueError:
                        log.error('Invalid parameter: %s' % entry['imdb_url'])
                        feed.filter(entry)
                        continue # next entry
                    except urllib2.HTTPError, he:
                        feed.log_once('Invalid imdb url %s ? %s' % (entry['imdb_url'], he), log)
                        feed.filter(entry)
                        continue # next entry
                    except Exception, e:
                        feed.filter(entry)
                        log.error('Unable to process url %s' % entry['imdb_url'])
                        log.exception(e)
                        continue # next entry
                else:
                    imdb.from_yaml(cached)
                # store to cache
                feed.shared_cache.store(entry['imdb_url'], imdb.to_yaml())
            else:
                # Set few required fields manually from entry, and thus avoiding request & parse
                # Note: It doesn't matter even if some fields are missing, previous imdb_required
                # checks that those aren't required in condition check. So just set them all! :)
                imdb.votes = entry.get('imdb_votes', 0)
                imdb.score = entry.get('imdb_score', 0.0)
                imdb.year = entry.get('imdb_year', 0)
                imdb.languages = entry.get('imdb_languages', [])
                imdb.genres = entry.get('imdb_genres', [])

            # Check defined conditions, TODO: rewrite into functions?
            
            reasons = []
            if config.has_key('min_score'):
                if imdb.score < config['min_score']:
                    reasons.append('min_score (%s < %s)' % (imdb.score, config['min_score']))
            if config.has_key('min_votes'):
                if imdb.votes < config['min_votes']:
                    reasons.append('min_votes (%s < %s)' % (imdb.votes, config['min_votes']))
            if config.has_key('min_year'):
                if imdb.year < config['min_year']:
                    reasons.append('min_year')
            if config.has_key('reject_genres'):
                rejected = config['reject_genres']
                for genre in imdb.genres:
                    if genre in rejected:
                        reasons.append('reject_genres')
                        break
            if config.has_key('reject_languages'):
                rejected = config['reject_languages']
                for language in imdb.languages:
                    if language in rejected:
                        reasons.append('relect_languages')
                        break
            if config.has_key('accept_languages'):
                accepted = config['accept_languages']
                for language in imdb.languages:
                    if language not in accepted:
                        reasons.append('accept_languages')
                        break

            # populate some fields from imdb results, incase someone wants to use them later
            entry['imdb_plot_outline'] = imdb.plot_outline
            entry['imdb_name'] = imdb.name

            if reasons:
                feed.log_once('Filtering %s because of rule(s) %s' % (entry['title'], string.join(reasons, ', ')), log)
                feed.filter(entry)
            else:
                log.debug('Accepting %s' % (entry))
                feed.accept(entry)
