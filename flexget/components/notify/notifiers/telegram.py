from distutils.version import LooseVersion

from loguru import logger
from sqlalchemy import Column, Integer, String

from flexget import db_schema, plugin
from flexget.event import event
from flexget.manager import Session
from flexget.plugin import PluginError, PluginWarning

try:
    import telegram
    from telegram.error import TelegramError
    from telegram.utils.request import NetworkError
except ImportError:
    telegram = None

_MIN_TELEGRAM_VER = '3.4'

_PLUGIN_NAME = 'telegram'

_PARSERS = ['markdown', 'html']

_DISABLE_PREVIEWS_ATTR = 'disable_previews'
_TOKEN_ATTR = 'bot_token'
_PARSE_ATTR = 'parse_mode'
_RCPTS_ATTR = 'recipients'
_USERNAME_ATTR = 'username'
_FULLNAME_ATTR = 'fullname'
_FIRSTNAME_ATTR = 'first'
_SURNAME_ATTR = 'sur'
_GROUP_ATTR = 'group'
_SOCKSPROXY_ATTR = 'socks_proxy'
_SOCKSPROXYURL_ATTR = 'url'
_SOCKSPROXYUSERNAME_ATTR = 'username'
_SOCKSPROXYPASSWORD_ATTR = 'password'

ChatIdsBase = db_schema.versioned_base('telegram_chat_ids', 0)

logger = logger.bind(name=_PLUGIN_NAME)


class ChatIdEntry(ChatIdsBase):
    __tablename__ = 'telegram_chat_ids'

    id = Column(Integer, primary_key=True)
    username = Column(String, index=True, nullable=True)
    firstname = Column(String, index=True, nullable=True)
    surname = Column(String, index=True, nullable=True)
    group = Column(String, index=True, nullable=True)

    def __str__(self):
        x = ['id={0}'.format(self.id)]
        if self.username:
            x.append('username={0}'.format(self.username))
        if self.firstname:
            x.append('firstname={0}'.format(self.firstname))
        if self.surname:
            x.append('surname={0}'.format(self.surname))
        if self.group:
            x.append('group={0}'.format(self.group))
        return ' '.join(x)


