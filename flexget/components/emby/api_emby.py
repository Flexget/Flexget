import copy
import functools
import re
from abc import ABC, abstractmethod, abstractstaticmethod
from collections.abc import MutableSet
from datetime import datetime
from urllib.parse import urlencode

from loguru import logger
from requests.exceptions import HTTPError, RequestException

from flexget.components.emby.emby_util import get_field_map
from flexget.entry import Entry
from flexget.plugin import PluginError
from flexget.utils import requests
from flexget.utils.simple_persistence import SimplePersistence
from flexget.utils.tools import get_current_flexget_version, split_title_year, str_to_int

persist = SimplePersistence('api_emby')

LOGIN_API = 'api'
LOGIN_USER = 'user'
LOGIN_CONNECT = 'connect'

EMBY_CONNECT = 'https://connect.emby.media'

EMBY_ENDPOINT_CONNECT_LOGIN = '/service/user/authenticate'
EMBY_ENDPOINT_CONNECT_SERVERS = '/service/servers'
EMBY_ENDPOINT_CONNECT_EXCHANGE = '/Connect/Exchange'

EMBY_ENDPOINT_LOGIN = '/emby/Users/AuthenticateByName'
EMBY_ENDPOINT_SEARCH = '/emby/Users/{userid}/Items'
EMBY_ENDPOINT_PHOTOS = '/emby/Items/{itemid}/Images/Primary'
EMBY_ENDPOINT_DOWNLOAD = '/emby/Items/{itemid}/Download'
EMBY_ENDPOINT_GETUSERS = '/emby/Users'
EMBY_ENDPOINT_USERINFO = '/emby/Users/{userid}'
EMBY_ENDPOINT_SERVERINFO = '/emby/System/Info'
EMBY_ENDPOINT_PARENTS = '/emby/Items/{itemid}/Ancestors'
EMBY_ENDPOINT_LIBRARY = '/emby/Library/MediaFolders'
EMBY_ENDPOINT_FAVORITE = '/emby/Users/{userid}/FavoriteItems/{itemid}'
EMBY_ENDPOINT_ITEMUPD = '/emby/Items/{itemid}'
EMBY_ENDPOINT_WATCHED = '/emby/Users/{userid}/PlayedItems/{itemid}'
EMBY_ENDPOINT_NEW_PLAYLIST = '/emby/Playlists'
EMBY_ENDPOINT_PLAYLIST = '/emby/Playlists/{listid}/Items'
EMBY_ENDPOINT_DELETE_ITEM = '/emby/Items/{itemid}'
EMBY_ENDPOINT_LIBRARY_REFRESH = '/emby/Library/Refresh'

logger = logger.bind(name='api_emby')


class EmbyApiBase(ABC):
    """
    Base Class to all API integratios
    """

    EMBY_PREF = 'emby_'

    @staticmethod
    def merge_field_map(dst: dict, *arg: dict, **kwargs):
        """Merge field maps from clild and parent class"""

        allow_new = kwargs.get('allow_new', False)

        destination = copy.deepcopy(dst)

        for src in arg:
            source = copy.deepcopy(src)

            for key in source:
                if key in destination and isinstance(destination[key], str):
                    destination[key] = [destination[key]]
                elif key not in destination and not allow_new:
                    continue
                elif key not in destination and allow_new:
                    destination[key] = []

                if isinstance(source[key], str):
                    source[key] = [source[key]]

                if source[key][0] and source[key][0].find(EmbyApiBase.EMBY_PREF) < 0:
                    source[key].insert(0, f'{EmbyApiBase.EMBY_PREF}{source[key][0]}')

                for value_source in source[key]:
                    if not value_source in destination[key]:
                        destination[key].append(value_source)

        return destination

    @staticmethod
    def update_using_map(target, field_map: dict, source_item, **kwargs):
        """
        Updates based on field map with source
        """

        allow_new = kwargs.get('allow_new', False)

        my_field_map = field_map.copy()

        func_get = dict.get if isinstance(source_item, dict) else getattr
        for field, val in my_field_map.items():

            values = val
            if not isinstance(values, list):
                values = [val]

            if values[0] and values[0].find(EmbyApiBase.EMBY_PREF) < 0:
                values.insert(0, f'{EmbyApiBase.EMBY_PREF}{values[0]}')

            for value in values:
                if isinstance(value, str):
                    try:
                        val = functools.reduce(func_get, value.split('.'), source_item)
                    except TypeError:
                        continue
                else:
                    val = value(source_item)

                if val is None:
                    continue

                if not hasattr(target, field) and not allow_new:
                    continue

                if isinstance(target, dict):
                    target[field] = val
                else:
                    setattr(target, field, val)

                break


class EmbyAuth(EmbyApiBase):
    """
    Manage API Authorizations
    """

    _last_auth = None

    field_map = {
        'host': 'host',
        'return_host': 'return_host',
        '_apikey': 'apikey',
        '_username': 'username',
        '_password': 'password',
    }

    EMBY_DEF_HOST = 'http://localhost:8096'

    EMBY_CLIENT = 'Flexget'
    EMBY_DEVICE = 'Flexget Plugin'
    EMBY_DEVICE_ID = 'flexget_plugin'
    EMBY_VERSION = get_current_flexget_version()

    host = EMBY_DEF_HOST
    return_host = None

    _userid = ''
    _token = ''
    _connect_token = ''
    _connect_token_link = ''
    _connect_username = ''
    _serverid = ''
    _logged = False
    _username = None
    _password = None
    _apikey = None
    _wanurl = None
    _lanurl = None
    _can_download = None
    _login_type = None

    def __init__(self, **kwargs):
        if 'server' in kwargs:
            server = kwargs.get('server')
        else:
            server = kwargs

        EmbyApiBase.update_using_map(self, EmbyAuth.field_map, server)

    def is_connect_server(self) -> bool:
        """Checks if it's a connect server, if it's a url assumed not a emby connect

        Returns:
            bool: Is emby connect server
        """

        regexp = (
            '('
            + '|'.join(['http', 'https'])
            + r'):\/\/(\w+:{0,1}\w*@)?(\S+)(:[0-9]+)?(\/|\/([\w#!:.?+=&%@!\-\/]))?'
        )
        return not re.match(regexp, self.host)

    def login(self, optional=False):
        """Login user to API"""

        userdata = None

        if not self._apikey:

            if self.is_connect_server():
                # Make Emby connect login
                self._login_type = LOGIN_CONNECT
                userdata = self.check_token_data(persist.get('token_data'), LOGIN_CONNECT)
                if not userdata:
                    logger.debug(
                        'Login to Emby Connect with username `{}` host `{}`',
                        self.username,
                        self.host,
                    )

                    self._connect_username = self._username

                    # Login to emby connect
                    args = {'nameOrEmail': self._username, 'rawpw': self._password}
                    connect_data = EmbyApi.resquest_emby(
                        EMBY_ENDPOINT_CONNECT_LOGIN, self, 'POST', emby_connect=True, **args
                    )

                    if (
                        not connect_data
                        or not 'AccessToken' in connect_data
                        or not 'User' in connect_data
                        or not 'Id' in connect_data['User']
                    ):
                        raise PluginError(
                            f'Could not login to Emby Connect account `{self._connect_username}`'
                        )

                    self._connect_token = connect_data['AccessToken']

                    # Retrive emby connect servers
                    args = {'userId': connect_data['User']['Id']}
                    connect_servers = EmbyApi.resquest_emby(
                        EMBY_ENDPOINT_CONNECT_SERVERS, self, 'GET', emby_connect=True, **args
                    )
                    if not isinstance(connect_servers, list):
                        raise PluginError(
                            f'Could not login to Emby Connect account `{self._connect_username}`, no server list'
                        )

                    for server in connect_servers:
                        if not 'Name' in server:
                            raise PluginError(
                                f'Could not login to Emby Connect account `{self._connect_username}`, no server list'
                            )
                        if server['Name'].lower() == self.host.lower():
                            connect_server = server
                            break
                    else:
                        raise PluginError(
                            f'No server with name `{self.host}`` on `{self._connect_username}` account'
                        )

                    if not 'AccessKey' in connect_server or not 'Url' in connect_server:
                        raise PluginError(
                            f'Could not login to Emby Connect account `{self._connect_username}`, no server list'
                        )

                    self._connect_token_link = connect_server['AccessKey']
                    self.host = connect_server['Url']

                    args = {'format': 'json', 'ConnectUserId': connect_data['User']['Id']}
                    connect_exchange = EmbyApi.resquest_emby(
                        EMBY_ENDPOINT_CONNECT_EXCHANGE, self, 'GET', **args
                    )

                    if (
                        not 'LocalUserId' in connect_exchange
                        or not 'AccessToken' in connect_exchange
                    ):
                        raise PluginError(
                            f'Could not login with Emby Connect to server `{self.host}`'
                        )

                    self._userid = connect_exchange['LocalUserId']
                    self._token = connect_exchange['AccessToken']
                    self._logged = True
                    userdata = EmbyApi.resquest_emby(EMBY_ENDPOINT_USERINFO, self, 'GET', {})

            else:
                # Make Local user login
                self._login_type = LOGIN_USER
                userdata = self.check_token_data(persist.get('token_data'), LOGIN_USER)
                if not userdata:
                    logger.debug(
                        'Login to {} with username {} and password', self.host, self.username
                    )
                    args = {'Username': self._username, 'Pw': self._password}

                    login_data = EmbyApi.resquest_emby(EMBY_ENDPOINT_LOGIN, self, 'POST', **args)

                    if not login_data and optional:
                        return
                    elif not login_data:
                        self.logout()
                        raise PluginError('Could not login to Emby')

                    userdata = login_data.get('User')
                    self._token = login_data.get('AccessToken')
                else:
                    allow_retry = True
        else:
            logger.debug('Login to {} with username {} and apikey', self.host, self.username)
            userdata = self.get_user_by_name(self._username)
            self._login_type = LOGIN_API

        if not userdata and optional:
            return
        elif not userdata:
            self.logout()
            raise PluginError('Could not login to Emby')

        self._username = userdata.get('Name')
        self._userid = userdata.get('Id')
        self._serverid = userdata.get('ServerId')

        if 'Policy' in userdata and not self._apikey:
            self._can_download = userdata['Policy'].get('EnableContentDownloading', False)
        elif self._apikey:
            self._can_download = True

        self._logged = True

        serverinfo = EmbyApi.resquest_emby(EMBY_ENDPOINT_SERVERINFO, self, 'GET')
        if serverinfo:
            self._wanurl = serverinfo.get('WanAddress')
            self._lanurl = serverinfo.get('LocalAddress')
        elif allow_retry:
            logger.debug('Try to clean token data to login again')
            self.logout()
            self.login()
            return
        else:
            self.logout()
            raise PluginError('Could not login to Emby')

        self.save_token_data()
        EmbyAuth._last_auth = self

    def logout(self):
        """Logout user from API"""
        self._token = None
        self._logged = False
        self._connect_username = ''

        if 'token_data' in persist:
            persist['token_data']['token'] = None

    def check_token_data(self, token_data, login_type):
        """Checks saved tokens"""
        if not token_data:
            return False

        if login_type == LOGIN_CONNECT:
            connect_username = self._connect_username if self._connect_username else self._username
            if (
                'token' not in token_data
                or 'userid' not in token_data
                or token_data.get('connect_username') != connect_username
                or login_type != token_data.get('login_type')
            ):
                self.logout()
                return False
        else:
            if (
                'token' not in token_data
                or 'userid' not in token_data
                or token_data.get('username') != self._username
                or token_data.get('host') != self.host
                or login_type != token_data.get('login_type')
            ):
                self.logout()
                return False

        self._userid = token_data.get('userid')
        self._token = token_data.get('token')
        self._login_type = token_data.get('type')
        self._connect_username = token_data.get('connect_username', '')
        self.host = token_data.get('host', '')
        self._logged = True
        endpoint = EMBY_ENDPOINT_USERINFO.format(userid=token_data['userid'])
        response = EmbyApi.resquest_emby(endpoint, self, 'GET')
        if not response:
            self.logout()
            return False

        if self._userid != response.get('Id'):
            self.logout()
            return False

        response['AccessToken'] = token_data['token']

        logger.debug('Restored emby token from database')

        return response

    def save_token_data(self):
        """Saves token data to Data Base"""

        if self._apikey or not self.host or not self.username:
            return

        if self._login_type == LOGIN_API:
            return

        logger.debug('Saving emby token to database')

        persist['token_data'] = {
            'host': self.host.lower(),
            'username': self._username.lower(),
            'userid': self._userid,
            'serverid': self._serverid,
            'token': self._token,
            'connect_username': self._connect_username,
            'login_type': self._login_type,
        }

    @property
    def uid(self) -> str:
        return self._userid

    @property
    def username(self) -> str:
        return self._username

    @property
    def logged(self) -> bool:
        return self._logged

    @property
    def can_download(self) -> bool:
        return self._can_download

    @property
    def token(self) -> str:
        return self._token

    @property
    def server_id(self) -> str:
        return self._serverid

    @property
    def wanurl(self) -> str:
        return self._wanurl

    @property
    def lanurl(self) -> str:
        return self._lanurl

    def add_token_header(self, header: dict, emby_connect=False) -> dict:
        """Adds data to request header"""
        if not header:
            header = {}

        if emby_connect:
            header = {'X-Application': self.EMBY_CLIENT}
            if self._connect_token:
                header['X-Connect-UserToken'] = self._connect_token

            return header

        if self._apikey:
            header['X-Emby-Token'] = self._apikey
            return header

        fields = [
            f'Emby UserId={self._userid}',
            f'Client={self.EMBY_CLIENT}',
            f'Device={self.EMBY_DEVICE}',
            f'DeviceId={self.EMBY_DEVICE_ID}',
            f'Version={self.EMBY_VERSION}',
        ]

        header['X-Emby-Authorization'] = ', '.join(fields)
        header['accept'] = 'application/json'

        if not self.logged:
            return header

        header['X-Emby-Token'] = self.token
        return header

    def get_user_by_name(self, name: str) -> dict:
        """Gets user by username"""

        args = {'IsDisabled': False}
        useres = EmbyApi.resquest_emby(EMBY_ENDPOINT_GETUSERS, self, 'GET', **args)
        if not useres:
            return

        for user in useres:
            if user.get('Name').lower() == name.lower():
                return user

    @staticmethod
    def get_last_auth():
        return EmbyAuth._last_auth


