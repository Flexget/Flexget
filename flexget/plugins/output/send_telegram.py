from __future__ import unicode_literals, division, absolute_import

from sqlalchemy import Column, Integer, String

from flexget import db_schema, plugin
from flexget.event import event
from flexget.utils.template import RenderError

try:
    import telegram
except ImportError:
    telegram = None

_PLUGIN_NAME = 'send_telegram'

_TOKEN_ATTR = 'bot_token'
_TMPL_ATTR = 'template'
_RCPTS_ATTR = 'recipients'
_USERNAME_ATTR = 'username'
_FULLNAME_ATTR = 'fullname'
_FIRSTNAME_ATTR = 'first'
_SURNAME_ATTR = 'sur'
_GROUP_ATTR = 'group'

ChatIdsBase = db_schema.versioned_base('telegram_chat_ids', 0)


class ChatIdEntry(ChatIdsBase):
    __tablename__ = 'telegram_chat_ids'

    id = Column(Integer, primary_key=True)
    username = Column(String, index=True, nullable=True)
    firstname = Column(String, index=True, nullable=True)
    surname = Column(String, index=True, nullable=True)
    group = Column(String, index=True, nullable=True)


class SendTelegram(object):
    """Send a message to one or more Telegram users or groups upon accepting a download.


    Preparations::

    * Install 'python-telegram-bot' python pkg
    * Create a bot & obtain a token for it (see https://core.telegram.org/bots#botfather).
    * For direct messages (not to a group), start a conversation with the bot and click "START" in the Telegram app.
    * For group messages, add the bot to the desired group and send a start message to the bot: "/start" (mind the
      leading '/').


    Configuration example::

    my-task:
      send_telegram:
        bot_token: token
        template: {{title}}
        recipients:
          - username: my-user-name
          - group: my-group-name
          - fullname:
              first: my-first-name
              sur: my-sur-name

    You may use any combination of recipients types (`username`, `group` or `fullname`) - 0 or more of each (but you
    need at least one total...).

    `template`::
    Optional. The template from the example is the default.

    `username` vs. `fullname`::

    Not all Telegram users have a username. In such cases you would have to use the `fullname` approach. Otherwise, it
    is much easier to use the `username` configuration.

    """
    log = None  # initialized during plugin.register
    """:type: flexget.logger.FlexGetLogger"""

    schema = {
        'type': 'object',
        'properties': {
            _TOKEN_ATTR: {'type': 'string'},
            _TMPL_ATTR: {'type': 'string', 'default': '{{title}}'},
            _RCPTS_ATTR: {
                'type': 'array',
                'minItems': 1,
                'items': {
                    'oneOf': [
                        {
                            'type': 'object',
                            'properties': {
                                _USERNAME_ATTR: {'type': 'string'},
                            },
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
                                },
                            },
                            'required': [_FULLNAME_ATTR],
                            'additionalProperties': False,
                        },
                        {
                            'type': 'object',
                            'properties': {
                                _GROUP_ATTR: {'type': 'string'},
                            },
                            'required': [_GROUP_ATTR],
                            'additionalProperties': False,
                        },
                    ],
                },
            },
        },
        'required': [_TOKEN_ATTR, _RCPTS_ATTR],
        'additionalProperties': False,
    }

    @staticmethod
    def _parse_config(config):
        """
        :type config: dict
        :returns: token, tmpl, usernames, fullnames, groups
        :rtype: str, str, tuple[list[str], list[tuple[str, str]], list[str]]

        """
        token = config[_TOKEN_ATTR]
        tmpl = config[_TMPL_ATTR]
        usernames = []
        fullnames = []
        groups = []

        for i in config[_RCPTS_ATTR]:
            if _USERNAME_ATTR in i:
                usernames.append(i[_USERNAME_ATTR])
            elif _FULLNAME_ATTR in i:
                fullname = i[_FULLNAME_ATTR]
                firstname = fullname[_FIRSTNAME_ATTR]
                surname = fullname[_SURNAME_ATTR]
                fullnames.append((firstname, surname))
            elif _GROUP_ATTR in i:
                groups.append(i[_GROUP_ATTR])

        return token, tmpl, usernames, fullnames, groups

    def on_task_output(self, task, config):
        """makes this plugin count as output (stops warnings about missing outputs)"""
        pass

    def on_task_exit(self, task, config):
        """Send telegram message(s) at exit"""
        if telegram is None:
            raise plugin.PluginWarning('missing telegram python pkg')

        accepted_tasks = list(task.accepted)
        """:type: list[flexget.entry.Entry]"""
        token, tmpl, usernames, fullnames, groups = self._parse_config(config)
        self.log.debug('token={0} tmpl={4!r} usernames={1} fullnames={2} groups={3}'.format(
            token, usernames, fullnames, groups, tmpl))

        bot = telegram.Bot(token)
        try:
            bot.getMe()
        except UnicodeDecodeError as e:
            self.log.trace('bot.getMe() raised: {!r}'.format(e))
            raise plugin.PluginWarning('invalid bot token')
        session = task.session

        chat_ids = self._get_chat_ids_n_update_db(bot, session, usernames, fullnames, groups)

        if not chat_ids:
            return

        for entry in accepted_tasks:
            msg = self._render_msg(entry, tmpl)
            for chat_id in (x.id for x in chat_ids):
                bot.sendMessage(chat_id=chat_id, text=msg)

    def _render_msg(self, entry, tmpl):
        """
        :type entry: flexget.entry.Entry
        :type tmpl: str
        :rtype: str

        """
        try:
            msg = entry.render(tmpl)
        except RenderError as e:
            title = entry.get('title')
            self.log.error('render error; title={0} err={1}'.format(title, e))
            msg = title
        return msg

    def _get_chat_ids_n_update_db(self, bot, session, usernames, fullnames, groups):
        """
        :type bot: telgram.Bot
        :type session: sqlalchemy.orm.Session
        :type usernames: list[str]
        :type fullnames: list[tuple[str, str]]
        :type groups: list[str]
        :rtype: list[ChatIdEntry]

        """
        chat_ids, has_new_chat_ids = self._get_chat_ids(session, bot, usernames, fullnames, groups)
        self.log.debug('chat_ids={0}'.format(chat_ids))

        if not chat_ids:
            self.log.warning('no chat id found')
        else:
            if usernames:
                self.log.warning('no chat id found for usernames: {0}'.format(usernames))
            if fullnames:
                self.log.warning('no chat id found for fullnames: {0}'.format(fullnames))
            if groups:
                self.log.warning('no chat id found for groups: {0}'.format(groups))
            if has_new_chat_ids:
                self._update_db(session, chat_ids)

        return chat_ids

    def _get_chat_ids(self, session, bot, usernames, fullnames, groups):
        """get chat ids for `usernames`, `fullnames` & `groups`.
        entries with a matching chat ids will be removed from the input lists.

        :type session: sqlalchemy.orm.Session
        :type bot: telegram.Bot
        :type usernames: list[str]
        :type fullnames: list[tuple[str, str]]
        :type groups: list[str]
        :returns: chat ids, new chat ids found?
        :rtype: list[ChatIdEntry], bool

        """
        chat_ids = list()

        self.log.debug('loading cached chat ids')
        chat_ids = self._get_cached_chat_ids(session, usernames, fullnames, groups)

        if not (usernames or fullnames or groups):
            self.log.debug('all chat ids found in cache')
            return chat_ids, False

        self.log.debug('loading new chat ids')
        new_chat_ids = list(self._get_new_chat_ids(bot, usernames, fullnames, groups))
        self.log.debug('found {0} new chat ids'.format(len(new_chat_ids)))

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
        cached_usernames = dict((x.username, x)
                                for x in session.query(ChatIdEntry).filter(ChatIdEntry.username != None).all())
        cached_fullnames = dict(((x.firstname, x.surname), x)
                                for x in session.query(ChatIdEntry).filter(ChatIdEntry.firstname != None).all())
        cached_groups = dict((x.group, x)
                             for x in session.query(ChatIdEntry).filter(ChatIdEntry.group != None).all())

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

    def _get_new_chat_ids(self, bot, usernames, fullnames, groups):
        """get chat ids by querying the telegram `bot`

        :type bot: telegram.Bot
        :type usernames: list[str]
        :type fullnames: list[tuple[str, str]]
        :type groups: list[str]
        :rtype: __generator[ChatIdEntry]

        """
        upd_usernames, upd_fullnames, upd_groups = self._get_bot_updates(bot)

        len_ = len(usernames)
        for i, username in enumerate(reversed(usernames)):
            chat = upd_usernames.get(username)
            if chat is not None:
                entry = ChatIdEntry(id=chat.id, username=chat.username, firstname=chat.first_name,
                                    surname=chat.last_name)
                yield entry
                usernames.pop(len_ - i - 1)

        len_ = len(fullnames)
        for i, fullname in enumerate(reversed(fullnames)):
            chat = upd_fullnames.get(fullname)
            if chat is not None:
                entry = ChatIdEntry(id=chat.id, username=chat.username, firstname=chat.first_name,
                                    surname=chat.last_name)
                yield entry
                fullnames.pop(len_ - i - 1)

        len_ = len(groups)
        for i, grp in enumerate(reversed(groups)):
            chat = upd_groups.get(grp)
            if chat is not None:
                entry = ChatIdEntry(id=chat.id, group=chat.title)
                yield entry
                groups.pop(len_ - i - 1)

    def _get_bot_updates(self, bot):
        """get updated chats info from telegram
        :type bot: telegram.Bot
        :rtype: (dict[str, telegram.User], dict[(str, str), telegram.User], dict[str, telegram.GroupChat])

        """
        updates = bot.getUpdates()
        usernames = dict()
        fullnames = dict()
        groups = dict()

        for chat in (x.message.chat for x in updates):
            if isinstance(chat, telegram.User):
                usernames[chat.username] = chat
                fullnames[(chat.first_name, chat.last_name)] = chat
            elif isinstance(chat, telegram.GroupChat):
                groups[chat.title] = chat
            else:
                self.log.warn('unknown chat type: {0}'.format(type(chat)))

        return usernames, fullnames, groups

    def _update_db(self, session, chat_ids):
        """Update the DB with found `chat_ids`
        :type session: sqlalchemy.orm.Session
        :type chat_ids: list[ChatIdEntry]

        """
        self.log.info('saving updated chat_ids to db')
        session.add_all(chat_ids)


@event('plugin.register')
def register_plugin():
    plugin.register(SendTelegram, _PLUGIN_NAME, api_ver=2)
