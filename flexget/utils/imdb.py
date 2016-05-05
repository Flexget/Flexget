from __future__ import unicode_literals, division, absolute_import
from builtins import *  # pylint: disable=unused-import, redefined-builtin
from past.builtins import basestring

import difflib
import logging
import re
import random

from bs4.element import Tag

from flexget.utils.soup import get_soup
from flexget.utils.requests import Session, TimedLimiter
from flexget.utils.tools import str_to_int
from flexget.plugin import get_plugin_by_name, PluginError

log = logging.getLogger('utils.imdb')
# IMDb delivers a version of the page which is unparsable to unknown (and some known) user agents, such as requests'
# Spoof the old urllib user agent to keep results consistent
requests = Session()
requests.headers.update({'User-Agent': 'Python-urllib/2.6'})
# requests.headers.update({'User-Agent': random.choice(USERAGENTS)})

# this makes most of the titles to be returned in english translation, but not all of them
requests.headers.update({'Accept-Language': 'en-US,en;q=0.8'})
requests.headers.update({'X-Forwarded-For': '24.110.%d.%d' % (random.randint(0, 254), random.randint(0, 254))})

# give imdb a little break between requests (see: http://flexget.com/ticket/129#comment:1)
requests.add_domain_limiter(TimedLimiter('imdb.com', '3 seconds'))


def is_imdb_url(url):
    """Tests the url to see if it's for imdb.com."""
    if not isinstance(url, basestring):
        return
    # Probably should use urlparse.
    return re.match(r'https?://[^/]*imdb\.com/', url)


def extract_id(url):
    """Return IMDb ID of the given URL. Return None if not valid or if URL is not a string."""
    if not isinstance(url, basestring):
        return
    m = re.search(r'((?:nm|tt)[\d]{7})', url)
    if m:
        return m.group(1)


def make_url(imdb_id):
    """Return IMDb URL of the given ID"""
    return u'http://www.imdb.com/title/%s/' % imdb_id


