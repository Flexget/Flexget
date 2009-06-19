import difflib
import urllib
import urllib2
import logging
import re
from flexget.utils.soup import get_soup
from BeautifulSoup import NavigableString
from socket import timeout

log = logging.getLogger('utils.imdb')

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
        s = ' '.join(parts[:cut_pos])
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
        
        if not movies:
            log.debug('search did not return any movies')
            return None

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

        if not movies:
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
        url = u'http://www.imdb.com/find?' + urllib.urlencode({'q':name.encode('latin1'), 's':'all'})
        log.debug('Serch query: %s' % repr(url))
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

        soup = get_soup(page)

        sections = ['Popular Titles', 'Titles (Exact Matches)',
                    'Titles (Partial Matches)', 'Titles (Approx Matches)']

        for section in sections:
            section_tag = soup.find('b', text=section)
            if not section_tag:
                log.debug('section %s not found' % section)
                continue
            log.debug('processing section %s' % section)
            try:
                section_table = section_tag.parent.parent.nextSibling
            except AttributeError:
                log.debug('Section % does not have a table?' % section)
                continue
            
            links = section_table.findAll('a', attrs={'href': re.compile('\/title\/tt')})
            if not links:
                log.debug('section %s does not have links' % section)
            for link in links:
                # skip links with div as a parent (not movies, somewhat rare links in additional details)
                if link.parent.name==u'div': 
                    continue
                    
                # skip links without text value, these are small pictures before title
                if len(link.contents) == 1 and not isinstance(link.contents[0], NavigableString):
                    continue

                #log.debug('processing link %s' % link)
                    
                movie = {}
                additional = re.findall('\((.*?)\)', link.next.next)
                if len(additional) > 0:
                    movie['year'] = filter(unicode.isdigit, additional[0]) # strip non numbers ie. 2008/I
                if len(additional) > 1:
                    movie['type'] = additional[1]
                
                movie['name'] = link.contents[0]
                movie['url'] = "http://www.imdb.com" + link.get('href')
                log.debug('processing name: %s url: %s' % (movie['name'], movie['url']))
                # calc & set best matching ratio
                seq = difflib.SequenceMatcher(lambda x: x==' ', movie['name'], name)
                ratio = seq.ratio()
                # check if some of the akas have better ratio
                aka_re = re.compile('".*"')
                for aka in [l for l in link.parent.findAll(text=re.compile('".*"')) if l.parent.name == 'em']:
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

    def __init__(self):
        self.genres = []
        self.languages = []
        self.score = 0.0
        self.votes = 0
        self.year = 0
        self.plot_outline = None
        self.name = None

    def parse(self, url):
        try:
            page = urllib2.urlopen(url)
        except ValueError:
            raise ValueError('Invalid url %s' % url)
            
        soup = get_soup(page)

        # get name
        tag_name = soup.find('h1')
        if tag_name:
            if tag_name.next:
                self.name = tag_name.next.string.strip()
                log.debug('Detected name: %s' % self.name)
        else:
            log.warning('Unable to get name for %s - plugin needs update?' % url)
            
        # get votes
        tag_votes = soup.find('b', text=re.compile('\d votes'))
        if tag_votes:
            str_votes = ''.join([c for c in tag_votes.string if c.isdigit()])
            self.votes = int(str_votes)
            log.debug('Detected votes: %s' % self.votes)
        else:
            log.warning('Unable to get votes for %s - plugin needs update?' % url)

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
            log.warning('Unable to get score for %s - plugin needs update?' % url)

        # get genres
        for link in soup.findAll('a', attrs={'href': re.compile('^/Sections/Genres/')}):
            # skip links that have javascipr onclick (not in genrelist)
            if link.has_key('onclick'): 
                continue
            self.genres.append(link.contents[0].lower())

        # get languages
        for link in soup.findAll('a', attrs={'href': re.compile('^/Sections/Languages/')}):
            lang = link.contents[0].lower()
            if not lang in self.languages:
                self.languages.append(lang.strip())

        # get year
        tag_year = soup.find('a', attrs={'href': re.compile('^/Sections/Years/\d*')})
        if tag_year:
            self.year = int(tag_year.contents[0])
            log.debug('Detected year: %s' % self.year)
        else:
            log.warning('Unable to get year for %s - plugin needs update?' % url)

        # get plot outline
        tag_outline = soup.find('h5', text=re.compile('Plot.*:'))
        if tag_outline:
            if tag_outline.next:
                self.plot_outline = tag_outline.next.string.strip()
                log.debug('Detected plot outline: %s' % self.plot_outline)

        log.debug('Detected genres: %s' % self.genres)
        log.debug('Detected languages: %s' % self.languages)