class TelegramNotifier:
    """Send a message to one or more Telegram users or groups upon accepting a download.


    Preparations::

    * Install 'python-telegram-bot' python pkg (i.e. `pip install python-telegram-bot`)
    * Create a bot & obtain a token for it (see https://core.telegram.org/bots#botfather).
    * For direct messages (not to a group), start a conversation with the bot and click "START" in the Telegram app.
    * For group messages, add the bot to the desired group and send a start message to the bot: "/start" (mind the
      leading '/').


    Configuration example::

    my-task:
      notify:
        title: {{title}}
        message: {{title}}
        entries:
          via:
            telegram:
              bot_token: token
              use_markdown: no
              disable_previews: yes
              recipients:
                - username: my-user-name
                - group: my-group-name
                - fullname:
                    first: my-first-name
                    sur: my-sur-name
              socks_proxy:
                url: socks-proxy-url
                username: socks-proxy-username
                password: socks-proxy-password


    Bootstrapping and testing the bot::

    * Execute: `flexget telegram bootstrap`.
      Look at the console output and make sure that the operation was successful.
    * Execute: `flexget telegram test-msg`.
      This will send a test message for every recipient you've configured.


    Configuration notes::

    You may use any combination of recipients types (`username`, `group` or `fullname`) - 0 or more of each (but you
    need at least one total...).

    `parse_mode`::
    Optional. Whether the template uses `markdown` or `html` formatting.

    NOTE: The markdown parser will fall back to basic parsing if there is a parsing error. This can be cause due to
    unclosed tags (watch out for wandering underscore when using markdown)

    `username` vs. `fullname`::

    Not all Telegram users have a username. In such cases you would have to use the `fullname` approach. Otherwise, it
    is much easier to use the `username` configuration.

    """

    _token = None
    _usernames = None
    _fullnames = None
    _groups = None
    _bot = None

    schema = {
        'type': 'object',
        'properties': {
            _TOKEN_ATTR: {'type': 'string'},
            _PARSE_ATTR: {'type': 'string', 'enum': _PARSERS},
            _DISABLE_PREVIEWS_ATTR: {'type': 'boolean', 'default': False},
            _RCPTS_ATTR: {
                'type': 'array',
                'minItems': 1,
                'items': {
                    'oneOf': [
                        {
                            'type': 'object',
                            'properties': {_USERNAME_ATTR: {'type': 'string'}},
                            'required': [_USERNAME_ATTR],
                            'additionalProperties': False,
                        },
                        {
                            'type': 'object',
                            'properties': {
                                _FULLNAME_ATTR: {
                                    'type': 'object',
                                    'properties': {
                                        _FIRSTNAME_ATTR: {'type': 'string'},
                                        _SURNAME_ATTR: {'type': 'string'},
                                    },
                                    'required': [_FIRSTNAME_ATTR, _SURNAME_ATTR],
                                    'additionalProperties': False,
                                }
                            },
                            'required': [_FULLNAME_ATTR],
                            'additionalProperties': False,
                        },
                        {
                            'type': 'object',
                            'properties': {_GROUP_ATTR: {'type': 'string'}},
                            'required': [_GROUP_ATTR],
                            'additionalProperties': False,
                        },
                    ]
                },
            },
            _SOCKSPROXY_ATTR: {
                'type': 'object',
                'properties': {
                    _SOCKSPROXYURL_ATTR: {'type': 'string'},
                    _SOCKSPROXYUSERNAME_ATTR: {'type': 'string'},
                    _SOCKSPROXYPASSWORD_ATTR: {'type': 'string'},
                },
                'required': [_SOCKSPROXYURL_ATTR],
                'additionalProperties': False,
            },
        },
        'required': [_TOKEN_ATTR, _RCPTS_ATTR],
        'additionalProperties': False,
    }

    def notify(self, title, message, config):
        """
        Send a Telegram notification
        """
        chat_ids = self._real_init(Session(), config)

        if not chat_ids:
            return
        self._send_msgs(message, chat_ids)

    def _parse_config(self, config):
        """
        :type config: dict

        """
        self._token = config[_TOKEN_ATTR]
        self._parse_mode = config.get(_PARSE_ATTR)
        self._disable_previews = config[_DISABLE_PREVIEWS_ATTR]
        self._usernames = []
        self._fullnames = []
        self._groups = []

        for i in config[_RCPTS_ATTR]:
            if _USERNAME_ATTR in i:
                self._usernames.append(i[_USERNAME_ATTR])
            elif _FULLNAME_ATTR in i:
                fullname = i[_FULLNAME_ATTR]
                firstname = fullname[_FIRSTNAME_ATTR]
                surname = fullname[_SURNAME_ATTR]
                self._fullnames.append((firstname, surname))
            elif _GROUP_ATTR in i:
                self._groups.append(i[_GROUP_ATTR])

        self._socks_proxy_url = None
        self._socks_proxy_username = None
        self._socks_proxy_password = None
        socksproxy = config.get(_SOCKSPROXY_ATTR)
        if socksproxy:
            self._socks_proxy_url = socksproxy[_SOCKSPROXYURL_ATTR]
            self._socks_proxy_username = socksproxy.get(_SOCKSPROXYUSERNAME_ATTR)
            self._socks_proxy_password = socksproxy.get(_SOCKSPROXYPASSWORD_ATTR)

    def _real_init(self, session, config):
        self._enforce_telegram_plugin_ver()
        self._parse_config(config)
        logger.debug(
            'token={}, parse_mode={}, disable_previews={}, usernames={}, fullnames={}, groups={}',
            self._token,
            self._parse_mode,
            self._disable_previews,
            self._usernames,
            self._fullnames,
            self._groups,
        )
        self._init_bot()
        chat_ids = self._get_chat_ids_n_update_db(session)
        return chat_ids

    def _init_bot(self):
        self._bot = telegram.Bot(self._token, request=self._get_request())
        self._check_token()

    def _get_request(self):
        request = None
        if self._socks_proxy_url:
            urllib3_proxy_kwargs = None
            if self._socks_proxy_username and self._socks_proxy_password:
                urllib3_proxy_kwargs = {
                    'username': self._socks_proxy_username,
                    'password': self._socks_proxy_password,
                }
            request = telegram.utils.request.Request(
                proxy_url=self._socks_proxy_url, urllib3_proxy_kwargs=urllib3_proxy_kwargs
            )

        return request

    def _check_token(self):
        try:
            self._bot.getMe()
        except UnicodeDecodeError as e:
            logger.trace('bot.getMe() raised: {}', repr(e))
            raise plugin.PluginWarning('invalid bot token')
        except (NetworkError, TelegramError) as e:
            logger.error(
                'Could not connect Telegram servers at this time, please try again later: {}',
                e.message,
            )

    @staticmethod
    def _enforce_telegram_plugin_ver():
        if telegram is None:
            raise plugin.PluginWarning('missing python-telegram-bot pkg')
        elif not hasattr(telegram, str('__version__')):
            raise plugin.PluginWarning('invalid or old python-telegram-bot pkg')
        elif LooseVersion(telegram.__version__) < _MIN_TELEGRAM_VER:
            raise plugin.PluginWarning(
                'old python-telegram-bot ({0})'.format(telegram.__version__)
            )

    def _send_msgs(self, msg, chat_ids):
        kwargs = dict()
        if self._parse_mode == 'markdown':
            kwargs['parse_mode'] = telegram.ParseMode.MARKDOWN
        elif self._parse_mode == 'html':
            kwargs['parse_mode'] = telegram.ParseMode.HTML
        kwargs['disable_web_page_preview'] = self._disable_previews
        for chat_id in (x.id for x in chat_ids):
            try:
                logger.debug('sending msg to telegram servers: {}', msg)
                self._bot.sendMessage(chat_id=chat_id, text=msg, **kwargs)
            except TelegramError as e:
                if kwargs.get('parse_mode'):
                    logger.warning(
                        'Failed to render message using parse mode {}. Falling back to basic parsing: {}',
                        kwargs['parse_mode'],
                        e.message,
                    )
                    del kwargs['parse_mode']
                    try:
                        self._bot.sendMessage(chat_id=chat_id, text=msg, **kwargs)
                    except TelegramError as e:
                        raise PluginWarning(e.message)
                else:
                    raise PluginWarning(e.message)

    def _get_chat_ids_n_update_db(self, session):
        """
        :type session: sqlalchemy.orm.Session
        :rtype: list[ChatIdEntry]

        """
        usernames = self._usernames[:]
        fullnames = self._fullnames[:]
        groups = self._groups[:]
        chat_ids, has_new_chat_ids = self._get_chat_ids(session, usernames, fullnames, groups)
        logger.debug('chat_ids={}', chat_ids)

        if not chat_ids:
            raise PluginError(
                'no chat id found, try manually sending the bot any message to initialize the chat'
            )
        else:
            if usernames:
                logger.warning('no chat id found for usernames: {}', usernames)
            if fullnames:
                logger.warning('no chat id found for fullnames: {}', fullnames)
            if groups:
                logger.warning('no chat id found for groups: {}', groups)
            if has_new_chat_ids:
                self._update_db(session, chat_ids)

        return chat_ids

    def _get_chat_ids(self, session, usernames, fullnames, groups):
        """get chat ids for `usernames`, `fullnames` & `groups`.
        entries with a matching chat ids will be removed from the input lists.

        :type session: sqlalchemy.orm.Session
        :type usernames: list[str]
        :type fullnames: list[tuple[str, str]]
        :type groups: list[str]
        :returns: chat ids, new chat ids found?
        :rtype: list[ChatIdEntry], bool

        """
        logger.debug('loading cached chat ids')
        chat_ids = self._get_cached_chat_ids(session, usernames, fullnames, groups)
        logger.debug(
            'found {0} cached chat_ids: {1}'.format(
                len(chat_ids), ['{0}'.format(x) for x in chat_ids]
            )
        )

        if not (usernames or fullnames or groups):
            logger.debug('all chat ids found in cache')
            return chat_ids, False

        logger.debug('loading new chat ids')
        new_chat_ids = list(self._get_new_chat_ids(usernames, fullnames, groups))
        logger.debug(
            'found {0} new chat_ids: {1}'.format(
                len(new_chat_ids), ['{0}'.format(x) for x in new_chat_ids]
            )
        )

        chat_ids.extend(new_chat_ids)
        return chat_ids, bool(new_chat_ids)

    @staticmethod
    def _get_cached_chat_ids(session, usernames, fullnames, groups):
        """get chat ids from the cache (DB). remove found entries from `usernames`, `fullnames` & `groups`

        :type session: sqlalchemy.orm.Session
        :type usernames: list[str]
        :type fullnames: list[tuple[str, str]]
        :type groups: list[str]
        :rtype: list[ChatIdEntry]

        """
        chat_ids = list()
        cached_usernames = dict(
            (x.username, x)
            for x in session.query(ChatIdEntry).filter(ChatIdEntry.username != None).all()
        )
        cached_fullnames = dict(
            ((x.firstname, x.surname), x)
            for x in session.query(ChatIdEntry).filter(ChatIdEntry.firstname != None).all()
        )
        cached_groups = dict(
            (x.group, x)
            for x in session.query(ChatIdEntry).filter(ChatIdEntry.group != None).all()
        )

        len_ = len(usernames)
        for i, username in enumerate(reversed(usernames)):
            item = cached_usernames.get(username)
            if item:
                chat_ids.append(item)
                usernames.pop(len_ - i - 1)

        len_ = len(fullnames)
        for i, fullname in enumerate(reversed(fullnames)):
            item = cached_fullnames.get(fullname)
            if item:
                chat_ids.append(item)
                fullnames.pop(len_ - i - 1)

        len_ = len(groups)
        for i, grp in enumerate(reversed(groups)):
            item = cached_groups.get(grp)
            if item:
                chat_ids.append(item)
                groups.pop(len_ - i - 1)

        return chat_ids

    def _get_new_chat_ids(self, usernames, fullnames, groups):
        """get chat ids by querying the telegram `bot`

        :type usernames: list[str]
        :type fullnames: list[tuple[str, str]]
        :type groups: list[str]
        :rtype: __generator[ChatIdEntry]

        """
        upd_usernames, upd_fullnames, upd_groups = self._get_bot_updates()

        len_ = len(usernames)
        for i, username in enumerate(reversed(usernames)):
            chat = upd_usernames.get(username)
            if chat is not None:
                entry = ChatIdEntry(
                    id=chat.id,
                    username=chat.username,
                    firstname=chat.first_name,
                    surname=chat.last_name,
                )
                yield entry
                usernames.pop(len_ - i - 1)

        len_ = len(fullnames)
        for i, fullname in enumerate(reversed(fullnames)):
            chat = upd_fullnames.get(fullname)
            if chat is not None:
                entry = ChatIdEntry(
                    id=chat.id,
                    username=chat.username,
                    firstname=chat.first_name,
                    surname=chat.last_name,
                )
                yield entry
                fullnames.pop(len_ - i - 1)

        len_ = len(groups)
        for i, grp in enumerate(reversed(groups)):
            chat = upd_groups.get(grp)
            if chat is not None:
                entry = ChatIdEntry(id=chat.id, group=chat.title)
                yield entry
                groups.pop(len_ - i - 1)

    def _get_bot_updates(self):
        """get updated chats info from telegram
        :type bot: telegram.Bot
        :rtype: (dict[str, telegram.User], dict[(str, str), telegram.User], dict[str, telegram.GroupChat])

        """
        # highly unlikely, but if there are more than 100 msgs waiting for the bot, we should not miss one
        updates = []
        last_upd = 0
        while 1:
            ups = self._bot.getUpdates(last_upd, limit=100)
            updates.extend(ups)
            if len(ups) < 100:
                break
            last_upd = ups[-1].update_id

        usernames = dict()
        fullnames = dict()
        groups = dict()
        for update in updates:
            if update.message:
                chat = update.message.chat
            elif update.edited_message:
                chat = update.edited_message.chat
            elif update.channel_post:
                chat = update.channel_post.chat
            else:
                raise PluginError('Unknown update type encountered: %s' % update)

            if chat.type == 'private':
                usernames[chat.username] = chat
                fullnames[(chat.first_name, chat.last_name)] = chat
            elif chat.type in ('group', 'supergroup' or 'channel'):
                groups[chat.title] = chat
            else:
                logger.warning('unknown chat type: {}}}', type(chat))

        return usernames, fullnames, groups

    def _update_db(self, session, chat_ids):
        """Update the DB with found `chat_ids`
        :type session: sqlalchemy.orm.Session
        :type chat_ids: list[ChatIdEntry]

        """
        logger.info('saving updated chat_ids to db')

        # avoid duplicate chat_ids. (this is possible if configuration specified both username & fullname
        chat_ids_d = dict((x.id, x) for x in chat_ids)

        session.add_all(iter(chat_ids_d.values()))
        session.commit()


@event('plugin.register')
def register_plugin():
    plugin.register(TelegramNotifier, _PLUGIN_NAME, api_ver=2, interfaces=['notifiers'])