class EmbyApiListBase(EmbyApiBase):
    """Base class to all API Lists"""

    auth = None

    _index = 0
    _iterator = 10
    _len = 0

    id = None
    _name = None
    types = None
    watched = None
    favorite = None
    sort = None

    allow_create = False

    _internal_items = None

    field_map = {
        'id': ['library_id', 'id', 'Id'],
        '_name': ['library_name', 'list', 'name', 'Name'],
        'types': ['types'],
        'watched': ['watched'],
        'favorite': ['favorite'],
        'sort': ['sort'],
    }

    def __init__(self, **kwargs):
        self.auth = EmbyApi.get_auth(**kwargs)
        EmbyApiBase.update_using_map(self, EmbyApiListBase.field_map, kwargs)

        if self.types and not isinstance(self.types, list):
            self.types = [self.types]

        if isinstance(self.sort, str):
            self.sort = {'field': self.sort, 'order': 'ascending'}

        if isinstance(self.sort, dict):
            self.sort['field'] = self.sort['field'].replace('_', '')

    def set_list_search_args(self, args: dict):
        if self.watched is not None:
            args['IsPlayed'] = self.watched

        if self.favorite is not None:
            args['IsFavorite'] = self.favorite

        if self.sort is not None:
            args['SortBy'] = self.sort['field']
            args['SortOrder'] = self.sort['order']

        if not self.types or len(self.types) == 0:
            args['IncludeItemTypes'] = 'Movie,Episode'
        else:
            args['IncludeItemTypes'] = ','.join(typ.title() for typ in self.types)

    def add(self, entry: Entry):
        """Adds a item to list"""
        item = EmbyApiMedia.cast(auth=self.auth, **entry)
        if not item:
            logger.warning('Not possible to match \'{}\' in emby', item.fullname)
            return

        if self.contains(item):
            logger.warning('\'{}\' already in {}', item.fullname, self.fullname)
            return

        logger.debug('Adding \'{}\' to {}', item.fullname, self.fullname)
        self._add(item)

    @abstractmethod
    def _add(self, item: 'EmbyApiMedia'):
        pass

    def remove(self, entry: Entry):
        """Removes a item from list"""
        item = EmbyApiMedia.cast(auth=self.auth, **entry)
        if not item:
            logger.warning('Not possible to match \'{}\' in emby', item.fullname)
            return

        if not self.contains(item):
            logger.warning('\'{}\' not in {}', item.fullname, self.fullname)
            return

        logger.debug('Removing \'{}\' from {}', item.fullname, self.fullname)
        self._remove(item)

    @abstractmethod
    def _remove(self, item: 'EmbyApiMedia'):
        pass

    @abstractmethod
    def get_items(self):
        pass

    def contains(self, item):
        """Checks if list contains item"""
        return bool(self.get(item))

    def get(self, item) -> 'EmbyApiMedia':
        """Get Item from list"""

        if isinstance(item, EmbyApiMedia):
            s_item = item
        else:
            s_item = EmbyApiMedia.cast(auth=self.auth, **item)

        if not s_item:
            return None

        return s_item

    @property
    def iterator(self):
        return self._iterator

    @property
    def index(self):
        return self._index * self._iterator

    @property
    def next_index(self):
        index = self._index + 1
        return index * self._iterator

    @property
    def len(self):
        return self._len

    @property
    def name(self):
        return self._name

    @property
    def fullname(self):
        return self._name

    @property
    def created(self):
        return bool(self.id)

    @property
    def immutable(self):
        return

    @abstractstaticmethod
    def is_type(**kwargs):
        pass


