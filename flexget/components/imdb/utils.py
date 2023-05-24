import difflib
import json
import random
import re
from urllib.parse import quote

from loguru import logger

from flexget import plugin
from flexget.utils.requests import Session, TimedLimiter
from flexget.utils.soup import get_soup
from flexget.utils.tools import str_to_int

logger = logger.bind(name='imdb.utils')

requests = Session()
# Declare browser user agent to avoid being classified as a bot and getting a 403
requests.headers.update(
    {'User-Agent': 'Mozilla/5.0 (Windows NT 6.1; Win64; x64; rv:47.0) Gecko/20100101 Firefox/47.0'}
)
# requests.headers.update({'User-Agent': random.choice(USERAGENTS)})

# this makes most of the titles to be returned in english translation, but not all of them
requests.headers.update({'Accept-Language': 'en-US,en;q=0.8'})
requests.headers.update(
    {'X-Forwarded-For': '24.110.%d.%d' % (random.randint(0, 254), random.randint(0, 254))}
)

# give imdb a little break between requests (see: http://flexget.com/ticket/129#comment:1)
requests.add_domain_limiter(TimedLimiter('imdb.com', '3 seconds'))


def is_imdb_url(url):
    """Tests the url to see if it's for imdb.com."""
    if not isinstance(url, str):
        return
    # Probably should use urlparse.
    return re.match(r'https?://[^/]*imdb\.com/', url)


def is_valid_imdb_title_id(value):
    """
    Return True if `value` is a valid IMDB ID for titles (movies, series, etc).
    """
    if not isinstance(value, str):
        raise TypeError(f"is_valid_imdb_title_id expects a string but got {type(value)}")
    # IMDB IDs for titles have 'tt' followed by 7 or 8 digits
    return re.match(r'tt\d{7,8}', value) is not None


def is_valid_imdb_person_id(value):
    """
    Return True if `value` is a valid IMDB ID for a person.
    """
    if not isinstance(value, str):
        raise TypeError(f"is_valid_imdb_person_id expects a string but got {type(value)}")
    # An IMDB ID for a person is formed by 'nm' followed by 7 digits
    return re.match(r'nm\d{7,8}', value) is not None


def extract_id(url):
    """Return IMDb ID of the given URL. Return None if not valid or if URL is not a string."""
    if not isinstance(url, str):
        return
    m = re.search(r'((?:nm|tt)\d{7,8})', url)
    if m:
        return m.group(1)


def make_url(imdb_id):
    """Return IMDb URL of the given ID"""
    return 'https://www.imdb.com/title/%s/' % imdb_id


