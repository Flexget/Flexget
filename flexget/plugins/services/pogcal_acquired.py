from __future__ import unicode_literals, division, absolute_import
from builtins import *  # pylint: disable=unused-import, redefined-builtin

import logging
import re
from datetime import datetime

from sqlalchemy import Column, Unicode, Integer

from flexget import plugin
from flexget.event import event
from flexget.utils import requests
from flexget.utils.soup import get_soup
from flexget.utils.titles.series import name_to_re
from flexget.db_schema import versioned_base

log = logging.getLogger('pogcal_acquired')
Base = versioned_base('pogcal_acquired', 0)
session = requests.Session(max_retries=3)


class PogcalShow(Base):
    __tablename__ = 'pogcal_shows'
    id = Column(Integer, primary_key=True, autoincrement=False, nullable=False)
    name = Column(Unicode)


class PogcalAcquired(object):
    schema = {
        'type': 'object',
        'properties': {
            'username': {'type': 'string'},
            'password': {'type': 'string'}
        },
        'required': ['username', 'password'],
        'additionalProperties': False
    }

    @plugin.priority(-255)
    def on_task_output(self, task, config):
        if not task.accepted and not task.options.test:
            return
        try:
            result = session.post('http://www.pogdesign.co.uk/cat/',
                                  data={'username': config['username'],
                                        'password': config['password'],
                                        'sub_login': 'Account Login'})
        except requests.RequestException as e:
            log.error('Error logging in to pog calendar: %s' % e)
            return
        if 'logout' not in result.text:
            log.error('Username/password for pogdesign calendar appear to be incorrect.')
            return
        elif task.options.test:
            log.verbose('Successfully logged in to pogdesign calendar.')
        for entry in task.accepted:
            if not entry.get('series_name') or not entry.get('series_id_type') == 'ep':
                continue
            show_id = self.find_show_id(entry['series_name'], task.session)
            if not show_id:
                log.debug('Could not find pogdesign calendar id for `%s`' % entry['series_name'])
                continue
            if task.options.test:
                log.verbose('Would mark %s %s in pogdesign calenadar.' % (entry['series_name'], entry['series_id']))
                continue
            else:
                log.verbose('Marking %s %s in pogdesign calenadar.' % (entry['series_name'], entry['series_id']))
            shid = '%s-%s-%s/%s-%s' % (show_id, entry['series_season'], entry['series_episode'],
                                       datetime.now().month, datetime.now().year)
            try:
                session.post('http://www.pogdesign.co.uk/cat/watchhandle',
                             data={'watched': 'adding', 'shid': shid})
            except requests.RequestException as e:
                log.error('Error marking %s %s in pogdesign calendar: %s' %
                          (entry['series_name'], entry['series_id'], e))

    def find_show_id(self, show_name, db_sess):
        # Check if we have this show id cached
        show_name = show_name.lower()
        db_show = db_sess.query(PogcalShow).filter(PogcalShow.name == show_name).first()
        if db_show:
            return db_show.id
        try:
            page = session.get('http://www.pogdesign.co.uk/cat/showselect.php')
        except requests.RequestException as e:
            log.error('Error looking up show show list from pogdesign calendar: %s' % e)
            return
        # Try to find the show id from pogdesign show list
        show_re = name_to_re(None, show_name)
        soup = get_soup(page.content)
        search = re.compile(show_re, flags=re.I)
        show = soup.find(text=search)
        if show:
            id = int(show.previous['value'])
            db_sess.add(PogcalShow(id=id, name=show_name))
            return id
        else:
            log.verbose('Could not find pogdesign calendar id for show `%s`' % show_re)


@event('plugin.register')
def register_plugin():
    plugin.register(PogcalAcquired, 'pogcal_acquired', api_ver=2)