class EmbyApiList(EmbyApiBase, MutableSet):
    """Class to interface lists"""

    auth = None
    id = None
    name = None
    _list = None
    _items = None

    field_map = {
        'id': ['library_id', 'id', 'Id'],
        'name': ['library_name', 'list', 'name', 'Name'],
    }

    def __init__(self, **kwargs):
        self.auth = EmbyApi.get_auth(**kwargs)
        EmbyApiBase.update_using_map(self, self.field_map, kwargs)

        self._list = self.get_api_list(**kwargs)
        if not self._list:
            raise PluginError('List \'%s\' does not exist' % self.name)

        self._items = self._list.get_items()

    def __contains__(self, item):
        return self._list.contains

    def __iter__(self):
        return iter(self._items)

    def __len__(self):
        return self._list.len

    def add(self, item) -> None:
        self._list.add(item)

    def discard(self, item) -> None:
        self._list.remove(item)

    def get(self, item) -> None:
        item_s = self._list.get(item)
        if not item_s:
            return None

        return item_s.to_entry()

    @property
    def immutable(self):
        return self._list.immutable

    @staticmethod
    def get_api_list(**kwargs) -> EmbyApiListBase:

        if EmbyApiRootList.is_type(**kwargs):
            logger.debug('List is a root list')
            return EmbyApiRootList(**kwargs)
        elif EmbyApiWatchedList.is_type(**kwargs):
            logger.debug('List is a watched list')
            return EmbyApiWatchedList(**kwargs)
        elif EmbyApiFavoriteList.is_type(**kwargs):
            logger.debug('List is a favorite list')
            return EmbyApiFavoriteList(**kwargs)
        elif EmbyApiLibrary.is_type(**kwargs):
            logger.debug('List is a library')
            return EmbyApiLibrary(**kwargs)
        elif EmbyApiPlayList.is_type(**kwargs):
            logger.debug('List is a playlist')
            return EmbyApiPlayList(**kwargs)

        if EmbyApiRootList.is_type(**kwargs) or EmbyApiRootList.allow_create:
            logger.debug('Creating a root list')
            return EmbyApiRootList(**kwargs)
        if EmbyApiWatchedList.is_type(**kwargs) or EmbyApiWatchedList.allow_create:
            logger.debug('Creating a watched list')
            return EmbyApiWatchedList(**kwargs)
        elif EmbyApiFavoriteList.is_type(**kwargs) or EmbyApiFavoriteList.allow_create:
            logger.debug('Creating a favorite list')
            return EmbyApiFavoriteList(**kwargs)
        elif EmbyApiLibrary.is_type(**kwargs) or EmbyApiLibrary.allow_create:
            logger.debug('Creating a library')
            return EmbyApiLibrary(**kwargs)
        elif EmbyApiPlayList.is_type(**kwargs) or EmbyApiPlayList.allow_create:
            logger.debug('Creating a playlist')
            return EmbyApiPlayList(**kwargs)


class EmbyApiLibrary(EmbyApiListBase):
    """Library List"""

    def __init__(self, **kwargs):
        EmbyApiListBase.__init__(self, **kwargs)

        list_data = EmbyApiLibrary._get_list_data(self.auth, list=self.name)
        if not list_data:
            return

        self.id = list_data['Id']

    def _add(self, item):
        pass

    def _remove(self, item):
        pass

    def get(self, item):
        item_g = EmbyApiListBase.get(self, item)
        if not item_g:
            return None

        if isinstance(item_g.library, EmbyApiLibrary) and item_g.library.id == self.id:
            return item_g

        return None

    def get_items(self):
        if not self.created:
            return []

        args = {}

        EmbyApi.set_common_search_arg(args)
        self.set_list_search_args(args)

        index = 0
        args['ParentId'] = self.id
        endpoint = EMBY_ENDPOINT_SEARCH.format(userid=self.auth.uid)
        logger.debug('Search library with: {}', args)

        while True:
            args['Limit'] = self.iterator
            args['StartIndex'] = index * self.iterator
            items = EmbyApi.resquest_emby(endpoint, self.auth, 'GET', **args)

            self._len = items.get('TotalRecordCount', 0)

            if not items.get('Items'):
                if index > 0:
                    items = []
                return

            items = items.get('Items', [])

            for media in items:
                media_obj = EmbyApiMedia.cast(auth=self.auth, **media)
                if media_obj:
                    yield media_obj

            index += 1

    @staticmethod
    def library_refresh(auth):
        if not auth:
            auth = EmbyApi.get_auth()

        additem = EmbyApi.resquest_emby(EMBY_ENDPOINT_LIBRARY_REFRESH, auth, 'POST')
        if not additem:
            logger.error('Not possible to refresh emby library')

    @staticmethod
    def _get_list_data(auth, **kwargs):
        args = {}

        list_name = kwargs.get('list')

        EmbyApi.set_common_search_arg(args)

        args['IsHidden'] = False

        logger.debug('Search Library name list with: {}', args)
        search_list_data = EmbyApi.resquest_emby(EMBY_ENDPOINT_LIBRARY, auth, 'GET', **args)
        if not search_list_data or not search_list_data['Items']:
            return

        for search_list in search_list_data['Items']:
            if (
                'Type' not in search_list
                or 'CollectionType' not in search_list
                or 'IsFolder' not in search_list
            ):
                continue

            if search_list['Type'] != 'CollectionFolder':
                continue
            elif (
                search_list['CollectionType'] != 'tvshows'
                and search_list['CollectionType'] != 'movies'
            ):
                continue

            if search_list['Name'].lower() == list_name.lower():
                return search_list

    @staticmethod
    def is_type(**kwargs):
        auth = EmbyApi.get_auth(**kwargs)

        list_name = kwargs.get('list')

        list_data = EmbyApiLibrary._get_list_data(auth, list=list_name)
        if not list_data:
            return False

        return True

    @property
    def fullname(self):
        return f'Library \'{self.name}\''

    @property
    def created(self):
        return bool(self.id)

    @property
    def immutable(self):
        return 'Library is not modifiable'


class EmbyApiRootList(EmbyApiListBase):
    """Root Media List"""

    def __init__(self, **kwargs):
        EmbyApiListBase.__init__(self, **kwargs)

        self._name = 'Root List'

    def _add(self, item: 'EmbyApiMedia'):
        logger.warning('Not possible to add items to root list')

    def _remove(self, item: 'EmbyApiMedia'):
        logger.warning('Not possible to remove items from root list')

    def get_items(self):
        args = {}

        EmbyApi.set_common_search_arg(args)
        self.set_list_search_args(args)

        index = 0

        endpoint = EMBY_ENDPOINT_SEARCH.format(userid=self.auth.uid)
        logger.debug('Search root list with: {}', args)

        while True:
            args['Limit'] = self.iterator
            args['StartIndex'] = index * self.iterator
            items = EmbyApi.resquest_emby(endpoint, self.auth, 'GET', **args)

            self._len = items.get('TotalRecordCount', 0)

            if not items.get('Items'):
                if index > 0:
                    items = []
                return

            items = items.get('Items', [])

            for media in items:
                media_obj = EmbyApiMedia.cast(auth=self.auth, **media)
                if media_obj:
                    yield media_obj

            index += 1

    @staticmethod
    def is_type(**kwargs):
        return kwargs.get('list') == '' or kwargs.get('list') is None

    @property
    def created(self):
        return True


class EmbyApiWatchedList(EmbyApiListBase):
    """Watched Media List"""

    def __init__(self, **kwargs):
        EmbyApiListBase.__init__(self, **kwargs)

        self._name = 'Watched List'

    def _add(self, item: 'EmbyApiMedia'):
        args = {}
        endpoint = EMBY_ENDPOINT_WATCHED.format(userid=self.auth.uid, itemid=item.id)
        additem = EmbyApi.resquest_emby(endpoint, self.auth, 'POST', **args)
        if not additem:
            logger.warning('Not possible to add item \'{}\' to watched list', item.fullname)

    def _remove(self, item: 'EmbyApiMedia'):
        args = {}
        endpoint = EMBY_ENDPOINT_WATCHED.format(userid=self.auth.uid, itemid=item.id)
        additem = EmbyApi.resquest_emby(endpoint, self.auth, 'DELETE', **args)
        if not additem:
            logger.warning('Not possible to remove item \'{}\' from watched list', item.fullname)

    def get(self, item):
        item_g = EmbyApiListBase.get(self, item)
        if not item_g:
            return None

        if item_g.watched:
            return item_g

        return None

    def get_items(self):
        args = {}

        EmbyApi.set_common_search_arg(args)
        self.set_list_search_args(args)

        index = 0
        args['IsPlayed'] = True
        endpoint = EMBY_ENDPOINT_SEARCH.format(userid=self.auth.uid)
        logger.debug('Search watched list with: {}', args)

        while True:
            args['Limit'] = self.iterator
            args['StartIndex'] = index * self.iterator
            items = EmbyApi.resquest_emby(endpoint, self.auth, 'GET', **args)

            self._len = items.get('TotalRecordCount', 0)

            if not items.get('Items'):
                if index > 0:
                    items = []
                return

            items = items.get('Items', [])

            for media in items:
                media_obj = EmbyApiMedia.cast(auth=self.auth, **media)
                if media_obj:
                    yield media_obj

            index += 1

    @staticmethod
    def is_type(**kwargs):
        return kwargs.get('list') == 'watched'

    @property
    def created(self):
        return True


class EmbyApiFavoriteList(EmbyApiListBase):
    """Favorite media list"""

    def __init__(self, **kwargs):
        EmbyApiListBase.__init__(self, **kwargs)

        self._name = 'Favorite List'

    def _add(self, item: 'EmbyApiMedia'):
        args = {}
        endpoint = EMBY_ENDPOINT_FAVORITE.format(userid=self.auth.uid, itemid=item.id)
        additem = EmbyApi.resquest_emby(endpoint, self.auth, 'POST', **args)
        if not additem:
            logger.warning('Not possible to add item \'{}\' to favorite list', item.fullname)

    def _remove(self, item: 'EmbyApiMedia'):
        args = {}
        endpoint = EMBY_ENDPOINT_FAVORITE.format(userid=self.auth.uid, itemid=item.id)
        additem = EmbyApi.resquest_emby(endpoint, self.auth, 'DELETE', **args)
        if not additem:
            logger.warning('Not possible to remove item \'{}\' from favorite list', item.fullname)

    def get(self, item):
        item_g = EmbyApiListBase.get(self, item)
        if not item_g:
            return None

        if item_g.favorite:
            return item_g

        return None

    def get_items(self):
        args = {}

        EmbyApi.set_common_search_arg(args)
        self.set_list_search_args(args)

        index = 0
        args['IsFavorite'] = True
        endpoint = EMBY_ENDPOINT_SEARCH.format(userid=self.auth.uid)
        logger.debug('Search favorite list with: {}', args)

        while True:
            args['Limit'] = self.iterator
            args['StartIndex'] = index * self.iterator
            items = EmbyApi.resquest_emby(endpoint, self.auth, 'GET', **args)

            self._len = items.get('TotalRecordCount', 0)

            if not items.get('Items'):
                if index > 0:
                    items = []
                return

            items = items.get('Items', [])

            for media in items:
                media_obj = EmbyApiMedia.cast(auth=self.auth, **media)
                if media_obj:
                    yield media_obj

            index += 1

    @staticmethod
    def is_type(**kwargs):
        return kwargs.get('list') == 'favorite'

    @property
    def created(self):
        return True


