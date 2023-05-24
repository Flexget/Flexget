from datetime import datetime

from loguru import logger

from flexget import plugin
from flexget.components.imdb.utils import ImdbParser, ImdbSearch, extract_id, make_url
from flexget.entry import Entry, register_lazy_lookup
from flexget.event import event
from flexget.utils.database import with_session
from flexget.utils.log import log_once

from . import db

logger = logger.bind(name='imdb_lookup')


class ImdbLookup:
    """
    Retrieves imdb information for entries.
    Also provides imdb lookup functionality to all other imdb related plugins.

    Example::

        imdb_lookup: yes
    """

    field_map = {
        'imdb_url': 'url',
        'imdb_id': lambda movie: extract_id(movie.url),
        'imdb_name': 'title',
        'imdb_original_name': 'original_title',
        'imdb_photo': 'photo',
        'imdb_plot_outline': 'plot_outline',
        'imdb_score': 'score',
        'imdb_votes': 'votes',
        'imdb_meta_score': 'meta_score',
        'imdb_year': 'year',
        'imdb_genres': lambda movie: [genre.name for genre in movie.genres],
        'imdb_languages': lambda movie: [lang.language.name for lang in movie.languages],
        'imdb_actors': lambda movie: {actor.imdb_id: actor.name for actor in movie.actors},
        'imdb_directors': lambda movie: {
            director.imdb_id: director.name for director in movie.directors
        },
        'imdb_writers': lambda movie: {writer.imdb_id: writer.name for writer in movie.writers},
        'imdb_mpaa_rating': 'mpaa_rating',
        'imdb_plot_keywords': lambda movie: [
            plot_keyword.name for plot_keyword in movie.plot_keywords
        ],
        # Generic fields filled by all movie lookup plugins:
        'movie_name': 'title',
        'movie_year': 'year',
    }

    schema = {'type': 'boolean'}

    @plugin.priority(130)
    def on_task_metainfo(self, task, config):
        if not config:
            return
        for entry in task.entries:
            entry.add_lazy_fields(self.lazy_loader, self.field_map)

    @register_lazy_lookup('imdb_lookup')
    def lazy_loader(self, entry):
        """Does the lookup for this entry and populates the entry fields."""
        try:
            self.lookup(entry)
        except plugin.PluginError as e:
            log_once(str(e.value).capitalize(), logger=logger)

    @with_session
    def imdb_id_lookup(self, movie_title=None, movie_year=None, raw_title=None, session=None):
        """
        Perform faster lookup providing just imdb_id.
        Falls back to using basic lookup if data cannot be found from cache.

        .. note::

           API will be changed, it's dumb to return None on errors AND
           raise PluginError on some else

        :param movie_title: Name of the movie
        :param raw_title: Raw entry title
        :return: imdb id or None
        :raises PluginError: Failure reason
        """
        if movie_title:
            logger.debug('imdb_id_lookup: trying with title: {}', movie_title)
            query = session.query(db.Movie).filter(db.Movie.title == movie_title)
            if movie_year is not None:
                query = query.filter(db.Movie.year == movie_year)
            movie = query.first()
            if movie:
                logger.debug('--> success! got {} returning {}', movie, movie.imdb_id)
                return movie.imdb_id
        if raw_title:
            logger.debug('imdb_id_lookup: trying cache with: {}', raw_title)
            result = (
                session.query(db.SearchResult).filter(db.SearchResult.title == raw_title).first()
            )
            if result:
                # this title is hopeless, give up ..
                if result.fails:
                    return None
                logger.debug('--> success! got {} returning {}', result, result.imdb_id)
                return result.imdb_id
        if raw_title:
            # last hope with hacky lookup
            fake_entry = Entry(raw_title, '')
            self.lookup(fake_entry)
            return fake_entry['imdb_id']

    @plugin.internet(logger)
    @with_session
    def lookup(self, entry, search_allowed=True, session=None):
        """
        Perform imdb lookup for entry.

        :param entry: Entry instance
        :param search_allowed: Allow fallback to search
        :raises PluginError: Failure reason
        """

        from flexget.manager import manager

        if entry.get('imdb_id', eval_lazy=False):
            logger.debug('No title passed. Lookup for {}', entry['imdb_id'])
        elif entry.get('imdb_url', eval_lazy=False):
            logger.debug('No title passed. Lookup for {}', entry['imdb_url'])
        elif entry.get('title', eval_lazy=False):
            logger.debug('lookup for {}', entry['title'])
        else:
            raise plugin.PluginError(
                'looking up IMDB for entry failed, no title, imdb_url or imdb_id passed.'
            )

        # if imdb_id is included, build the url.
        if entry.get('imdb_id', eval_lazy=False) and not entry.get('imdb_url', eval_lazy=False):
            entry['imdb_url'] = make_url(entry['imdb_id'])

        # make sure imdb url is valid
        if entry.get('imdb_url', eval_lazy=False):
            imdb_id = extract_id(entry['imdb_url'])
            if imdb_id:
                entry['imdb_url'] = make_url(imdb_id)
            else:
                logger.debug('imdb url {} is invalid, removing it', entry['imdb_url'])
                entry['imdb_url'] = ''

        # no imdb_url, check if there is cached result for it or if the
        # search is known to fail
        if not entry.get('imdb_url', eval_lazy=False):
            result = (
                session.query(db.SearchResult)
                .filter(db.SearchResult.title == entry['title'])
                .first()
            )
            if result:
                # TODO: 1.2 this should really be checking task.options.retry
                if result.fails and not manager.options.execute.retry:
                    # this movie cannot be found, not worth trying again ...
                    logger.debug('{} will fail lookup', entry['title'])
                    raise plugin.PluginError('IMDB lookup failed for %s' % entry['title'])
                else:
                    if result.url:
                        logger.trace('Setting imdb url for {} from db', entry['title'])
                        entry['imdb_id'] = result.imdb_id
                        entry['imdb_url'] = result.url

        # no imdb url, but information required, try searching
        if not entry.get('imdb_url', eval_lazy=False) and search_allowed:
            logger.verbose('Searching from imdb `{}`', entry['title'])
            search = ImdbSearch()
            search_name = entry.get('movie_name', entry['title'], eval_lazy=False)
            search_result = search.smart_match(search_name)
            if search_result:
                entry['imdb_url'] = search_result['url']
                # store url for this movie, so we don't have to search on every run
                result = db.SearchResult(entry['title'], entry['imdb_url'])
                session.add(result)
                session.commit()
                logger.verbose('Found {}', entry['imdb_url'])
            else:
                log_once(
                    'IMDB lookup failed for %s' % entry['title'],
                    logger,
                    'WARNING',
                    session=session,
                )
                # store FAIL for this title
                result = db.SearchResult(entry['title'])
                result.fails = True
                session.add(result)
                session.commit()
                raise plugin.PluginError('Title `%s` lookup failed' % entry['title'])

        # check if this imdb page has been parsed & cached
        movie = session.query(db.Movie).filter(db.Movie.url == entry['imdb_url']).first()

        # If we have a movie from cache, we are done
        if movie and not movie.expired:
            entry.update_using_map(self.field_map, movie)
            return

        # Movie was not found in cache, or was expired
        if movie is not None:
            if movie.expired:
                logger.verbose('Movie `{}` details expired, refreshing ...', movie.title)
            # Remove the old movie, we'll store another one later.
            session.query(db.MovieLanguage).filter(db.MovieLanguage.movie_id == movie.id).delete()
            session.query(db.Movie).filter(db.Movie.url == entry['imdb_url']).delete()
            session.commit()

        # search and store to cache
        if 'title' in entry:
            logger.verbose('Parsing imdb for `{}`', entry['title'])
        else:
            logger.verbose('Parsing imdb for `{}`', entry['imdb_id'])
        try:
            movie = self._parse_new_movie(entry['imdb_url'], session)
        except UnicodeDecodeError:
            logger.error(
                'Unable to determine encoding for {}. Installing chardet library may help.',
                entry['imdb_url'],
            )
            # store cache so this will not be tried again
            movie = db.Movie()
            movie.url = entry['imdb_url']
            session.add(movie)
            session.commit()
            raise plugin.PluginError('UnicodeDecodeError')
        except ValueError as e:
            # TODO: might be a little too broad catch, what was this for anyway? ;P
            if manager.options.debug:
                logger.exception(e)
            raise plugin.PluginError('Invalid parameter: %s' % entry['imdb_url'], logger)

        for att in [
            'title',
            'score',
            'votes',
            'meta_score',
            'year',
            'genres',
            'languages',
            'actors',
            'directors',
            'writers',
            'mpaa_rating',
        ]:
            logger.trace('movie.{}: {}', att, getattr(movie, att))

        # Update the entry fields
        entry.update_using_map(self.field_map, movie)

    def _parse_new_movie(self, imdb_url, session):
        """
        Get Movie object by parsing imdb page and save movie into the database.

        :param imdb_url: IMDB url
        :param session: Session to be used
        :return: Newly added Movie
        """
        parser = ImdbParser()
        parser.parse(imdb_url)
        # store to database
        movie = db.Movie()
        movie.photo = parser.photo
        movie.title = parser.name
        movie.original_title = parser.original_name
        movie.score = parser.score
        movie.votes = parser.votes
        movie.meta_score = parser.meta_score
        movie.year = parser.year
        movie.mpaa_rating = parser.mpaa_rating
        movie.plot_outline = parser.plot_outline
        movie.url = imdb_url
        for name in parser.genres:
            genre = session.query(db.Genre).filter(db.Genre.name == name).first()
            if not genre:
                genre = db.Genre(name)
            movie.genres.append(genre)  # pylint:disable=E1101
        for index, name in enumerate(parser.languages):
            language = session.query(db.Language).filter(db.Language.name == name).first()
            if not language:
                language = db.Language(name)
            movie.languages.append(db.MovieLanguage(language, prominence=index))
        for imdb_id, name in parser.actors.items():
            actor = session.query(db.Actor).filter(db.Actor.imdb_id == imdb_id).first()
            if not actor:
                actor = db.Actor(imdb_id, name)
            movie.actors.append(actor)  # pylint:disable=E1101
        for imdb_id, name in parser.directors.items():
            director = session.query(db.Director).filter(db.Director.imdb_id == imdb_id).first()
            if not director:
                director = db.Director(imdb_id, name)
            movie.directors.append(director)  # pylint:disable=E1101
        for imdb_id, name in parser.writers.items():
            writer = session.query(db.Writer).filter(db.Writer.imdb_id == imdb_id).first()
            if not writer:
                writer = db.Writer(imdb_id, name)
            movie.writers.append(writer)  # pylint:disable=E1101
        for name in parser.plot_keywords:
            plot_keyword = (
                session.query(db.PlotKeyword).filter(db.PlotKeyword.name == name).first()
            )
            if not plot_keyword:
                plot_keyword = db.PlotKeyword(name)
            movie.plot_keywords.append(plot_keyword)  # pylint:disable=E1101
        # so that we can track how long since we've updated the info later
        movie.updated = datetime.now()
        session.add(movie)
        return movie

    @property
    def movie_identifier(self):
        """Returns the plugin main identifier type"""
        return 'imdb_id'


@event('plugin.register')
def register_plugin():
    plugin.register(ImdbLookup, 'imdb_lookup', api_ver=2, interfaces=['task', 'movie_metainfo'])
