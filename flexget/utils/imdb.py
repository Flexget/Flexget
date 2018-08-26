from __future__ import unicode_literals, division, absolute_import
from builtins import *  # noqa pylint: disable=unused-import, redefined-builtin
from past.builtins import basestring

import difflib
import json
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


def is_valid_imdb_title_id(value):
    """
    Return True if `value` is a valid IMDB ID for titles (movies, series, etc).
    """
    if not isinstance(value, basestring):
        raise TypeError("is_valid_imdb_title_id expects a string but got {0}".format(type(value)))
    # IMDB IDs for titles have 'tt' followed by 7 digits
    return re.match('tt[\d]{7}', value) is not None


def is_valid_imdb_person_id(value):
    """
    Return True if `value` is a valid IMDB ID for a person.
    """
    if not isinstance(value, basestring):
        raise TypeError("is_valid_imdb_person_id expects a string but got {0}".format(type(value)))
    # An IMDB ID for a person is formed by 'nm' followed by 7 digits
    return re.match('nm[\d]{7}', value) is not None


def extract_id(url):
    """Return IMDb ID of the given URL. Return None if not valid or if URL is not a string."""
    if not isinstance(url, basestring):
        return
    m = re.search(r'((?:nm|tt)[\d]{7})', url)
    if m:
        return m.group(1)


def make_url(imdb_id):
    """Return IMDb URL of the given ID"""
    return u'https://www.imdb.com/title/%s/' % imdb_id