class EmbyApiPlayList(EmbyApiListBase):
    """Playlist lists"""

    allow_create = True

    playlist_bind = {}

    def __init__(self, **kwargs):
        EmbyApiListBase.__init__(self, **kwargs)

        list_data = EmbyApiPlayList._get_list_data(self.auth, list=self.name)
        if not list_data:
            return

        self.id = list_data['Id']

    def _add(self, item: 'EmbyApiMedia'):
        if not self.created:
            new_list = EmbyApiPlayList.create(item, auth=self.auth, list=self.name)
            self.id = new_list.id
            return

        args = {}
        args['UserId'] = self.auth.uid
        args['Ids'] = item.id

        endpoint = EMBY_ENDPOINT_PLAYLIST.format(listid=self.id)
        additem = EmbyApi.resquest_emby(endpoint, self.auth, 'POST', **args)
        if not additem:
            logger.warning(
                'Not possible to add item \'{}\' to Playlist \'{}\'', item.fullname, self.name
            )
            return

    def _remove(self, item):
        if not self.playlist_bind:
            self.fill_items()

        if len(self.playlist_bind) == 1:
            logger.debug('{} is empty', self.fullname)
            self.destroy()
            return

        if item.id not in self.playlist_bind:
            logger.warning('Can\'t find entry of \'{}\' in {}', item.fullname, self.fullname)
            return

        args = {}
        args['EntryIds'] = self.playlist_bind[item.id]

        endpoint = EMBY_ENDPOINT_PLAYLIST.format(listid=self.id)
        additem = EmbyApi.resquest_emby(endpoint, self.auth, 'DELETE', **args)
        if not additem:
            logger.warning(
                'Not possible to remove item \'{}\' from Playlist \'{}\'', item.fullname, self.name
            )
            return

        self.playlist_bind.pop(item.id, None)

        if not self.playlist_bind:
            self.destroy()

    def contains(self, item):
        """Checks if list contains item"""
        self.fill_items()
        return EmbyApiListBase.contains(self, item)

    def destroy(self):
        logger.debug('Deleting {}', self.fullname)
        endpoint = EMBY_ENDPOINT_DELETE_ITEM.format(itemid=self.id)
        additem = EmbyApi.resquest_emby(endpoint, self.auth, 'DELETE')
        if not additem:
            logger.warning('Not possible to delete {}', self.fullname)
            return
        self.id = None
        self._internal_items = []
        self.playlist_bind = {}

    def fill_items(self):
        args = {}

        EmbyApi.set_common_search_arg(args)
        self.set_list_search_args(args)
        if not self.id:
            return

        args['ParentId'] = self.id
        logger.debug('Search PlayList  with: {}', args)
        endpoint = EMBY_ENDPOINT_SEARCH.format(userid=self.auth.uid)
        items = EmbyApi.resquest_emby(endpoint, self.auth, 'GET', **args)
        self._internal_items = items['Items'] if items else []

        self.playlist_bind = {}
        for media in self._internal_items:
            self.playlist_bind[media['Id']] = media['PlaylistItemId']

    def get(self, item):
        item_g = EmbyApiListBase.get(self, item)
        if not item_g or not self.playlist_bind:
            return None

        if self.playlist_bind.get(item.id):
            return item_g

        return None

    def get_items(self):
        if not self.created:
            return []

        self.fill_items()

        for media in self._internal_items:
            media_obj = EmbyApiMedia.cast(auth=self.auth, **media)
            if media_obj:
                yield media_obj

    @staticmethod
    def _get_list_data(auth, **kwargs):
        args = {}

        list_name = kwargs.get('list')

        EmbyApi.set_common_search_arg(args)

        args['SearchTerm'] = list_name
        args['Type'] = 'Playlist'

        logger.debug('Search Playlist Name list with: {}', args)
        search_list_data = EmbyApi.resquest_emby(EMBY_ENDPOINT_SEARCH, auth, 'GET', **args)
        if not search_list_data or not search_list_data['Items']:
            return

        for search_list in search_list_data['Items']:
            if search_list['Name'].lower() == list_name.lower():
                return search_list

    @staticmethod
    def is_type(**kwargs):
        auth = EmbyApi.get_auth(**kwargs)

        list_name = kwargs.get('list')

        list_data = EmbyApiPlayList._get_list_data(auth, list=list_name)
        if not list_data:
            return False

        return True

    @staticmethod
    def create(item, **kwargs):
        auth = EmbyApi.get_auth(**kwargs)

        list_name = kwargs.get('list')

        args = {}
        args['Name'] = list_name
        args['Ids'] = item.id
        logger.debug('Creating playlist \'{}\'', list_name)

        items = EmbyApi.resquest_emby(EMBY_ENDPOINT_NEW_PLAYLIST, auth, 'POST', **args)
        if not items:
            logger.warning('Not possible to create playlist \'{}\'', list_name)
            return

        logger.debug('Returning information of new playlist \'{}\'', items)

        new_playlist = EmbyApiPlayList(auth=auth, **items)
        if not new_playlist.created:
            logger.warning('Not possible to create playlist \'{}\'', list_name)
            return

        logger.debug('Created playlist \'{}\' with id {}', new_playlist.name, new_playlist.id)

        return new_playlist

    @property
    def fullname(self):
        return f'Playlist \'{self.name}\''