class ImdbSearch(object):

    def __init__(self):
        # de-prioritize aka matches a bit
        self.aka_weight = 0.95
        # prioritize first
        self.first_weight = 1.1
        self.min_match = 0.7
        self.min_diff = 0.01
        self.debug = False

        self.max_results = 10

    def ireplace(self, text, old, new, count=0):
        """Case insensitive string replace"""
        pattern = re.compile(re.escape(old), re.I)
        return re.sub(pattern, new, text, count)

    def smart_match(self, raw_name):
        """Accepts messy name, cleans it and uses information available to make smartest and best match"""
        parser = get_plugin_by_name('parsing').instance.parse_movie(raw_name)
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
                    log.debug('best_match removing %s - %s (wrong year: %s)' % (
                        movie['name'],
                        movie['url'],
                        str(movie['year'])))
                    movies.remove(movie)
                    continue
            if movie['match'] < self.min_match:
                log.debug('best_match removing %s (min_match)' % movie['name'])
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
            log.debug('unable to determine correct movie, min_diff too small (`%s` <-?-> `%s`)' %
                      (movies[0], movies[1]))
            for m in movies:
                log.debug('remain: %s (match: %s) %s' % (m['name'], m['match'], m['url']))
            return None
        else:
            return movies[0]

    def search(self, name):
        """Return array of movie details (dict)"""
        log.debug('Searching: %s' % name)
        url = u'http://www.imdb.com/find'
        # This may include Shorts and TV series in the results
        params = {'q': name, 's': 'tt'}

        log.debug('Search query: %s' % repr(url))
        page = requests.get(url, params=params)
        actual_url = page.url

        movies = []
        # in case we got redirected to movie page (perfect match)
        re_m = re.match(r'.*\.imdb\.com/title/tt\d+/', actual_url)
        if re_m:
            actual_url = re_m.group(0)
            log.debug('Perfect hit. Search got redirected to %s' % actual_url)
            movie = {}
            movie['match'] = 1.0
            movie['name'] = name
            movie['imdb_id'] = extract_id(actual_url)
            movie['url'] = make_url(movie['imdb_id'])
            movie['year'] = None  # skips year check
            movies.append(movie)
            return movies

        # the god damn page has declared a wrong encoding
        soup = get_soup(page.text)

        section_table = soup.find('table', 'findList')
        if not section_table:
            log.debug('results table not found')
            return

        rows = section_table.find_all('td', 'result_text')
        if not rows:
            log.debug('Titles section does not have links')
        for count, row in enumerate(rows):
            # Title search gives a lot of results, only check the first ones
            if count > self.max_results:
                break

            movie = {}
            additional = re.findall(r'\((.*?)\)', row.text)
            if len(additional) > 0:
                if re.match('^\d{4}$', additional[-1]):
                    movie['year'] = additional[-1]
                elif len(additional) > 1:
                    movie['year'] = additional[-2]
                    if additional[-1] not in ['TV Movie', 'Video']:
                        log.debug('skipping %s', row.text)
                        break

            link = row.find_next('a')
            movie['name'] = link.text
            movie['imdb_id'] = extract_id(link.get('href'))
            movie['url'] = make_url(movie['imdb_id'])
            log.debug('processing name: %s url: %s' % (movie['name'], movie['url']))

            # calc & set best matching ratio
            seq = difflib.SequenceMatcher(lambda x: x == ' ', movie['name'].title(), name.title())
            ratio = seq.ratio()

            # check if some of the akas have better ratio
            for aka in link.parent.find_all('i'):
                aka = aka.next.string
                match = re.search(r'".*"', aka)
                if not match:
                    log.debug('aka `%s` is invalid' % aka)
                    continue
                aka = match.group(0).replace('"', '')
                log.trace('processing aka %s' % aka)
                seq = difflib.SequenceMatcher(lambda x: x == ' ', aka.title(), name.title())
                aka_ratio = seq.ratio()
                if aka_ratio > ratio:
                    ratio = aka_ratio * self.aka_weight
                    log.debug('- aka `%s` matches better to `%s` ratio %s (weighted to %s)' %
                              (aka, name, aka_ratio, ratio))

            # prioritize items by position
            position_ratio = (self.first_weight - 1) / (count + 1) + 1
            log.debug('- prioritizing based on position %s `%s`: %s' % (count, movie['url'], position_ratio))
            ratio *= position_ratio

            # store ratio
            movie['match'] = ratio
            movies.append(movie)

        movies.sort(key=lambda x: x['match'], reverse=True)
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
        self.original_name = None
        self.url = None
        self.imdb_id = None
        self.photo = None
        self.mpaa_rating = ''

    def __str__(self):
        return '<ImdbParser(name=%s,imdb_id=%s)>' % (self.name, self.imdb_id)

    def parse(self, imdb_id):
        self.imdb_id = extract_id(imdb_id)
        url = make_url(self.imdb_id)
        self.url = url
        page = requests.get(url)
        soup = get_soup(page.text)

        title_overview = soup.find('div', attrs={'class': 'title-overview'})
        if not title_overview:
            raise PluginError('IMDB parser needs updating, imdb format changed. Please report on Github.')

        # Parse stuff from the title-overview section
        name_elem = title_overview.find('h1', attrs={'itemprop': 'name'})
        if name_elem:
            self.name = name_elem.contents[0].strip()
        else:
            log.error('Possible IMDB parser needs updating, Please report on Github.')
            raise PluginError('Unable to set imdb_name for %s from %s' % (self.imdb_id, self.url))

        year = title_overview.find('span', attrs={'id': 'titleYear'})
        if year:
            m = re.search(r'([0-9]{4})', year.text)
            if m:
                self.year = int(m.group(1))

        if not self.year:
            log.debug('No year found for %s' % self.imdb_id)

        mpaa_rating_elem = title_overview.find(itemprop='contentRating')
        if mpaa_rating_elem:
            self.mpaa_rating = mpaa_rating_elem['content']
        else:
            log.debug('No rating found for %s' % self.imdb_id)

        photo_elem = title_overview.find(itemprop='image')
        if photo_elem:
            self.photo = photo_elem['src']
        else:
            log.debug('No photo found for %s' % self.imdb_id)

        original_name_elem = title_overview.find(attrs={'class': 'originalTitle'})
        if original_name_elem:
            self.original_name = original_name_elem.contents[0].strip().strip('"')
        else:
            log.debug('No original title found for %s' % self.imdb_id)

        votes_elem = title_overview.find(itemprop='ratingCount')
        if votes_elem:
            self.votes = str_to_int(votes_elem.text)
        else:
            log.debug('No votes found for %s' % self.imdb_id)

        score_elem = title_overview.find(itemprop='ratingValue')
        if score_elem:
            self.score = float(score_elem.text)
        else:
            log.debug('No score found for %s' % self.imdb_id)

        # get director(s)
        for director in title_overview.select('[itemprop="director"] > a'):
            director_id = extract_id(director['href'])
            director_name = director.text
            # tag instead of name
            if isinstance(director_name, Tag):
                director_name = None
            self.directors[director_id] = director_name

        # Details section
        title_details = soup.find('div', attrs={'id': 'titleDetails'})
        if title_details:
            # get languages
            for link in title_details.find_all('a', href=re.compile('/language/')):
                lang = link.text.strip().lower()
                if lang not in self.languages:
                    self.languages.append(lang.strip())

        # Storyline section
        storyline = soup.find('div', attrs={'id': 'titleStoryLine'})
        if storyline:
            plot_elem = storyline.find('p')
            if plot_elem:
                # Remove the "Written By" part.
                if plot_elem.em:
                    plot_elem.em.replace_with('')
                self.plot_outline = plot_elem.text.strip()
            else:
                log.debug('No storyline found for %s' % self.imdb_id)
            self.genres = [i.text.strip().lower() for i in storyline.select('[itemprop="genre"] > a')]

        # Cast section
        cast = soup.find('div', attrs={'id': 'titleCast'})
        if cast:
            for actor in cast.select('[itemprop="actor"] > a'):
                actor_id = extract_id(actor['href'])
                actor_name = actor.text.strip()
                # tag instead of name
                if isinstance(actor_name, Tag):
                    actor_name = None
                self.actors[actor_id] = actor_name