class ImdbSearch(object):
    def __init__(self):
        # de-prioritize aka matches a bit
        self.aka_weight = 0.95
        # prioritize first
        self.first_weight = 1.1
        self.min_match = 0.7
        self.min_diff = 0.01
        self.debug = False

        self.max_results = 50

    def ireplace(self, text, old, new, count=0):
        """Case insensitive string replace"""
        pattern = re.compile(re.escape(old), re.I)
        return re.sub(pattern, new, text, count)

    def smart_match(self, raw_name, single_match=True):
        """Accepts messy name, cleans it and uses information available to make smartest and best match"""
        parser = get_plugin_by_name('parsing').instance.parse_movie(raw_name)
        name = parser.name
        year = parser.year
        if name == '':
            log.critical('Failed to parse name from %s', raw_name)
            return None
        log.debug('smart_match name=%s year=%s' % (name, str(year)))
        return self.best_match(name, year, single_match)

    def best_match(self, name, year=None, single_match=True):
        """Return single movie that best matches name criteria or None"""
        movies = self.search(name)

        if not movies:
            log.debug('search did not return any movies')
            return None

        # remove all movies below min_match, and different year
        for movie in movies[:]:
            if year and movie.get('year'):
                if movie['year'] != year:
                    log.debug('best_match removing %s - %s (wrong year: %s)' % (
                        movie['name'],
                        movie['url'],
                        str(movie['year'])))
                    movies.remove(movie)
                    continue
            if movie['match'] < self.min_match:
                log.debug('best_match removing %s (min_match)', movie['name'])
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
            return movies[0] if single_match else movies

    def search(self, name):
        """Return array of movie details (dict)"""
        log.debug('Searching: %s', name)
        url = u'https://www.imdb.com/find'
        # This may include Shorts and TV series in the results
        params = {'q': name, 's': 'tt', }

        log.debug('Search query: %s', repr(url))
        page = requests.get(url, params=params)
        actual_url = page.url

        movies = []
        soup = get_soup(page.text)
        # in case we got redirected to movie page (perfect match)
        re_m = re.match(r'.*\.imdb\.com/title/tt\d+/', actual_url)
        if re_m:
            actual_url = re_m.group(0)
            imdb_id = extract_id(actual_url)
            movie_parse = ImdbParser()
            movie_parse.parse(imdb_id, soup=soup)
            log.debug('Perfect hit. Search got redirected to %s', actual_url)
            movie = {
                'match': 1.0,
                'name': movie_parse.name,
                'imdb_id': imdb_id,
                'url': make_url(imdb_id),
                'year': movie_parse.year
            }
            movies.append(movie)
            return movies

        section_table = soup.find('table', 'findList')
        if not section_table:
            log.debug('results table not found')
            return

        rows = section_table.find_all('tr')
        if not rows:
            log.debug('Titles section does not have links')
        for count, row in enumerate(rows):
            # Title search gives a lot of results, only check the first ones
            if count > self.max_results:
                break

            result_text = row.find('td', 'result_text')
            movie = {}
            additional = re.findall(r'\((.*?)\)', result_text.text)
            if len(additional) > 0:
                if re.match('^\d{4}$', additional[-1]):
                    movie['year'] = str_to_int(additional[-1])
                elif len(additional) > 1:
                    movie['year'] = str_to_int(additional[-2])
                    if additional[-1] not in ['TV Movie', 'Video']:
                        log.debug('skipping %s', result_text.text)
                        continue
            primary_photo = row.find('td', 'primary_photo')
            movie['thumbnail'] = primary_photo.find('a').find('img').get('src')

            link = result_text.find_next('a')
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
        self.writers = {}
        self.score = 0.0
        self.votes = 0
        self.meta_score = 0
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

    def parse(self, imdb_id, soup=None):
        self.imdb_id = extract_id(imdb_id)
        url = make_url(self.imdb_id)
        self.url = url

        if not soup:
            page = requests.get(url)
            soup = get_soup(page.text)

        title_wrapper = soup.find('div', attrs={'class': 'title_wrapper'})

        data = json.loads(soup.find('script', {'type': 'application/ld+json'}).text)

        if not data:
            raise PluginError('IMDB parser needs updating, imdb format changed. Please report on Github.')

        # Parse stuff from the title-overview section
        name_elem = data['name']
        if name_elem:
            self.name = name_elem.strip()
        else:
            log.error('Possible IMDB parser needs updating, Please report on Github.')
            raise PluginError('Unable to set imdb_name for %s from %s' % (self.imdb_id, self.url))

        year = soup.find('span', attrs={'id': 'titleYear'})
        if year:
            m = re.search(r'([0-9]{4})', year.text)
            if m:
                self.year = int(m.group(1))

        if not self.year:
            log.debug('No year found for %s', self.imdb_id)

        mpaa_rating_elem = data.get('contentRating')
        if mpaa_rating_elem:
            self.mpaa_rating = mpaa_rating_elem
        else:
            log.debug('No rating found for %s', self.imdb_id)

        photo_elem = data.get('image')
        if photo_elem:
            self.photo = photo_elem
        else:
            log.debug('No photo found for %s', self.imdb_id)

        original_name_elem = title_wrapper.find('div', {'class': 'originalTitle'})
        if original_name_elem:
            self.name = title_wrapper.find('h1').contents[0].strip()
            self.original_name = original_name_elem.contents[0].strip().strip('"')
        else:
            log.debug('No original title found for %s', self.imdb_id)

        votes_elem = data.get('aggregateRating', {}).get('ratingCount')
        if votes_elem:
            self.votes = str_to_int(votes_elem) if not isinstance(votes_elem, int) else votes_elem
        else:
            log.debug('No votes found for %s', self.imdb_id)

        score_elem = data.get('aggregateRating', {}).get('ratingValue')
        if score_elem:
            self.score = float(score_elem)
        else:
            log.debug('No score found for %s', self.imdb_id)

        meta_score_elem = soup.find(attrs={'class': 'metacriticScore'})
        if meta_score_elem:
            self.meta_score = str_to_int(meta_score_elem.text)
        else:
            log.debug('No Metacritic score found for %s', self.imdb_id)

        # get director(s)
        directors = data.get('director', [])
        if not isinstance(directors, list):
            directors = [directors]

        for director in directors:
            if director['@type'] != 'Person':
                continue
            director_id = extract_id(director['url'])
            director_name = director['name']
            self.directors[director_id] = director_name

        # get writer(s)
        writers = data.get('creator', [])
        if not isinstance(writers, list):
            writers = [writers]

        for writer in writers:
            if writer['@type'] != 'Person':
                continue
            writer_id = extract_id(writer['url'])
            writer_name = writer['name']
            self.writers[writer_id] = writer_name

        # Details section
        title_details = soup.find('div', attrs={'id': 'titleDetails'})
        if title_details:
            # get languages
            for link in title_details.find_all('a', href=re.compile('^/search/title\?title_type=feature'
                                                                    '&primary_language=')):
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
                log.debug('No storyline found for %s', self.imdb_id)

        genres = data.get('genre', [])
        if not isinstance(genres, list):
            genres = [genres]

        self.genres = [g.strip().lower() for g in genres]

        # Cast section
        cast = soup.find('table', attrs={'class': 'cast_list'})
        if cast:
            for actor in cast.select('tr > td:nth-of-type(2) > a'):
                actor_id = extract_id(actor['href'])
                actor_name = actor.text.strip()
                # tag instead of name
                if isinstance(actor_name, Tag):
                    actor_name = None
                self.actors[actor_id] = actor_name