class EmbyApiMedia(EmbyApiBase):
    """Basic media"""

    TYPE = 'unknown'

    auth = None

    id = None
    base_name = None
    overview = None
    imdb_id = None
    tmdb_id = None
    tvdb_id = None
    aired_date = None

    source_id = None
    mtype = None
    path = None
    created_date = None
    watched = None
    playcount = None
    favorite = None
    media_sources_raw = None
    format_3d = None
    audio = None
    quality = None
    subtitles = None
    photo_tag = None

    library = None

    field_map = {
        'mtype': ['mtype', 'Type'],
        'id': ['id', 'Id'],
        'search_string': ['search_string'],
        'base_name': ['base_name', 'name', 'Name', 'title'],
        'path': ['path', 'Path'],
        'year': ['ProductionYear'],
        'overview': ['overview', 'Overview'],
        'imdb_id': ['imdb_id', 'ProviderIds.Imdb'],
        'tmdb_id': ['tmdb_id', 'ProviderIds.Tmdb'],
        'tvdb_id': ['tvdb_id', 'ProviderIds.Tvdb'],
        'created_date': ['created_date', 'DateCreated'],
        'aired_date': ['aired_date', 'PremiereDate'],
        'photo_tag': ['photo_tag', 'ImageTags.Primary'],
        'watched': ['watched', 'UserData.Played'],
        'favorite': ['favorite', 'UserData.IsFavorite'],
        'playcount': ['playcount', 'UserData.PlayCount'],
        'format_3d': ['format_3d', 'Video3DFormat'],
    }

    field_to_dic = {}

    def __init__(self, **kwargs):
        if not kwargs:
            return

        myfield_map = EmbyApiMedia.field_map.copy()

        if 'field_map' in kwargs:
            myfield_map = EmbyApiBase.merge_field_map(kwargs.get('field_map'), myfield_map)

        EmbyApiBase.update_using_map(self, EmbyApiMedia.field_map, kwargs)

        self.auth = EmbyApi.get_auth(**kwargs)

        if self.created_date:
            self.created_date = EmbyApi.strtotime(self.created_date)

        if self.aired_date:
            self.aired_date = EmbyApi.strtotime(self.aired_date)

        if self.mtype:
            self.mtype = self.mtype.lower()

        if 'MediaSources' in kwargs:
            self.media_sources_raw = kwargs.get('MediaSources')
            for file in self.media_sources_raw:
                if 'Type' not in file or file.get('Type') != 'Default':
                    continue

                if 'MediaStreams' not in file:
                    continue

                self.source_id = file.get('Id')

                for stream in file.get('MediaStreams'):
                    if stream.get('Type') == 'Video':
                        self.quality = stream.get('DisplayTitle')

                    if stream.get('Type') == 'Subtitle' and stream.get('Language'):
                        if not self.subtitles:
                            self.subtitles = []

                        self.subtitles.append(stream['Language'])

                    if stream.get('Type') == 'Audio' and 'Language' in stream:
                        if not self.audio:
                            self.audio = []

                        self.audio.append(stream['Language'])

        self.library = self.get_libary()

    def _get_parents(self) -> dict:
        if not self.id or not self.auth or not self.auth.uid:
            return

        args = {'userid': self.auth.uid}

        endpoint = EMBY_ENDPOINT_PARENTS.format(itemid=self.id)
        parents = EmbyApi.resquest_emby(endpoint, self.auth, 'GET', **args)
        if not parents:
            return

        return parents

    def get_libary(self) -> 'EmbyApiLibrary':
        parents = self._get_parents()
        if not parents:
            return

        if len(parents) < 2:
            return

        parent = parents[len(parents) - 2]

        library = EmbyApiLibrary(auth=self.auth, **parent)

        return library

    def to_entry(self) -> Entry:
        field_map = get_field_map(**self.to_dict())
        entry = Entry()
        entry.update_using_map(field_map, self.to_dict(), ignore_none=True)

        if self.auth:
            entry['emby_server_id'] = self.auth.server_id
            entry['emby_username'] = self.auth.username
            entry['emby_user_id'] = self.auth.uid

        entry['title'] = self.fullname
        entry['url'] = self.page
        return entry

    def to_dict(self) -> dict:
        if not self:
            return {}

        mtype = self.mtype
        if isinstance(mtype, str):
            mtype = mtype.lower()

        return {
            'id': self.id,
            'name': self.name,
            'fullname': self.fullname,
            'type': mtype,
            'mtype': mtype,
            'media_type': mtype,
            'path': self.path,
            'page': self.page,
            'filename': self.filename,
            'file_extension': self.file_extension,
            'created_date': self.created_date,
            'watched': self.watched,
            'year': self.year,
            'favorite': self.favorite,
            'playcount': self.playcount,
            'media_sources_raw': self.media_sources_raw,
            'format_3d': self.format_3d,
            'audio': self.audio,
            'quality': self.quality,
            'subtitles': self.subtitles,
            'imdb_id': self.imdb_id,
            'tmdb_id': self.tmdb_id,
            'tvdb_id': self.tvdb_id,
            'imdb_url': self.imdb_url,
            'executed': True,
            'source_id': self.source_id,
            'download_url': self.download_url,
            'library_name': self.library_name,
        }

    @staticmethod
    def get_mtype(**kwargs) -> str:
        mtype = None
        if 'mtype' in kwargs:
            mtype = kwargs.get('mtype')
        elif 'Type' in kwargs:
            mtype = kwargs.get('Type')
        elif 'emby_type' in kwargs:
            mtype = kwargs.get('emby_type')

        if not isinstance(mtype, str):
            mtype = ''

        if mtype:
            mtype = mtype.lower()

        return mtype

    @property
    def name(self) -> str:
        return split_title_year(self.base_name).title

    @property
    def fullname(self) -> str:
        return self.name

    @property
    def library_name(self) -> str:
        if not self.library:
            return

        return self.library.name

    @property
    def download_url(self) -> str:
        if not self.auth or not self.auth.token or not self.id:
            return

        if not self.auth.can_download:
            return

        endpoint = EMBY_ENDPOINT_DOWNLOAD.format(itemid=self.id)
        qstr = urlencode({'api_key': self.auth.token, 'mediaSourceId': self.source_id})
        return f'{self.host}{endpoint}?{qstr}'

    @property
    def year(self) -> int:
        if self.aired_date:
            return self.aired_date.year

        year = split_title_year(self.base_name).year
        if year:
            return year

    @property
    def imdb_url(self) -> str:
        if self.imdb_id:
            return f'http://www.imdb.com/title/{self.imdb_id}'

    @property
    def filename(self) -> str:
        if not self.path:
            return

        filename = re.search('([^\\/\\\\]+)$', self.path)
        if filename:
            return filename.group(1)

    @property
    def file_extension(self) -> str:
        if not self.path:
            return

        ext = re.search('\\.([^\\/\\\\]+)$', self.path)
        if ext:
            return ext.group(1)

    @property
    def host(self) -> str:
        if not self.auth:
            return ''

        if self.auth.return_host == 'lan' and self.auth.lanurl:
            host = f'{self.auth.lanurl}@'
        elif self.auth.return_host == 'wan' and self.auth.wanurl:
            host = f'{self.auth.wanurl}@'
        else:
            return f'{self.auth.host}'

        return host.replace(':80@', '').replace(':443@', '').replace('@', '')

    @property
    def page(self) -> str:
        if not self.id:
            return None

        qstr = urlencode({'id': self.id, 'serverId': self.auth.server_id})
        return f'{self.host}/web/index.html#!/item?{qstr}'

    @property
    def photo(self) -> str:
        if not self.photo_tag or not self.id:
            return None

        endpoint = EMBY_ENDPOINT_PHOTOS.format(itemid=self.id)

        qstr = urlencode(
            {
                'Tag': self.photo_tag,
                'CropWhitespace': 'true',
                'EnableImageEnhancers': 'false',
                'Format': 'jpg',
            }
        )

        return f'{self.host}{endpoint}?{qstr}'

    @classmethod
    def get_from_child(cls, child: "EmbyApiMedia") -> "EmbyApiMedia":
        parents = cls._get_parents(child)
        if not parents:
            return None

        for parent in parents:
            if not 'Type' in parent or parent['Type'].lower() != cls.TYPE:
                continue
            season = cls.cast(**parent)
            if isinstance(season, cls):
                return season

    @staticmethod
    def cast(**kwargs) -> 'EmbyApiMedia':
        if EmbyApiEpisode.is_type(**kwargs):
            return EmbyApiEpisode.search(**kwargs)

        if EmbyApiSeason.is_type(**kwargs):
            return EmbyApiSeason.search(**kwargs)

        if EmbyApiSerie.is_type(**kwargs):
            return EmbyApiSerie.search(**kwargs)

        if EmbyApiMovie.is_type(**kwargs):
            return EmbyApiMovie.search(**kwargs)

        return EmbyApiMedia.search(**kwargs)

    @staticmethod
    def parse_string(string: str):
        """Returns Relevante Information from string"""
        if not string:
            return None, None

        name, year = EmbyApiSerie.parse_string(string)
        if name:
            return name, year

        return split_title_year(string)

    @staticmethod
    def search(**kwargs) -> 'EmbyApiMedia':
        args = {}

        auth = EmbyApi.get_auth(**kwargs)
        kwargs['auth'] = auth

        parameters = {}
        EmbyApi.update_using_map(parameters, EmbyApiMedia.field_map, kwargs, allow_new=True)

        EmbyApi.set_common_search_arg(args)

        if 'id' in parameters:
            args['Ids'] = parameters.get('id')
        else:
            if EmbyApi.has_provideres_search_arg(**kwargs):
                EmbyApi.set_provideres_search_arg(args, **kwargs)
            else:
                args['SearchTerm'], year = EmbyApiMedia.parse_string(
                    parameters.get('search_string', parameters.get('base_name', None))
                )

                if not args['SearchTerm']:
                    logger.warning('Not possible to search media, no search term')
                    return

                if parameters.get('year'):
                    args['Years'] = parameters['year']
                elif year:
                    args['Years'] = year

        logger.debug('Search media with: {}', args)
        medias = EmbyApi.resquest_emby(EMBY_ENDPOINT_SEARCH, auth, 'GET', **args)
        if not medias or 'Items' not in medias or not medias['Items']:
            if EmbyApi.has_provideres_search_arg(**parameters):
                EmbyApi.remove_provideres_search(parameters)
                return EmbyApiMedia.search(**parameters)

            logger.warning('No media found')
            return

        media = medias['Items'][0]

        media_api = EmbyApiMedia(auth=auth, **media)

        if media_api.mtype and media_api.mtype != EmbyApiMedia.TYPE:
            return EmbyApi.search(auth=auth, **media_api.to_dict())
        else:
            logger.debug('Found media \'{}\' in emby server', media_api.fullname)

        return media_api


class EmbyApiSerie(EmbyApiMedia):
    """Series"""

    TYPE = 'series'

    field_map_up = {
        'id': 'serie_id',
        'base_name': ['serie_name', 'series_name', 'SeriesName'],
        'imdb_id': 'serie_imdb_id',
        'tmdb_id': 'serie_tmdb_id',
        'tvdb_id': 'serie_tvdb_id',
        'page': 'serie_page',
        'aired_date': 'serie_aired_date',
        'overview': 'serie_overview',
        'photo': 'serie_photo',
        'serie_id': ['serie_id', 'SeriesId'],
        'serie_name': ['serie_name', 'series_name', 'SeriesName'],
        'serie_imdb_id': 'serie_imdb_id',
        'serie_tmdb_id': 'serie_tmdb_id',
        'serie_tvdb_id': 'serie_tvdb_id',
    }

    def __init__(self, **kwargs):
        EmbyApiMedia.__init__(self, field_map=self.field_map_up, **kwargs)

    def to_dict(self) -> dict:
        if not self:
            return {}

        return {
            **EmbyApiMedia.to_dict(self),
            **{
                'serie_id': self.serie_id,
                'serie_name': self.serie_name,
                'serie_imdb_id': self.serie_imdb_id,
                'serie_tmdb_id': self.serie_tmdb_id,
                'serie_tvdb_id': self.serie_tvdb_id,
                'serie_aired_date': self.serie_aired_date,
                'serie_year': self.serie_year,
                'serie_overview': self.serie_overview,
                'serie_photo': self.serie_photo,
                'serie_page': self.serie_page,
            },
        }

    @property
    def serie_id(self) -> str:
        return self.id

    @property
    def serie_name(self) -> str:
        return self.name

    @property
    def serie_overview(self) -> str:
        return self.overview

    @property
    def serie_photo(self) -> str:
        return self.photo

    @property
    def serie_page(self) -> str:
        return self.page

    @property
    def serie_imdb_id(self) -> str:
        return self.imdb_id

    @property
    def serie_tmdb_id(self) -> str:
        return self.tmdb_id

    @property
    def serie_tvdb_id(self) -> str:
        return self.tvdb_id

    @property
    def serie_aired_date(self) -> 'datetime':
        return self.aired_date

    @property
    def serie_year(self) -> int:
        return self.year

    @property
    def fullname(self) -> str:
        if self.year:
            return f'{self.name} ({self.year})'

        return self.name

    @staticmethod
    def parse_string(string: str, force_parse=False):
        """Returns Relevante Information from string"""
        if not string:
            return None, None

        info = re.search(r'(.+) [s]?([0-9]+)[e|x]([0-9]+)', string, re.IGNORECASE)
        if not info or not info.groups():
            info = re.search(r'(.+) [s]([0-9]+)', string, re.IGNORECASE)
            if not info or not info.groups():
                if force_parse:
                    # I assume that it's only a serie if contains pathern, but I might need to assume it's a serie
                    return split_title_year(string)
                else:
                    return None, None

        try:
            info = info.group(1)
        except IndexError:
            return None, None

        return split_title_year(info)

    @staticmethod
    def search(**kwargs) -> 'EmbyApiSerie':
        args = {}

        auth = EmbyApi.get_auth(**kwargs)

        parameters = {}
        field_map = EmbyApiBase.merge_field_map(
            EmbyApiSerie.field_map_up,
            EmbyApiMedia.field_map,
            allow_new=True,
        )

        EmbyApi.update_using_map(parameters, field_map, kwargs, allow_new=True)

        EmbyApi.set_common_search_arg(args)

        if 'serie_id' in parameters:
            args['Ids'] = parameters.get('serie_id')
        else:
            if EmbyApi.has_provideres_search_arg(**parameters):
                EmbyApi.set_provideres_search_arg(args, **parameters)
            else:
                args['SearchTerm'], year = EmbyApiSerie.parse_string(
                    parameters.get('search_string', parameters.get('base_name', None)), True
                )

                if not args['SearchTerm']:
                    logger.warning('Not possible to search series, no search term')
                    return

                if parameters.get('year'):
                    args['Years'] = parameters['year']
                elif year:
                    args['Years'] = year

        args['IncludeItemTypes'] = 'Series'

        logger.debug('Search serie with: {}', args)
        series = EmbyApi.resquest_emby(EMBY_ENDPOINT_SEARCH, auth, 'GET', **args)
        if not series or 'Items' not in series or not series['Items']:
            if EmbyApi.has_provideres_search_arg(**parameters):
                EmbyApi.remove_provideres_search(parameters)
                return EmbyApiSerie.search(**parameters)

            logger.warning('No serie found')
            return

        if len(series['Items']) == 1:
            serie = series['Items'][0]
        elif len(series['Items']) > 1:
            serie_filter = list(
                filter(lambda s: s.get('Name') == args.get('SearchTerm'), series['Items'])
            )

            if args.get('Years'):
                serie_filter = list(
                    filter(lambda s: s.get('Year') == args.get('Years'), serie_filter)
                )

            if len(serie_filter) == 1:
                serie = serie_filter[0]
            else:
                logger.warning('More than one serie found')
                return

        serie_api = EmbyApiSerie(auth=auth, **serie)
        if serie_api:
            logger.debug('Found serie \'{}\' in emby server', serie_api.fullname)
            return serie_api

    @staticmethod
    def is_type(**kwargs) -> bool:
        mtype = EmbyApiMedia.get_mtype(**kwargs)
        if mtype.lower() == EmbyApiSerie.TYPE.lower():
            return True

        if mtype:
            return False

        if kwargs.get('series_name'):
            return True

        serie, _ = EmbyApiSerie.parse_string(
            kwargs.get('search_string', kwargs.get('title', None))
        )
        if serie:
            return True

        return False


