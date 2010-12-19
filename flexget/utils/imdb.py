import difflib
import urllib
import urllib2
import logging
import re
from flexget.utils.soup import get_soup
from BeautifulSoup import NavigableString, Tag

log = logging.getLogger('utils.imdb')


def extract_id(url):
    """Return IMDb ID of the given URL"""
    m = re.search(r'((?:nm|tt)[\d]{7})', url)
    if m:
        return m.group(1)


class ImdbSearch(object):

    def __init__(self):
        # de-prioritize aka matches a bit
        self.aka_weight = 0.9
        # prioritize popular matches a bit
        self.unpopular_weight = 0.95
        self.min_match = 0.5
        self.min_diff = 0.01
        self.debug = False

        self.remove = ['imax']

        self.ignore_types = ['VG']

    def ireplace(self, str, old, new, count=0):
        """Case insensitive string replace"""
        pattern = re.compile(re.escape(old), re.I)
        return re.sub(pattern, new, str, count)

    def smart_match(self, raw_name):
        """Accepts messy name, cleans it and uses information available to make smartest and best match"""
        from flexget.utils.titles.movie import MovieParser
        parser = MovieParser()
        parser.data = raw_name
        parser.parse()
        name = parser.name
        year = parser.year
        if name == '':
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
            log.debug('FAILURE: no movies remain')
            return None

        # if only one remains ..
        if len(movies) == 1:
            log.debug('SUCCESS: only one movie remains')
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
        try:
            url = u'http://www.imdb.com/find?' + urllib.urlencode({'q': name.encode('latin1'), 's': 'all'})
        except:
            log.warning('Problems with encoding %s, string possibly corrupted? Ignoring troublesome characters.' % name)
            url = u'http://www.imdb.com/find?' + urllib.urlencode({'q': name.encode('latin1', 'ignore'), 's': 'all'})

        log.debug('Serch query: %s' % repr(url))
        page = urllib2.urlopen(url)
        actual_url = page.geturl()

        movies = []
        # in case we got redirected to movie page (perfect match)
        re_m = re.match(r'.*\.imdb\.com/title/tt\d+/', actual_url)
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

        # the god damn page has declared a wrong encoding
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

            links = section_table.findAll('a', attrs={'href': re.compile(r'/title/tt')})
            if not links:
                log.debug('section %s does not have links' % section)
            for link in links:
                # skip links with div as a parent (not movies, somewhat rare links in additional details)
                if link.parent.name == u'div':
                    continue

                # skip links without text value, these are small pictures before title
                if len(link.contents) == 1 and not isinstance(link.contents[0], NavigableString):
                    continue

                movie = {}
                additional = re.findall(r'\((.*?)\)', link.next.next)
                if len(additional) > 0:
                    movie['year'] = filter(unicode.isdigit, additional[0]) # strip non numbers ie. 2008/I
                if len(additional) > 1:
                    movie['type'] = additional[1]

                movie['name'] = link.contents[0]
                movie['url'] = 'http://www.imdb.com' + link.get('href')
                log.debug('processing name: %s url: %s' % (movie['name'], movie['url']))

                # calc & set best matching ratio
                seq = difflib.SequenceMatcher(lambda x: x == ' ', movie['name'], name)
                ratio = seq.ratio()

                # check if some of the akas have better ratio
                for aka in link.parent.findAll('p', attrs={'class': 'find-aka'}):
                    aka = aka.next.string
                    match = re.search('".*"', aka)
                    if not match:
                        log.debug('aka `%s` is invalid' % aka)
                    aka = match.group(0).replace('"', '')
                    log.log(5, 'processing aka %s' % aka)
                    seq = difflib.SequenceMatcher(lambda x: x == ' ', aka.lower(), name.lower())
                    aka_ratio = seq.ratio() * self.aka_weight
                    if aka_ratio > ratio:
                        log.debug('- aka %s has better ratio %s' % (aka, aka_ratio))
                        ratio = aka_ratio

                # prioritize popular titles
                if section != sections[0]:
                    ratio = ratio * self.unpopular_weight
                else:
                    log.debug('- priorizing popular title')

                # store ratio
                movie['match'] = ratio
                movies.append(movie)

        def cmp_movie(m1, m2):
            return cmp(m2['match'], m1['match'])

        movies.sort(cmp_movie)
        return movies


