import re
from datetime import datetime

from loguru import logger
from sqlalchemy import Column, Integer, Unicode

from flexget import plugin
from flexget.db_schema import versioned_base
from flexget.event import event
from flexget.utils import requests
from flexget.utils.parsers.generic import name_to_re
from flexget.utils.soup import get_soup

logger = logger.bind(name='pogcal_acquired')
Base = versioned_base('pogcal_acquired', 0)
session = requests.Session(max_retries=3)


class PogcalShow(Base):
    __tablename__ = 'pogcal_shows'
    id = Column(Integer, primary_key=True, autoincrement=False, nullable=False)
    name = Column(Unicode)


class PogcalAcquired:
    schema = {
        'type': 'object',
        'properties': {'username': {'type': 'string'}, 'password': {'type': 'string'}},
        'required': ['username', 'password'],
        'additionalProperties': False,
    }

    @plugin.priority(plugin.PRIORITY_LAST)
    def on_task_output(self, task, config):
        if not task.accepted and not task.options.test:
            return
        try:
            result = session.post(
                'http://www.pogdesign.co.uk/cat/login',
                data={
                    'username': config['username'],
                    'password': config['password'],
                    'sub_login': 'Account Login',
                },
            )
        except requests.RequestException as e:
            logger.error('Error logging in to pog calendar: {}', e)
            return
        if 'logout' not in result.text:
            logger.error('Username/password for pogdesign calendar appear to be incorrect.')
            return
        if task.options.test:
            logger.verbose('Successfully logged in to pogdesign calendar.')
        for entry in task.accepted:
            if not entry.get('series_name') or entry.get('series_id_type') != 'ep':
                continue
            show_id = self.find_show_id(entry['series_name'], task.session)
            if not show_id:
                logger.debug('Could not find pogdesign calendar id for `{}`', entry['series_name'])
                continue
            if task.options.test:
                logger.verbose(
                    'Would mark {} {} in pogdesign calenadar.',
                    entry['series_name'],
                    entry['series_id'],
                )
                continue
            logger.verbose(
                'Marking {} {} in pogdesign calenadar.',
                entry['series_name'],
                entry['series_id'],
            )
            shid = '{}-{}-{}/{}-{}'.format(
                show_id,
                entry['series_season'],
                entry['series_episode'],
                datetime.now().month,
                datetime.now().year,
            )
            try:
                session.post(
                    'http://www.pogdesign.co.uk/cat/watchhandle',
                    data={'watched': 'adding', 'shid': shid},
                )
            except requests.RequestException as e:
                logger.error(
                    'Error marking {} {} in pogdesign calendar: {}',
                    entry['series_name'],
                    entry['series_id'],
                    e,
                )

    def find_show_id(self, show_name, db_sess):
        # Check if we have this show id cached
        show_name = show_name.lower()
        db_show = db_sess.query(PogcalShow).filter(PogcalShow.name == show_name).first()
        if db_show:
            return db_show.id
        try:
            page = session.get('http://www.pogdesign.co.uk/cat/showselect.php')
        except requests.RequestException as e:
            logger.error('Error looking up show show list from pogdesign calendar: {}', e)
            return None
        # Try to find the show id from pogdesign show list
        show_re = name_to_re(show_name)
        soup = get_soup(page.content)
        search = re.compile(show_re, flags=re.IGNORECASE)
        show = soup.find(text=search)
        if show:
            id = int(show.find_previous('input')['value'])
            db_sess.add(PogcalShow(id=id, name=show_name))
            return id
        logger.verbose('Could not find pogdesign calendar id for show `{}`', show_re)
        return None


@event('plugin.register')
def register_plugin():
    plugin.register(PogcalAcquired, 'pogcal_acquired', api_ver=2)
