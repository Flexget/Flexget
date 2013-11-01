"""Input plugin for www.betaseries.com"""
from __future__ import unicode_literals, division, absolute_import
from flexget.plugin import register_plugin
import logging
from flexget.utils import requests
from hashlib import md5
from flexget.utils.cached_input import cached
from flexget.entry import Entry


log = logging.getLogger('betaseries_list')

API_URL_PREFIX = 'http://api.betaseries.com/'


class BetaSeriesList(object):
    """
        Emits an entry for each serie followed by one or more BetaSeries account.
        See http://www.betaseries.com/

        Configuration examples:

        # will get all series followed by the account identified by your_user_name
        betaseries:
          username: your_user_name
          password: your_password
          api_key: your_api_key

        # will get all series followed by the account identified by some_other_guy
        betaseries:
          username: your_user_name
          password: your_password
          api_key: your_api_key
          members:
            - some_other_guy

        # will get all series followed by the accounts identified by guy1 and guy2
        betaseries:
          username: your_user_name
          password: your_password
          api_key: your_api_key
          members:
            - guy1
            - guy2


        Api key can be requested at http://www.betaseries.com/api.

        This plugin is meant to work with the import_series plugin as follow:

        import_series:
          from:
            betaseries_list:
              username: xxxxx
              password: xxxxx
              api_key: xxxxx

    """

    schema = {
        'type': 'object',
        'properties': {
            'username': {'type': 'string'},
            'password': {'type': 'string'},
            'api_key': {'type': 'string'},
            'members': {'oneOf': [
                {
                    'type': 'null',
                },
                {
                    'type': 'array',
                    'items': {
                        "title": "member name",
                        "type": "string"
                    }
                }
            ]},
        },
        'required': ['username', 'password', 'api_key'],
        'additionalProperties': False
    }

    @cached('betaseries_list', persist='2 hours')
    def on_task_input(self, task, config):
        username = config['username']
        password = config['password']
        api_key = config['api_key']
        try:
            members = config['members']
        except KeyError:
            members = [username]

        if members is None:
            members = [username]

        titles = set()
        try:
            user_token = create_token(api_key, username, password)
            for member in members:
                titles.update(query_series(api_key, user_token, member))
        except (requests.RequestException, AssertionError), err:
            log.critical('Failed to get series at BetaSeries.com: %s' % err.message, exc_info=err)

        log.verbose("series: " + ", ".join(titles))
        entries = []
        for t in titles:
            e = Entry()
            e['title'] = t
            entries.append(e)
        return entries


def create_token(api_key, login, password):
    """
    login in and request an new API token.
    http://www.betaseries.com/wiki/Documentation#cat-members

    @param api_key: api key requested at http://www.betaseries.com/api
    @param login:
    @param password:
    @return: user token
    """
    r = requests.post(API_URL_PREFIX + 'members/auth', params={
        'login': login,
        'password': md5(password).hexdigest()
    }, headers={
        'Accept': 'application/json',
        'X-BetaSeries-Version': '2.1',
        'X-BetaSeries-Key': api_key,
    })
    assert r.status_code == 200, "Bad HTTP status code: %s" % r.status_code
    j = r.json()
    error_list = j['errors']
    for err in error_list:
        log.error(str(err))
    if not error_list:
        return j['token']


def query_member_id(api_key, user_token, login_name):
    """
    get the member id of a member identified by its login name.

    @param api_key: api key requested at http://www.betaseries.com/api
    @param user_token: obtained with a call to create_token()
    @param login_name: the login name of the member
    @return: id of the member identified by its login name or None if not found
    """
    r = requests.get(API_URL_PREFIX + 'members/search', params={
        'login': login_name
    }, headers={
        'Accept': 'application/json',
        'X-BetaSeries-Version': '2.1',
        'X-BetaSeries-Key': api_key,
        'X-BetaSeries-Token': user_token,
    })
    assert r.status_code == 200, "Bad HTTP status code: %s" % r.status_code
    j = r.json()
    error_list = j['errors']
    for err in error_list:
        log.error(str(err))
    found_id = None
    if not error_list:
        for candidate in j['users']:
            if candidate['login'] == login_name:
                found_id = candidate['id']
                break
    return found_id


def query_series(api_key, user_token, member_name=None):
    """
    get the list of series followed by the authenticated user

    @param api_key: api key requested at http://www.betaseries.com/api
    @param user_token: obtained with a call to create_token()
    @param member_name: [optional] a member name to get the list of series from. If None, will query the member for whom
                    the user_token was for
    @return: list of serie titles
    """
    params = {}
    if member_name:
        member_id = query_member_id(api_key, user_token, member_name)
        if member_id:
            params = {'id': member_id}
        else:
            log.error("member %r not found" % member_name)
            return []
    r = requests.get(API_URL_PREFIX + 'members/infos', params=params, headers={
        'Accept': 'application/json',
        'X-BetaSeries-Version': '2.1',
        'X-BetaSeries-Key': api_key,
        'X-BetaSeries-Token': user_token,
    })
    assert r.status_code == 200, "Bad HTTP status code: %s" % r.status_code
    j = r.json()
    error_list = j['errors']
    for err in error_list:
        log.error(str(err))
    if not error_list:
        return [x['title'] for x in j['member']['shows'] if x['user']['archived'] is False]
    else:
        return []


register_plugin(BetaSeriesList, 'betaseries_list', api_ver=2)