class EmbyApiSeason(EmbyApiMedia):
    """Season"""

    TYPE = 'season'

    _serie = None
    season = None

    field_map = {'season': ['season', 'IndexNumber']}

    field_map_up = {
        'id': ['season_id', 'SeasonId'],
        'base_name': 'season_name',
        'imdb_id': 'season_imdb_id',
        'tmdb_id': 'season_tmdb_id',
        'tvdb_id': 'season_tvdb_id',
        'photo': 'season_photo',
        'page': 'season_page',
        'season_id': ['season_id', 'SeasonId'],
        'season_name': 'season_name',
        'season_imdb_id': 'season_imdb_id',
        'season_tmdb_id': 'season_tmdb_id',
        'season_tvdb_id': 'season_tvdb_id',
        'season': ['season', 'series_season'],
    }

    def __init__(self, **kwargs):
        EmbyApiMedia.__init__(self, field_map=self.field_map_up, **kwargs)

        if not kwargs:
            return

        EmbyApiBase.update_using_map(self, EmbyApiSeason.field_map, kwargs)

        if isinstance(kwargs.get('api_serie'), EmbyApiSerie):
            self._serie = kwargs.get('api_serie')
        elif isinstance(self.serie, EmbyApiSerie):
            self._serie = self.serie
        else:
            self._serie = EmbyApiSerie.search(**kwargs) or EmbyApiSerie(auth=self.auth)

    def to_dict(self) -> dict:
        if not self:
            return {}

        return {
            **EmbyApiSerie.to_dict(self.serie),
            **EmbyApiMedia.to_dict(self),
            **{
                'season': self.season,
                'season_id': self.season_id,
                'season_name': self.season_name,
                'season_page': self.season_page,
                'season_photo': self.season_photo,
                'season_imdb_id': self.season_imdb_id,
                'season_tmdb_id': self.season_tmdb_id,
                'season_tvdb_id': self.season_tvdb_id,
            },
        }

    @property
    def fullname(self) -> str:
        if not self.serie:
            return self.name
        elif self.season == 0:
            return f'{self.serie.fullname} S00'
        elif not self.season:
            return f'{self.serie.fullname} Sxx'

        return f'{self.serie.fullname} S{self.season:02d}'

    @property
    def season_name(self) -> str:
        return self.name

    @property
    def season_id(self) -> str:
        return self.id

    @property
    def serie_overview(self) -> str:
        return self.overview

    @property
    def season_imdb_id(self) -> str:
        return self.imdb_id

    @property
    def season_tmdb_id(self) -> str:
        return self.tmdb_id

    @property
    def season_tvdb_id(self) -> str:
        return self.tvdb_id

    @property
    def season_photo(self) -> str:
        return self.photo

    @property
    def season_page(self) -> str:
        return self.page

    @property
    def serie(self) -> EmbyApiSerie:
        if isinstance(self._serie, EmbyApiSerie):
            return self._serie

        self._serie = EmbyApiSerie.get_from_child(self)
        return self._serie

    @staticmethod
    def is_type(**kwargs) -> bool:
        mtype = EmbyApiMedia.get_mtype(**kwargs)
        if mtype.lower() == EmbyApiSeason.TYPE.lower():
            return True

        if mtype:
            return False

        if (
            EmbyApiSerie.is_type(**kwargs)
            and 'series_season' in kwargs
            and not EmbyApiEpisode.is_type(**kwargs)
        ):
            return True

        if EmbyApiSeason.parse_string(kwargs.get('title')):
            return True

        if EmbyApiSeason.parse_string(kwargs.get('search_string')):
            return True

        return False

    @staticmethod
    def parse_string(string: str):
        """Returns Relevante Information from string"""
        if not string:
            return None

        info = re.search(r'(.+) [s]?([0-9]+)[e|x]([0-9]+)', string, re.IGNORECASE)
        if not info or not info.groups():
            info = re.search(r'(.+) [s]([0-9]+)', string, re.IGNORECASE)
            if not info or not info.groups():
                return None

        try:
            return str_to_int(info.group(2))
        except IndexError:
            return None

    @staticmethod
    def search(**kwargs) -> 'EmbyApiSeason':
        args = {}

        auth = EmbyApi.get_auth(**kwargs)
        kwargs['auth'] = auth

        parameters = {}
        field_map = EmbyApiBase.merge_field_map(
            EmbyApiSeason.field_map_up,
            EmbyApiSerie.field_map_up,
            EmbyApiMedia.field_map,
            allow_new=True,
        )

        EmbyApi.update_using_map(parameters, field_map, kwargs, allow_new=True)

        # We need to have information regarding the series
        season_serie = None
        if 'api_serie' in kwargs:
            season_serie = kwargs.get('api_serie')

        if not season_serie:
            season_serie = EmbyApiSerie.search(**kwargs)

        if not season_serie:
            logger.warning('Not possible to determine season, serie not found')
            return

        if 'season_id' in parameters:
            args['Ids'] = parameters.get('season_id')
        else:
            args['ParentId'] = season_serie.serie_id

        args['IncludeItemTypes'] = 'Season'

        EmbyApi.set_common_search_arg(args)

        logger.debug('Search season with: {}', args)
        seasons = EmbyApi.resquest_emby(EMBY_ENDPOINT_SEARCH, auth, 'GET', **args)
        if not seasons or 'Items' not in seasons or not seasons['Items']:
            logger.warning('No season found')
            return

        seasons = seasons['Items']

        target_season = parameters.get('season', None)
        if not target_season:
            target_season = EmbyApiSeason.parse_string(
                parameters.get('search_string', parameters.get('base_name', None))
            )

        if target_season:
            seasons_filter = []
            seasons_filter = list(filter(lambda s: s.get('IndexNumber') == target_season, seasons))
            seasons = seasons_filter

        if len(seasons) == 1:
            season = seasons[0]
        elif len(seasons) > 1:
            logger.warning(
                'More than one season found for {} {}', season_serie.fullname, target_season
            )
            return
        else:
            logger.warning('No season found')
            return

        season_api = EmbyApiSeason(auth=auth, api_serie=season_serie, **season)
        if season_api:
            logger.debug('Found season \'{}\' in emby server', season_api.fullname)
            return season_api


