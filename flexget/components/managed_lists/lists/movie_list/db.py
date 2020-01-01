from datetime import datetime

from loguru import logger
from sqlalchemy import Column, DateTime, ForeignKey, Integer, Unicode, func
from sqlalchemy.orm import relationship
from sqlalchemy.sql.elements import and_

from flexget import plugin
from flexget.db_schema import versioned_base, with_session
from flexget.entry import Entry

try:
    # NOTE: Importing other plugins is discouraged!
    from flexget.components.parsing.parsers import parser_common as plugin_parser_common
except ImportError:
    raise plugin.DependencyError(issued_by=__name__, missing='parser_common')

logger = logger.bind(name='movie_list')
Base = versioned_base('movie_list', 0)


class MovieListBase:
    """
    Class that contains helper methods for movie list as well as plugins that use it,
    such as API and CLI.
    """

    @property
    def supported_ids(self):
        # Return a list of supported series identifier as registered via their plugins
        return [
            p.instance.movie_identifier for p in plugin.get_plugins(interface='movie_metainfo')
        ]


class MovieListList(Base):
    __tablename__ = 'movie_list_lists'
    id = Column(Integer, primary_key=True)
    name = Column(Unicode, unique=True)
    added = Column(DateTime, default=datetime.now)
    movies = relationship(
        'MovieListMovie', backref='list', cascade='all, delete, delete-orphan', lazy='dynamic'
    )

    def __repr__(self):
        return '<MovieListList,name={}id={}>'.format(self.name, self.id)

    def to_dict(self):
        return {'id': self.id, 'name': self.name, 'added_on': self.added}


class MovieListMovie(Base):
    __tablename__ = 'movie_list_movies'
    id = Column(Integer, primary_key=True)
    added = Column(DateTime, default=datetime.now)
    title = Column(Unicode)
    year = Column(Integer)
    list_id = Column(Integer, ForeignKey(MovieListList.id), nullable=False)
    ids = relationship('MovieListID', backref='movie', cascade='all, delete, delete-orphan')

    def __repr__(self):
        return '<MovieListMovie title=%s,year=%s,list_id=%d>' % (
            self.title,
            self.year,
            self.list_id,
        )

    def to_entry(self, strip_year=False):
        entry = Entry()
        entry['title'] = entry['movie_name'] = self.title
        entry['url'] = 'mock://localhost/movie_list/%d' % self.id
        entry['added'] = self.added
        if self.year:
            if strip_year is False:
                entry['title'] += ' (%d)' % self.year
            entry['movie_year'] = self.year
        for movie_list_id in self.ids:
            entry[movie_list_id.id_name] = movie_list_id.id_value
        return entry

    def to_dict(self):
        return {
            'id': self.id,
            'added_on': self.added,
            'title': self.title,
            'year': self.year,
            'list_id': self.list_id,
            'movies_list_ids': [movie_list_id.to_dict() for movie_list_id in self.ids],
        }

    @property
    def identifiers(self):
        """ Return a dict of movie identifiers """
        return {identifier.id_name: identifier.id_value for identifier in self.ids}


class MovieListID(Base):
    __tablename__ = 'movie_list_ids'
    id = Column(Integer, primary_key=True)
    added = Column(DateTime, default=datetime.now)
    id_name = Column(Unicode)
    id_value = Column(Unicode)
    movie_id = Column(Integer, ForeignKey(MovieListMovie.id))

    def __repr__(self):
        return '<MovieListID id_name=%s,id_value=%s,movie_id=%d>' % (
            self.id_name,
            self.id_value,
            self.movie_id,
        )

    def to_dict(self):
        return {
            'id': self.id,
            'added_on': self.added,
            'id_name': self.id_name,
            'id_value': self.id_value,
            'movie_id': self.movie_id,
        }


@with_session
def get_movies_by_list_id(
    list_id,
    start=None,
    stop=None,
    order_by='added',
    descending=False,
    movie_ids=None,
    session=None,
):
    query = session.query(MovieListMovie).filter(MovieListMovie.list_id == list_id)
    if movie_ids:
        query = query.filter(MovieListMovie.id.in_(movie_ids))
    if descending:
        query = query.order_by(getattr(MovieListMovie, order_by).desc())
    else:
        query = query.order_by(getattr(MovieListMovie, order_by))
    return query.slice(start, stop).all()


@with_session
def get_movie_lists(name=None, session=None):
    logger.debug('retrieving movie lists')
    query = session.query(MovieListList)
    if name:
        logger.debug('filtering by name {}', name)
        query = query.filter(MovieListList.name.contains(name))
    return query.all()


@with_session
def get_list_by_exact_name(name, session=None):
    logger.debug('returning list with name {}', name)
    return (
        session.query(MovieListList).filter(func.lower(MovieListList.name) == name.lower()).one()
    )


@with_session
def get_list_by_id(list_id, session=None):
    logger.debug('fetching list with id {}', list_id)
    return session.query(MovieListList).filter(MovieListList.id == list_id).one()


@with_session
def get_movie_by_id(list_id, movie_id, session=None):
    logger.debug('fetching movie with id {} from list id {}', movie_id, list_id)
    return (
        session.query(MovieListMovie)
        .filter(and_(MovieListMovie.id == movie_id, MovieListMovie.list_id == list_id))
        .one()
    )


@with_session
def get_movie_by_title_and_year(list_id, title, year=None, session=None):
    movie_list = get_list_by_id(list_id=list_id, session=session)
    if movie_list:
        logger.debug('searching for movie {} in list {}', title, list_id)
        return (
            session.query(MovieListMovie)
            .filter(
                and_(
                    func.lower(MovieListMovie.title) == title.lower(),
                    MovieListMovie.year == year,
                    MovieListMovie.list_id == list_id,
                )
            )
            .one_or_none()
        )


@with_session
def get_movie_identifier(identifier_name, identifier_value, movie_id=None, session=None):
    db_movie_id = (
        session.query(MovieListID)
        .filter(
            and_(
                MovieListID.id_name == identifier_name,
                MovieListID.id_value == identifier_value,
                MovieListID.movie_id == movie_id,
            )
        )
        .first()
    )
    if db_movie_id:
        logger.debug('fetching movie identifier {}: {}', db_movie_id.id_name, db_movie_id.id_value)
        return db_movie_id


@with_session
def get_db_movie_identifiers(identifier_list, movie_id=None, session=None):
    db_movie_ids = []
    for identifier in identifier_list:
        for key, value in identifier.items():
            if key in MovieListBase().supported_ids:
                db_movie_id = get_movie_identifier(
                    identifier_name=key, identifier_value=value, movie_id=movie_id, session=session
                )
                if not db_movie_id:
                    logger.debug('creating movie identifier {}: {}', key, value)
                    db_movie_id = MovieListID(id_name=key, id_value=value, movie_id=movie_id)
                session.merge(db_movie_id)
                db_movie_ids.append(db_movie_id)
    return db_movie_ids
