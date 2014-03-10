import logging

from sqlalchemy import Column, Unicode, Integer, PickleType, DateTime
from requests.utils import dict_from_cookiejar, cookiejar_from_dict
from datetime import datetime, timedelta
from urlparse import urlparse

from flexget.db_schema import versioned_base
from flexget.manager import Session as db_Session
from flexget.utils.requests import Session as requests_Session

Base = versioned_base('common_authentication', 0)

class CookiesDatabase(Base):
    __tablename__ = 'auth_cookies'
    id = Column(Integer, primary_key=True, autoincrement=True, nullable=False)
    hostname = Column(Unicode, index=True)
    username = Column(Unicode)
    cookiejar = Column(PickleType)
    expires = Column(DateTime)
    cookies_created = Column(DateTime)

class Authentication(object):
    """ Class for authenticating to remote host.
     main `Authenticate()` method will return `flexget.utils.requests` `Session` with already injected cookies.

     You can optionally override cookie loading from database and login directly by invoking class with force_login=True
    """
    def __init__(self, username, post_url, post_params, force_login=False):
        self.session = requests_Session()
        self.db_session = db_Session()
        self.log = logging.getLogger('common_authentication')

        self.force_login = force_login
        self.post_params = post_params
        self.post_url = post_url
        self.username = username

    def Authenticate(self):
        db = self._find_cookies_in_database()

        if db:
            if db.expires < datetime.now() or self.force_login is True:
                self.log.debug('Cookies for %s expired, removing from database...' % self._hostname)
                self.db_session.delete(db)
                self.db_session.commit()
                self._login()
            else:
                self.log.debug('Cookies for %s loaded from database' % self._hostname)
                cookiejar = cookiejar_from_dict(db.cookiejar)
                self.session.add_cookiejar(cookiejar)
        else:
            self._login()

        return self.session

    @property
    def cookies_age(self):
        db = self._find_cookies_in_database()
        created = db.cookies_created
        diff = datetime.now() - created
        return diff.seconds

    def _find_cookies_in_database(self):
        return self.db_session.query(CookiesDatabase).filter(
            CookiesDatabase.hostname == self._hostname, CookiesDatabase.username == self.username).first()

    def _add_to_database(self):
        cj = dict_from_cookiejar(self.session.cookies)
        expires = [cookie.expires for cookie in self.session.cookies if isinstance(cookie.expires, int)]
        expires = datetime.fromtimestamp(min(expires))
        self.log.debug('Adding cookies for %s to database' % self._hostname)
        self.db_session.add(CookiesDatabase(
            username=self.username, cookiejar=cj, hostname=self._hostname,
            expires=expires, cookies_created=datetime.now()
        ))
        return self.db_session.commit()

    @property
    def _hostname(self):
        hostname = urlparse(self.post_url).hostname
        if hostname.startswith('www.'):
            return ".".join(hostname.split('.')[1:])
        return hostname

    def _login(self):
        self.log.debug('Logging in to %s...' % self._hostname)
        self.session.post(self.post_url, data=self.post_params)
        self._add_to_database()