class EmbyApiEpisode(EmbyApiMedia):
    """Episode"""

    TYPE = 'episode'

    _serie = None
    _season = None
    episode = None

    field_map = {'episode': ['episode', 'IndexNumber']}

    field_map_up = {
        'id': 'ep_id',
        'base_name': 'ep_name',
        'imdb_id': 'ep_imdb_id',
        'tmdb_id': 'ep_tmdb_id',
        'tvdb_id': 'ep_tvdb_id',
        'aired_date': 'ep_aired_date',
        'photo': 'ep_photo',
        'page': 'ep_page',
        'ep_id': 'ep_id',
        'ep_name': 'ep_name',
        'ep_imdb_id': 'ep_imdb_id',
        'ep_tmdb_id': 'ep_tmdb_id',
        'ep_tvdb_id': 'ep_tvdb_id',
        'episode': ['episode', 'series_episode'],
    }

    episode = None

    def __init__(self, **kwargs):
        EmbyApiMedia.__init__(self, field_map=self.field_map_up, **kwargs)

        if not kwargs:
            return

        EmbyApiBase.update_using_map(self, EmbyApiEpisode.field_map, kwargs)

        if isinstance(kwargs.get('api_serie'), EmbyApiSerie):
            self._serie = kwargs.get('api_serie')
        elif isinstance(self.serie, EmbyApiSerie):
            self._serie = self.serie
        else:
            self._serie = EmbyApiSerie.search(**kwargs) or EmbyApiSerie(auth=self.auth)

        if isinstance(kwargs.get('api_season'), EmbyApiSeason):
            self._season = kwargs.get('api_season')
        elif isinstance(self.season, EmbyApiSeason):
            self._season = self.season
        else:
            self._season = EmbyApiSeason.search(**kwargs) or EmbyApiSeason(auth=self.auth)

    def to_dict(self) -> dict:
        if not self:
            return {}

        return {
            **EmbyApiSeason.to_dict(self.season),
            **EmbyApiSerie.to_dict(self.serie),
            **EmbyApiMedia.to_dict(self),
            **{
                'episode': self.episode,
                'ep_id': self.ep_id,
                'ep_name': self.ep_name,
                'ep_page': self.ep_page,
                'ep_photo': self.ep_photo,
                'ep_imdb_id': self.ep_imdb_id,
                'ep_tmdb_id': self.ep_tmdb_id,
                'ep_tvdb_id': self.ep_tvdb_id,
                'ep_aired_date': self.ep_aired_date,
                'ep_overview': self.ep_overview,
            },
        }

    @property
    def fullname(self) -> str:
        if not self.serie:
            return self.name
        elif not self.season:
            return f'{self.serie.fullname} SxxExx'
        elif self.episode == 0:
            return f'{self.serie.fullname} S{self.season.season:02d}E00'
        elif not self.episode:
            return f'{self.serie.fullname} S{self.season.season:02d}Exx'

        return f'{self.serie.fullname} S{self.season.season:02d}E{self.episode:02d} {self.name}'

    @property
    def ep_id(self) -> str:
        return self.id

    @property
    def ep_name(self) -> str:
        return self.name

    @property
    def ep_imdb_id(self) -> str:
        return self.imdb_id

    @property
    def ep_tmdb_id(self) -> str:
        return self.tmdb_id

    @property
    def ep_tvdb_id(self) -> str:
        return self.tvdb_id

    @property
    def ep_photo(self) -> str:
        return self.photo

    @property
    def ep_overview(self) -> str:
        return self.overview

    @property
    def ep_page(self) -> str:
        return self.page

    @property
    def ep_aired_date(self) -> 'datetime':
        return self.aired_date

    @property
    def season(self) -> EmbyApiSeason:
        if isinstance(self._season, EmbyApiSeason):
            return self._season

        self._season = EmbyApiSeason.get_from_child(self)
        return self._season

    @property
    def serie(self) -> EmbyApiSerie:
        if isinstance(self._serie, EmbyApiSerie):
            return self._serie

        self._serie = EmbyApiSerie.get_from_child(self)
        return self._serie

    @staticmethod
    def search(**kwargs) -> 'EmbyApiEpisode':
        episode_serie = None
        episode_season = None

        auth = EmbyApi.get_auth(**kwargs)
        kwargs['auth'] = auth

        args = {}

        parameters = {}
        field_map = EmbyApiBase.merge_field_map(
            EmbyApiEpisode.field_map,
            EmbyApiEpisode.field_map_up,
            EmbyApiSeason.field_map_up,
            EmbyApiSerie.field_map_up,
            EmbyApiMedia.field_map,
            allow_new=True,
        )

        EmbyApi.update_using_map(parameters, field_map, kwargs, allow_new=True)

        # We need to have information regarding the series
        if 'api_serie' in kwargs:
            episode_serie = kwargs.get('api_serie')

        if not episode_serie:
            episode_serie = EmbyApiSerie.search(**kwargs)

        if not episode_serie:
            logger.warning('Not possible to determine episode, serie not found')
            return

        # We need to have information regarding the season
        if 'api_season' in kwargs:
            episode_season = kwargs.get('api_season')

        if not episode_season:
            episode_season = EmbyApiSeason.search(api_serie=episode_serie, **kwargs)

        if not episode_season:
            logger.warning('Not possible to determine episode, season not found')
            return

        # We need to return all the episodes for that show/season
        if 'ep_id' in parameters:
            args['Ids'] = parameters.get('ep_id')
        elif episode_season and episode_season.season_id:
            args['ParentId'] = episode_season.season_id
        elif episode_serie and episode_serie.serie_id:
            args['ParentId'] = episode_serie.serie_id

        EmbyApi.set_common_search_arg(args)
        args['IncludeItemTypes'] = 'Episode'

        logger.debug('Search episode with: {}', args)
        response = EmbyApi.resquest_emby(EMBY_ENDPOINT_SEARCH, auth, 'GET', **args)
        if not response or 'Items' not in response or not response['Items']:
            logger.warning('No episode found')
            return

        episodes = response['Items']
        if len(episodes) == 0:
            logger.warning('No episode found')
            return

        target_episode = None
        if 'Ids' in args:
            target_episode = episodes[0].get('IndexNumber', None)

        if not target_episode:
            target_episode = parameters.get('episode')

        if not target_episode:
            target_episode = EmbyApiEpisode.parse_string(
                parameters.get('search_string', parameters.get('base_name', None))
            )

        episode = []
        episode = list(filter(lambda e: e.get('IndexNumber') == target_episode, episodes))

        if len(episode) > 1:
            logger.warning("More than one episode found")
            return
        elif len(episode) == 0:
            logger.warning(
                'Episodes found for {} but none matches {}',
                episode_season.fullname,
                target_episode,
            )
            return

        episode_api = EmbyApiEpisode(
            auth=auth,
            api_serie=episode_serie,
            api_season=episode_season,
            **episode[0],
        )

        if episode_api:
            logger.debug('Found episode \'{}\' in emby server', episode_api.fullname)
            return episode_api

    @staticmethod
    def parse_string(string: str):
        """Returns Relevante Information from string"""
        if not string:
            return None

        info = re.search(r'(.+) [s]?([0-9]+)[e|x]([0-9]+)', string, re.IGNORECASE)
        if not info or not info.groups():
            return None

        try:
            return str_to_int(info.group(3))
        except IndexError:
            return None

    @staticmethod
    def is_type(**kwargs) -> bool:
        mtype = EmbyApiMedia.get_mtype(**kwargs)
        if mtype.lower() == EmbyApiEpisode.TYPE.lower():
            return True

        if mtype:
            return False

        if (
            EmbyApiSerie.is_type(**kwargs)
            and 'series_season' in kwargs
            and 'series_episode' in kwargs
        ):
            return True

        if EmbyApiEpisode.parse_string(kwargs.get('search_string', kwargs.get('title'))):
            return True

        return False


