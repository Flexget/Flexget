from __future__ import annotations

from datetime import datetime

from loguru import logger
from sqlalchemy import ForeignKey, and_, func
from sqlalchemy.orm import DynamicMapped, Mapped, mapped_column, relationship

from flexget.db_schema import versioned_base, with_session
from flexget.entry import Entry

logger = logger.bind(name='regexp_list')
Base = versioned_base('regexp_list', 1)


class RegexpListList(Base):
    __tablename__ = 'regexp_list_lists'
    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str | None] = mapped_column(unique=True)
    added: Mapped[datetime | None] = mapped_column(default=datetime.now)
    regexps: DynamicMapped[RegexListRegexp] = relationship(
        back_populates='list_', cascade='all, delete-orphan'
    )

    def __repr__(self):
        return f'<RegexpListList name={self.name},id={self.id}>'

    def to_dict(self):
        return {'id': self.id, 'name': self.name, 'added_on': self.added}


class RegexListRegexp(Base):
    __tablename__ = 'regexp_list_regexps'
    id: Mapped[int] = mapped_column(primary_key=True)
    added: Mapped[datetime | None] = mapped_column(default=datetime.now)
    regexp: Mapped[str | None]
    list_id: Mapped[int] = mapped_column(ForeignKey(RegexpListList.id))
    list_: Mapped[RegexpListList] = relationship(back_populates='regexps')

    def __repr__(self):
        return f'<RegexListRegexp regexp={self.regexp},list_name={self.list_.name}>'

    def to_entry(self):
        entry = Entry()
        entry['title'] = entry['regexp'] = self.regexp
        entry['url'] = f'mock://localhost/regexp_list/{self.id}'
        return entry

    def to_dict(self):
        return {'id': self.id, 'added_on': self.added, 'regexp': self.regexp}


@with_session
def get_regexp_lists(name=None, session=None):
    logger.debug('retrieving regexp lists')
    query = session.query(RegexpListList)
    if name:
        logger.debug('filtering by name {}', name)
        query = query.filter(RegexpListList.name.contains(name))
    return query.all()


@with_session
def get_list_by_exact_name(name, session=None):
    logger.debug('returning list with name {}', name)
    return (
        session
        .query(RegexpListList)
        .filter(func.lower(RegexpListList.name) == name.lower())
        .one_or_none()
    )


@with_session
def get_regexps_by_list_id(
    list_id, count=False, start=None, stop=None, order_by='added', descending=False, session=None
):
    query = session.query(RegexListRegexp).filter(RegexListRegexp.list_id == list_id)
    if count:
        return query.count()
    query = query.slice(start, stop).from_self()
    if descending:
        query = query.order_by(getattr(RegexListRegexp, order_by).desc())
    else:
        query = query.order_by(getattr(RegexListRegexp, order_by))
    return query.all()


@with_session
def get_list_by_id(list_id, session=None):
    logger.debug('fetching list with id {}', list_id)
    return session.query(RegexpListList).filter(RegexpListList.id == list_id).one_or_none()


@with_session
def get_regexp(list_id, regexp, session=None):
    regexp_list = get_list_by_id(list_id=list_id, session=session)
    if regexp_list:
        logger.debug('searching for regexp {} in list {}', regexp, list_id)
        return (
            session
            .query(RegexListRegexp)
            .filter(
                and_(
                    func.lower(RegexListRegexp.regexp) == regexp.lower(),
                    RegexListRegexp.list_id == list_id,
                )
            )
            .first()
        )
    return None


@with_session
def create_list(list_name, session=None):
    """Only creates the list if it doesn't exist.

    :param str list_name: Name of the list
    :param Session session:
    :return: regex list with name list_name
    """
    regexp_list = get_list_by_exact_name(list_name, session=session)
    if not regexp_list:
        regexp_list = RegexpListList(name=list_name)
        session.merge(regexp_list)
        session.commit()
    return regexp_list


@with_session
def add_to_list_by_name(list_name, regexp, session=None):
    regexp_list = create_list(list_name, session=session)
    existing_regexp = get_regexp(regexp_list.id, regexp, session=session)
    if not existing_regexp:
        new_regexp = RegexListRegexp(regexp=regexp, list_id=regexp_list.id)
        session.merge(new_regexp)
        session.commit()