class ImdbParser(object):
    """Quick-hack to parse relevant imdb details"""

    def __init__(self):
        self.genres = []
        self.languages = []
        self.actors = {}
        self.directors = {}
        self.score = 0.0
        self.votes = 0
        self.year = 0
        self.plot_outline = None
        self.name = None
        self.url = None
        self.imdb_id = None
        self.photo = None
        self.mpaa_rating = ''

    def __str__(self):
        return '<ImdbParser(name=%s,imdb_id=%s)>' % (self.name, self.imdb_id)

    def parse(self, url):
        self.url = url
        try:
            page = urllib2.urlopen(url)
        except ValueError:
            raise ValueError('Invalid url %s' % url)

        self.imdb_id = extract_id(self.url)

        soup = get_soup(page)

        # get photo
        tag_photo = soup.find('div', attrs={'class': 'photo'})
        if tag_photo:
            tag_img = tag_photo.find('img')
            if tag_img:
                self.photo = tag_img.get('src')
                log.debug('Detected photo: %s' % self.photo)

        # get rating. Always the first absmiddle.
        tag_infobar_div = soup.find('div', attrs={'class': 'infobar'})
        if tag_infobar_div:
            tag_mpaa_rating = tag_infobar_div.find('img', attrs={'class': 'absmiddle'})
            if tag_mpaa_rating:
                if (tag_mpaa_rating['alt'] != tag_mpaa_rating['title']):
                    # If we've found something of class absmiddle in the infobar,
                    # it should be mpaa_rating, since that's the only one in there.
                    log.warning("MPAA rating alt and title don't match for URL %s - plugin needs an update?" % url)
                else:
                    self.mpaa_rating = tag_mpaa_rating['alt']
                    log.debug('Detected mpaa rating: %s' % self.mpaa_rating)
            else:
                log.debug('Unable to match signature of mpaa rating for %s - could be a TV episode, or plugin needs update?' % url)
        else:
            # We should match the infobar, it's an integral part of the IMDB page.
            log.warning('Unable to get infodiv class for %s - plugin needs update?' % url)


        # get name
        tag_name = soup.find('h1')
        if tag_name:
            if tag_name.next:
                # Handle a page not found in IMDB. tag_name.string is
                # "<br/> Page Not Found" and there is no next tag. Thus, None.
                if tag_name.next.string is not None:
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
        tag_score = soup.find('span', attrs={'class': 'rating-rating'})
        if tag_score:
            try:
                self.score = float(tag_score.contents[0])
            except ValueError:
                log.debug('tag_score %s is not valid float' % tag_score.contents[0])
            log.debug('Detected score: %s' % self.score)
        else:
            log.warning('Unable to get score for %s - plugin needs update?' % url)

        # get genres
        for link in soup.findAll('a', attrs={'href': re.compile('^/genre/')}):
            # skip links that have javascript onclick (not in genrelist)
            if link.has_key('onclick'):
                continue
            self.genres.append(link.contents[0].lower())

        # get languages
        for link in soup.findAll('a', attrs={'href': re.compile('^/language/')}):
            lang = link.contents[0].lower()
            if not lang in self.languages:
                self.languages.append(lang.strip())

        # get year
        tag_year = soup.find('a', attrs={'href': re.compile('^/year/\d+')})
        if tag_year:
            self.year = int(tag_year.contents[0])
            log.debug('Detected year: %s' % self.year)
        else:
            tag_year = soup.find('span', text=re.compile(r'^\((?:Video|TV) \d+\)'))
            if tag_year:
                m = re.search('(\d{4})', unicode(tag_year))
                if m:
                    self.year = int(m.group())
                    log.debug('Detected year: %s' % self.year)
                else:
                    log.warning('Unable to get year for %s (regexp mismatch) - plugin needs update?' % url)
            else:
                log.warning('Unable to get year for %s (tag not found) - plugin needs update?' % url)

        # get main cast
        tag_cast = soup.find('table', 'cast_list')
        if tag_cast:
            for actor in tag_cast.findAll('a', href=re.compile('/name/nm')):
                actor_id = extract_id(actor['href'])
                actor_name = actor.contents[0]
                # tag instead of name
                if isinstance(actor_name, Tag):
                    actor_name = None
                self.actors[actor_id] = actor_name

        # get director(s)
        h4_director = soup.find('h4', text=re.compile('Director'))
        if h4_director:
            for director in h4_director.parent.parent.findAll('a', href=re.compile('/name/nm')):
                director_id = extract_id(director['href'])
                director_name = director.contents[0]
                # tag instead of name
                if isinstance(director_name, Tag):
                    director_name = None
                self.directors[director_id] = director_name

        log.debug('Detected genres: %s' % self.genres)
        log.debug('Detected languages: %s' % self.languages)
        log.debug('Detected director(s): %s' % ', '.join(self.directors))
        log.debug('Detected actors: %s' % ', '.join(self.actors))

        # get plot (another page)
        plot_url = self.url
        if not self.url.endswith('/'):
            plot_url += '/'
        plot_url += 'plotsummary'

        log.debug('Requesting %s' % plot_url)
        page = urllib2.urlopen(plot_url)
        soup = get_soup(page)

        p_plot = soup.find('p', attrs={'class': 'plotpar'})
        if p_plot:
            self.plot_outline = p_plot.next.string.strip()
            log.debug('Detected plot outline: %s' % self.plot_outline)
        else:
            log.debug('Failed to find plot')