class ImdbSearch:
    def __init__(self):
        # de-prioritize aka matches a bit
        self.aka_weight = 0.95
        # prioritize first
        self.first_weight = 1.5
        self.min_match = 0.6
        self.min_diff = 0.01
        self.debug = False

        self.max_results = 50

    def ireplace(self, text, old, new, count=0):
        """Case insensitive string replace"""
        pattern = re.compile(re.escape(old), re.I)
        return re.sub(pattern, new, text, count)

    def smart_match(self, raw_name, single_match=True):
        """Accepts messy name, cleans it and uses information available to make smartest and best match"""
        parser = plugin.get('parsing', 'imdb_search').parse_movie(raw_name)
        name = parser.name
        year = parser.year
        if not name:
            logger.critical('Failed to parse name from {}', raw_name)
            return None
        logger.debug('smart_match name={} year={}', name, str(year))
        return self.best_match(name, year, single_match)

    def best_match(self, name, year=None, single_match=True):
        """Return single movie that best matches name criteria or None"""
        movies = self.search(name, year)

        if not movies:
            logger.debug('search did not return any movies')
            return None

        # remove all movies below min_match, and different year
        exact = []

        for movie in movies[:]:
            if year and movie.get('year'):
                if movie['year'] != year:
                    logger.debug(
                        'best_match removing {} - {} (wrong year: {})',
                        movie['name'],
                        movie['url'],
                        str(movie['year']),
                    )
                    movies.remove(movie)
                    continue
                # Look for exact match
                if movie['year'] == year and movie['name'].lower() == name.lower():
                    exact.append(movie)
            if movie['match'] < self.min_match:
                logger.debug('best_match removing {} (min_match)', movie['name'])
                movies.remove(movie)
                continue

        if not movies:
            logger.debug('FAILURE: no movies remain')
            return None

        # If we have 1 exact match
        if len(exact) == 1:
            logger.debug('SUCCESS: found exact movie match')
            return exact[0]

        # if only one remains ..
        if len(movies) == 1:
            logger.debug('SUCCESS: only one movie remains')
            return movies[0]

        # check min difference between best two hits
        diff = movies[0]['match'] - movies[1]['match']
        if diff < self.min_diff:
            logger.debug(
                'unable to determine correct movie, min_diff too small (`{}` <-?-> `{}`)',
                movies[0],
                movies[1],
            )
            for m in movies:
                logger.debug('remain: {} (match: {}) {}', m['name'], m['match'], m['url'])
            return None
        else:
            return movies[0] if single_match else movies

    def search(self, name, year=None):
        """Return array of movie details (dict)"""
        logger.debug('Searching: {}', name)
        # This may include Shorts and TV series in the results
        # It is using the live search suggestions api that populates movies as you type in the search bar
        search_imdb_id = extract_id(name)
        search = name
        # Adding the year to the search normally improves the results, except in the case that the
        # title of the movie is a number e.g. 1917 (2009)
        if year and not name.isdigit():
            search += f" {year}"
        url = f'https://v3.sg.media-imdb.com/suggestion/titles/x/{quote(search, safe="")}.json'
        params = {'includeVideos': 0}

        logger.debug('Search query: {}', repr(url))
        page = requests.get(url, params=params)
        rows = page.json()['d']

        movies = []

        for count, result in enumerate(rows):
            # Title search gives a lot of results, only check the first ones
            if count > self.max_results:
                break

            if result['qid'] not in ['tvMovie', 'movie', 'video']:
                logger.debug('skipping {}', result['l'])
                continue

            movie = {
                'name': result['l'],
                'year': result.get('y'),
                'imdb_id': result['id'],
                'url': make_url(result['id']),
                'thumbnail': result.get('i', {}).get('imageUrl'),
            }
            if search_imdb_id and movie['imdb_id'] == search_imdb_id:
                movie['match'] = 1.0
                return [movie]
            logger.debug('processing name: {} url: {}', movie['name'], movie['url'])

            # calc & set best matching ratio
            seq = difflib.SequenceMatcher(lambda x: x == ' ', movie['name'].title(), name.title())
            ratio = seq.ratio()

            # prioritize items by position
            position_ratio = (self.first_weight - 1) / (count + 1) + 1
            logger.debug(
                '- prioritizing based on position {} `{}`: {}', count, movie['url'], position_ratio
            )
            ratio *= position_ratio

            # store ratio
            movie['match'] = ratio
            movies.append(movie)

        movies.sort(key=lambda x: x['match'], reverse=True)
        return movies