class EmbyApiMovie(EmbyApiMedia):
    """Movie"""

    TYPE = 'movie'

    field_map_up = {
        'id': 'movie_id',
        'base_name': 'movie_name',
        'imdb_id': 'movie_imdb_id',
        'tmdb_id': 'movie_tmdb_id',
        'tvdb_id': 'movie_tvdb_id',
        'aired_date': 'movie_aired_date',
        'year': 'movie_year',
        'photo': 'movie_photo',
        'page': 'movie_page',
        'overview': 'movie_overview',
        'movie_id': 'movie_id',
        'movie_name': 'movie_name',
        'movie_imdb_id': 'movie_imdb_id',
        'movie_tmdb_id': 'movie_tmdb_id',
        'movie_tvdb_id': 'movie_tvdb_id',
        'movie_year': 'movie_year',
    }

    def __init__(self, **kwargs):
        EmbyApiMedia.__init__(self, field_map=EmbyApiMovie.field_map_up, **kwargs)
        self.mtype = EmbyApiMovie.TYPE

    def to_dict(self) -> dict:
        if not self:
            return {}

        return {
            **EmbyApiMedia.to_dict(self),
            **{
                'movie_id': self.movie_id,
                'movie_name': self.movie_name,
                'movie_imdb_id': self.movie_imdb_id,
                'movie_tmdb_id': self.movie_tmdb_id,
                'movie_tvdb_id': self.movie_tvdb_id,
                'movie_aired_date': self.movie_aired_date,
                'movie_year': self.movie_year,
                'movie_photo': self.movie_photo,
                'movie_page': self.movie_page,
                'movie_overview': self.movie_overview,
            },
        }

    @property
    def fullname(self):
        return f'{self.name} ({self.year})'

    @property
    def movie_id(self) -> str:
        return self.id

    @property
    def movie_name(self) -> str:
        return self.name

    @property
    def movie_page(self) -> str:
        return self.page

    @property
    def movie_imdb_id(self) -> str:
        return self.imdb_id

    @property
    def movie_tmdb_id(self) -> str:
        return self.tmdb_id

    @property
    def movie_tvdb_id(self) -> str:
        return self.tvdb_id

    @property
    def movie_overview(self) -> str:
        return self.overview

    @property
    def movie_photo(self) -> str:
        return self.photo

    @property
    def movie_aired_date(self) -> 'datetime':
        return self.aired_date

    @property
    def movie_year(self) -> int:
        return self.year

    @staticmethod
    def parse_string(string: str):
        """Returns Relevante Information from string"""
        if not string:
            return None, None

        return split_title_year(string)

    @staticmethod
    def search(**kwargs) -> 'EmbyApiMovie':
        args = {}

        auth = EmbyApi.get_auth(**kwargs)
        kwargs['auth'] = auth

        parameters = {}
        field_map = EmbyApiBase.merge_field_map(
            EmbyApiMovie.field_map_up,
            EmbyApiMedia.field_map,
            allow_new=True,
        )

        EmbyApi.update_using_map(parameters, field_map, kwargs, allow_new=True)

        EmbyApi.set_common_search_arg(args)

        if 'movie_id' in parameters:
            args['Ids'] = parameters.get('movie_id')
        elif 'id' in parameters:
            args['Ids'] = parameters.get('id')
        else:
            if EmbyApi.has_provideres_search_arg(**parameters):
                EmbyApi.set_provideres_search_arg(args, **parameters)
            else:
                args['SearchTerm'], year = EmbyApiMovie.parse_string(
                    parameters.get('search_string', parameters.get('base_name', None))
                )

                if not args['SearchTerm']:
                    logger.warning('Not possible to search movie, no search term')
                    return

                if parameters.get('year'):
                    args['Years'] = parameters['year']
                elif year:
                    args['Years'] = year

        args['IncludeItemTypes'] = 'Movie'

        logger.debug('Search movie with: {}', args)
        movies = EmbyApi.resquest_emby(EMBY_ENDPOINT_SEARCH, auth, 'GET', **args)
        if not movies or 'Items' not in movies or not movies['Items']:
            if EmbyApi.has_provideres_search_arg(**parameters):
                EmbyApi.remove_provideres_search(parameters)
                return EmbyApiMovie.search(**parameters)

            logger.warning('No movie found')
            return

        if len(movies['Items']) == 1:
            movie = movies['Items'][0]
        if len(movies['Items']) > 1:
            movie_filter = list(
                filter(lambda s: s.get('Name') == args.get('SearchTerm'), movies['Items'])
            )

            if args.get('Years'):
                movie_filter = list(
                    filter(lambda s: s.get('Year') == args.get('Years'), movie_filter)
                )

            if len(movie_filter) == 1:
                movie = movie_filter[0]
            else:
                logger.warning("More than one movie found")
                return

        movie_api = EmbyApiMovie(auth=auth, **movie)
        if movie_api:
            logger.debug('Found movie {} in emby server', movie_api.fullname)
            return movie_api

    @staticmethod
    def is_type(**kwargs) -> bool:
        mtype = EmbyApiMedia.get_mtype(**kwargs)
        if mtype.lower() == EmbyApiMovie.TYPE.lower():
            return True

        if mtype:
            return False

        if kwargs.get('movie_name'):
            return True

        movie, _ = EmbyApiMovie.parse_string(
            kwargs.get('title', kwargs.get('search_string', None))
        )
        if movie:
            return True

        return False


class EmbyApi(EmbyApiBase):
    """
    Class to interact with Emby API
    """

    _last_auth = None

    auth = None

    EMBY_EXTRA_FIELDS = [
        'DateCreated',
        'Path',
        'ProviderIds',
        'PremiereDate',
        'MediaSources',
        'Video3DFormat',
        'Overview',
    ]

    def __init__(self, auth: 'EmbyAuth'):
        self.auth = auth
        EmbyApi._last_auth = auth

    @staticmethod
    def set_common_search_arg(args: dict):
        args['Recursive'] = True
        args['Fields'] = ','.join(EmbyApi.EMBY_EXTRA_FIELDS)
        args['IsMissing'] = False

    @staticmethod
    def set_provideres_search_arg(args: dict, **kwargs):
        providers = []

        if 'imdb_id' in kwargs and kwargs['imdb_id']:
            providers.append(f'imdb.{kwargs.get("imdb_id")}')
        if 'tmdb_id' in kwargs and kwargs['tmdb_id']:
            providers.append(f'tmdb.{kwargs.get("tmdb_id")}')
        if 'tvdb_id' in kwargs and kwargs['tvdb_id']:
            providers.append(f'tvdb.{kwargs.get("tvdb_id")}')
        if 'tvrage_id' in kwargs and kwargs['tvrage_id']:
            providers.append(f'tvrage.{kwargs.get("tvrage_id")}')

        providers = list(dict.fromkeys(providers))

        providers_str = ';'.join(providers)
        if not providers_str:
            return

        args['AnyProviderIdEquals'] = providers_str

    @staticmethod
    def remove_provideres_search(args: dict):
        args.pop('imdb_id', None)
        args.pop('tmdb_id', None)
        args.pop('tvdb_id', None)
        args.pop('tvrage_id', None)

    @staticmethod
    def has_provideres_search_arg(**kwargs) -> bool:
        providers = {}
        EmbyApi.set_provideres_search_arg(providers, **kwargs)

        if providers and providers['AnyProviderIdEquals']:
            return True

        return False

    @staticmethod
    def get_auth(**kwargs) -> EmbyAuth:
        if 'auth' in kwargs:
            return kwargs['auth']
        elif EmbyApi._last_auth:
            return EmbyApi._last_auth
        elif EmbyAuth.get_last_auth():
            return EmbyAuth.get_last_auth()

        return EmbyAuth(**kwargs)

    @staticmethod
    def search(**kwargs):
        search_result = None

        if 'auth' not in kwargs:
            kwargs['auth'] = EmbyApi.get_auth(**kwargs)

        if EmbyApiEpisode.is_type(**kwargs):
            logger.debug("API search episode")
            search_result = EmbyApiEpisode.search(**kwargs)
        elif EmbyApiSeason.is_type(**kwargs):
            logger.debug("API search season")
            search_result = EmbyApiSeason.search(**kwargs)
        elif EmbyApiSerie.is_type(**kwargs):
            logger.debug("API search serie")
            search_result = EmbyApiSerie.search(**kwargs)
        elif EmbyApiMovie.is_type(**kwargs):
            logger.debug("API search movie")
            search_result = EmbyApiMovie.search(**kwargs)
        elif 'executed' not in kwargs:
            logger.debug("API search unknown media")
            search_result = EmbyApiMedia.search(**kwargs)

        if not search_result:
            return None

        if isinstance(search_result, dict):
            return search_result
        elif isinstance(search_result, EmbyApiMedia):
            return search_result.to_dict()
        else:
            return None

    @staticmethod
    def search_list(**kwargs):
        if 'auth' not in kwargs:
            kwargs['auth'] = EmbyApi.get_auth(**kwargs)

        mlist = kwargs.get('list')

        list_object = EmbyApiList.get_api_list(**kwargs)
        if not list_object:
            raise PluginError('List \'%s\' does not exist' % mlist)

        mlist = list_object.get_items()

        for list_obj in mlist:
            yield list_obj

    @staticmethod
    def strtotime(date) -> 'datetime':
        # YYYY-MM-DDTHH:MM:SS.0000000+00:00

        if not date:
            return None
        elif isinstance(date, datetime):
            return date
        elif not isinstance(date, str):
            return None

        # Normalize date
        date_py = re.sub(r'^(.*)\.([0-9]{6})[0-9]*\+([0-9]{2})\:([0-9]{2})$', r'\1.\2+\3\4', date)

        try:
            date = datetime.strptime(date_py, '%Y-%m-%dT%H:%M:%S.%f%z')
        except ValueError:
            date = None

        return date

    @staticmethod
    def get_type(**kwargs) -> bool:
        if EmbyApiEpisode.is_type(**kwargs):
            return EmbyApiEpisode.TYPE
        elif EmbyApiSeason.is_type(**kwargs):
            return EmbyApiSeason.TYPE
        elif EmbyApiSerie.is_type(**kwargs):
            return EmbyApiSerie.TYPE
        elif EmbyApiMovie.is_type(**kwargs):
            return EmbyApiMovie.TYPE

        return EmbyApiMedia.TYPE

    @staticmethod
    def resquest_emby(endpoint: str, auth: 'EmbyAuth', method: str, emby_connect=False, **kwargs):
        verify_certificates = True if emby_connect else False

        if not auth:
            auth = EmbyApi.get_auth(**kwargs)
            return

        if not auth.host:
            raise PluginError('No Emby server information')

        if auth:
            endpoint = endpoint.format(userid=auth.uid)

        if not auth:
            auth = EmbyApi.get_auth(**kwargs)

        url = f'{auth.host}{endpoint}' if not emby_connect else f'{EMBY_CONNECT}{endpoint}'

        if EMBY_ENDPOINT_CONNECT_EXCHANGE in endpoint:
            request_headers = {}
            request_headers['X-Emby-Token'] = auth._connect_token_link
        else:
            request_headers = auth.add_token_header({}, emby_connect=emby_connect)

        try:
            if method == 'POST':
                response = requests.post(
                    url,
                    json=kwargs,
                    headers=request_headers,
                    allow_redirects=True,
                    verify=verify_certificates,
                )
            elif method == 'GET':
                response = requests.get(
                    url,
                    params=kwargs,
                    headers=request_headers,
                    allow_redirects=True,
                    verify=verify_certificates,
                )
            elif method == 'DELETE':
                response = requests.request(
                    'DELETE',
                    url,
                    params=kwargs,
                    headers=request_headers,
                    allow_redirects=True,
                    verify=verify_certificates,
                )
        except HTTPError as e:  # Autentication Problem
            if e.response.status_code == 401:
                logger.error('Autentication Error: {}', str(e))
                return False
            else:
                raise PluginError('Could not connect to Emby Server: %s' % str(e)) from e
        except RequestException as e:
            raise PluginError('Could not connect to Emby Server: %s' % str(e)) from e

        if response.status_code == 200 or response.status_code == 204:
            try:
                return response.json()
            except ValueError:
                return {'code': response.status_code}

        return False