class ImdbParser:
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
        self.plot_keywords = []

    def __str__(self):
        return f'<ImdbParser(name={self.name},imdb_id={self.imdb_id})>'

    def parse(self, imdb_id, soup=None):
        self.imdb_id = extract_id(imdb_id)
        url = make_url(self.imdb_id)
        self.url = url

        if not soup:
            page = requests.get(url)
            soup = get_soup(page.text)

        data = json.loads(soup.find('script', {'type': 'application/ld+json'}).string)
        if not data:
            raise plugin.PluginError(
                'IMDB parser needs updating, imdb format changed. Please report on Github.'
            )

        props_data = json.loads(soup.find('script', {'type': 'application/json'}).string)
        if (
            not props_data
            or not props_data.get('props')
            or not props_data.get('props').get('pageProps')
        ):
            raise plugin.PluginError(
                'IMDB parser needs updating, imdb props_data format changed. Please report on Github.'
            )

        above_the_fold_data = props_data['props']['pageProps'].get('aboveTheFoldData')
        if not above_the_fold_data:
            raise plugin.PluginError(
                'IMDB parser needs updating, imdb above_the_fold_data format changed. Please report on Github.'
            )

        title = above_the_fold_data.get('titleText')
        if title:
            self.name = title.get('text')
        if not self.name:
            raise plugin.PluginError(
                'IMDB parser needs updating, imdb above_the_fold_data format changed for title. Please report on Github.'
            )

        original_name = above_the_fold_data.get('originalTitleText')
        if original_name:
            self.original_name = original_name.get('text')

        if not self.original_name:
            logger.debug('No original title found for {}', self.imdb_id)

        # NOTE: We cannot use the get default approach here .(get(x, {}))
        # as the data returned in imdb has all fields with null values if they do not exist.
        if above_the_fold_data.get('releaseYear'):
            self.year = above_the_fold_data['releaseYear'].get('year')
        if not self.year:
            logger.debug('No year found for {}', self.imdb_id)

        self.mpaa_rating = data.get('contentRating')
        if not self.mpaa_rating:
            logger.debug('No rating found for {}', self.imdb_id)

        self.photo = data.get('image')
        if not self.photo:
            logger.debug('No photo found for {}', self.imdb_id)

        rating_data = data.get('aggregateRating')
        if rating_data:
            rating_count = rating_data.get('ratingCount')
            if rating_count:
                self.votes = (
                    str_to_int(rating_count) if not isinstance(rating_count, int) else rating_count
                )
            else:
                logger.debug('No votes found for {}', self.imdb_id)

            score = rating_data.get('ratingValue')
            if score:
                self.score = float(score)
            else:
                logger.debug('No score found for {}', self.imdb_id)

        meta_critic = above_the_fold_data.get('metacritic')
        if meta_critic:
            meta_score = meta_critic.get('metascore')
            if meta_score:
                self.meta_score = meta_score.get('score')
        if not self.meta_score:
            logger.debug('No Metacritic score found for {}', self.imdb_id)

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
        main_column_data = props_data['props']['pageProps'].get('mainColumnData')
        if not main_column_data:
            raise plugin.PluginError(
                'IMDB parser needs updating, imdb main_column_data format changed. Please report on Github.'
            )

        for language in (main_column_data.get('spokenLanguages') or {}).get('spokenLanguages', []):
            self.languages.append(language['text'].lower())

        # Storyline section
        # NOTE: We cannot use the get default approach here .(get(x, {}))
        # as the data returned in imdb has all fields with null values if they do not exist.
        plot = above_the_fold_data['plot'] or {}
        plot_text = plot.get('plotText') or {}
        plot_plain_text = plot_text.get('plainText')
        if plot_plain_text:
            self.plot_outline = plot_plain_text
        if not self.plot_outline:
            logger.debug('No storyline found for {}', self.imdb_id)

        storyline_keywords = data.get('keywords') or ''
        if storyline_keywords:
            self.plot_keywords = storyline_keywords.split(',')

        genres = (above_the_fold_data.get('genres', {}) or {}).get('genres', [])
        self.genres = [g['text'].lower() for g in genres]

        # Cast section
        cast_data = main_column_data.get('cast', {}) or {}
        for cast_node in cast_data.get('edges') or []:
            actor_node = (cast_node.get('node') or {}).get('name') or {}
            actor_id = actor_node.get('id')
            actor_name = (actor_node.get('nameText') or {}).get('text')
            if actor_id and actor_name:
                self.actors[actor_id] = actor_name

        principal_cast_data = main_column_data.get('principalCast', []) or []
        if principal_cast_data:
            for cast_node in principal_cast_data[0].get('credits') or []:
                actor_node = cast_node.get('name') or {}
                actor_id = actor_node.get('id')
                actor_name = (actor_node.get('nameText') or {}).get('text')
                if actor_id and actor_name:
                    self.actors[actor_id] = actor_name
