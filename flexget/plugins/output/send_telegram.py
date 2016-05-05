from __future__ import unicode_literals, division, absolute_import
from builtins import *  # pylint: disable=unused-import, redefined-builtin
from future.utils import native_str

import sys
from distutils.version import LooseVersion

from sqlalchemy import Column, Integer, String

from flexget import db_schema, plugin, options
from flexget.event import event
from flexget.logger import console
from flexget.utils.database import with_session
from flexget.utils.template import RenderError

try:
    import telegram
    from telegram.error import TelegramError
    from telegram.utils.request import URLError, SSLError
except ImportError:
    telegram = None

_MIN_TELEGRAM_VER = '3.4'

_PLUGIN_NAME = 'send_telegram'

_PARSERS = ['markdown', 'html']

_TOKEN_ATTR = 'bot_token'
_TMPL_ATTR = 'template'
_PARSE_ATTR = 'parse_mode'
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


class SendTelegram(object):
    """Send a message to one or more Telegram users or groups upon accepting a download.


    Preparations::

    * Install 'python-telegram-bot' python pkg (i.e. `pip install python-telegram-bot`)
    * Create a bot & obtain a token for it (see https://core.telegram.org/bots#botfather).
    * For direct messages (not to a group), start a conversation with the bot and click "START" in the Telegram app.
    * For group messages, add the bot to the desired group and send a start message to the bot: "/start" (mind the
      leading '/').


    Configuration example::

    my-task:
      send_telegram:
        bot_token: token
        template: {{title}}
        use_markdown: no
        recipients:
          - username: my-user-name
          - group: my-group-name
          - fullname:
              first: my-first-name
              sur: my-sur-name


    Bootstrapping and testing the bot::

    * Execute: `flexget send_telegram bootstrap`.
      Look at the console output and make sure that the operation was successful.
    * Execute: `flexget send_telegram test-msg`.
      This will send a test message for every recipient you've configured.


    Configuration notes::

    You may use any combination of recipients types (`username`, `group` or `fullname`) - 0 or more of each (but you
    need at least one total...).

    `template`::
    Optional. The template from the example is the default.

    `parse_mode`::
    Optional. Whether the template uses `markdown` or `html` formatting.

    NOTE: The markdown parser will fall back to basic parsing if there is a parsing error. This can be cause due to
    unclosed tags (watch out for wandering underscore when using markdown)

    `username` vs. `fullname`::

    Not all Telegram users have a username. In such cases you would have to use the `fullname` approach. Otherwise, it
    is much easier to use the `username` configuration.

    """
    log = None  # initialized during plugin.register
    """:type: flexget.logger.FlexGetLogger"""
    _token = None
    _tmpl = None
    _use_markdown = False
    _usernames = None
    _fullnames = None
    _groups = None
    _bot = None

    schema = {
        'type': 'object',
        'properties': {
            _TOKEN_ATTR: {'type': 'string'},
            _TMPL_ATTR: {'type': 'string', 'default': '{{title}}'},
            _PARSE_ATTR: {'type': 'string', 'enum': _PARSERS},
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

    def _parse_config(self, config):
        """
        :type config: dict

        """
        self._token = config[_TOKEN_ATTR]
        self._tmpl = config[_TMPL_ATTR]
        self._parse_mode = config.get(_PARSE_ATTR)
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

    def on_task_output(self, task, config):
        """makes this plugin count as output (stops warnings about missing outputs)"""
        pass

    def on_task_exit(self, task, config):
        """Send telegram message(s) at exit"""
        session = task.session
        chat_ids = self._real_init(session, config)

        if not chat_ids:
            return

        self._send_msgs(task, chat_ids)

    def _real_init(self, session, config, ):
        self._enforce_telegram_plugin_ver()
        self._parse_config(config)
        self.log.debug('token={0} parse_mode={5}, tmpl={4!r} usernames={1} fullnames={2} groups={3}'.format(
                self._token, self._usernames, self._fullnames, self._groups, self._tmpl, self._parse_mode))
        self._init_bot()
        chat_ids = self._get_chat_ids_n_update_db(session)
        return chat_ids

    def bootstrap(self, session, config):
        """bootstrap the plugin configuration and update db with cached chat_ids"""
        console('{0} - bootstrapping...'.format(_PLUGIN_NAME))
        chat_ids = self._real_init(session, config)

        found_usernames = [x.username for x in chat_ids if x.username]
        found_fullnames = [(x.firstname, x.surname) for x in chat_ids if x.firstname]
        found_grps = [x.group for x in chat_ids if x.group]

        missing_usernames = [x for x in self._usernames if x not in found_usernames]
        missing_fullnames = [x for x in self._fullnames if x not in found_fullnames]
        missing_grps = [x for x in self._groups if x not in found_grps]

        if missing_usernames or missing_fullnames or missing_grps:
            for i in missing_usernames:
                console('ERR: could not find chat_id for username: {0}'.format(i))
            for i in missing_fullnames:
                console('ERR: could not find chat_id for fullname: {0} {1}'.format(*i))
            for i in missing_grps:
                console('ERR: could not find chat_id for group: {0}'.format(i))
            res = False
        else:
            console('{0} - bootstrap was successful'.format(_PLUGIN_NAME))
            res = True

        return res

    def test_msg(self, session, config):
        """send test message to configured recipients"""
        console('{0} loading chat_ids...'.format(_PLUGIN_NAME))
        chat_ids = self._real_init(session, config)

        console('{0} sending test message(s)...'.format(_PLUGIN_NAME))
        for chat_id in (x.id for x in chat_ids):
            self._bot.sendMessage(chat_id=chat_id, text='test message from flexget')

        return True

    def _init_bot(self):
        self._bot = telegram.Bot(self._token)
        self._check_token()

    def _check_token(self):
        try:
            self._bot.getMe()
        except UnicodeDecodeError as e:
            self.log.trace('bot.getMe() raised: {!r}'.format(e))
            raise plugin.PluginWarning('invalid bot token')
        except (URLError, SSLError) as e:
            self.log.error('Could not connect Telegram servers at this time, please try again later: %s', e.args[0])
        except TelegramError as e:
            self.log.error('Could not connect Telegram servers at this time, please try again later: %s', e.message)

    @staticmethod
    def _enforce_telegram_plugin_ver():
        if telegram is None:
            raise plugin.PluginWarning('missing python-telegram-bot pkg')
        elif not hasattr(telegram, str('__version__')):
            raise plugin.PluginWarning('invalid or old python-telegram-bot pkg')
        elif LooseVersion(telegram.__version__) < native_str(_MIN_TELEGRAM_VER):
            raise plugin.PluginWarning('old python-telegram-bot ({0})'.format(telegram.__version__))

    def _send_msgs(self, task, chat_ids):
        kwargs = dict()
        if self._parse_mode == 'markdown':
            kwargs['parse_mode'] = telegram.ParseMode.MARKDOWN
        elif self._parse_mode == 'html':
            kwargs['parse_mode'] = telegram.ParseMode.HTML
        for entry in task.accepted:
            msg = self._render_msg(entry, self._tmpl)
            for chat_id in (x.id for x in chat_ids):
                try:
                    self._bot.sendMessage(chat_id=chat_id, text=msg, **kwargs)
                except TelegramError as e:
                    if kwargs.get('parse_mode') and "can't parse message text" in e.message:
                        self.log.warning(
                                'Failed to render message using parse mode %s. Falling back to basic parsing: %s' % (
                                    kwargs['parse_mode'], e.message))
                        del kwargs['parse_mode']
                        try:
                            self._bot.sendMessage(chat_id=chat_id, text=msg, **kwargs)
                        except TelegramError as e:
                            self.log.error('Cannot send message, : %s' % e.message)
                            continue
                    else:
                        self.log.error('Cannot send message, : %s' % e.message)
                        continue

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

    def _get_chat_ids_n_update_db(self, session):
        """
        :type session: sqlalchemy.orm.Session
        :rtype: list[ChatIdEntry]

        """
        usernames = self._usernames[:]
        fullnames = self._fullnames[:]
        groups = self._groups[:]
        chat_ids, has_new_chat_ids = self._get_chat_ids(session, usernames, fullnames, groups)
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
        chat_ids = list()

        self.log.debug('loading cached chat ids')
        chat_ids = self._get_cached_chat_ids(session, usernames, fullnames, groups)
        self.log.debug('found {0} cached chat_ids: {1}'.format(len(chat_ids), ['{0}'.format(x) for x in chat_ids]))

        if not (usernames or fullnames or groups):
            self.log.debug('all chat ids found in cache')
            return chat_ids, False

        self.log.debug('loading new chat ids')
        new_chat_ids = list(self._get_new_chat_ids(usernames, fullnames, groups))
        self.log.debug('found {0} new chat_ids: {1}'.format(len(new_chat_ids), ['{0}'.format(x) for x in new_chat_ids]))

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

        for chat in (x.message.chat for x in updates):
            if chat.type == 'private':
                usernames[chat.username] = chat
                fullnames[(chat.first_name, chat.last_name)] = chat
            elif chat.type in ('group', 'supergroup' or 'channel'):
                groups[chat.title] = chat
            else:
                self.log.warning('unknown chat type: {0}'.format(type(chat)))

        return usernames, fullnames, groups

    def _update_db(self, session, chat_ids):
        """Update the DB with found `chat_ids`
        :type session: sqlalchemy.orm.Session
        :type chat_ids: list[ChatIdEntry]

        """
        self.log.info('saving updated chat_ids to db')

        # avoid duplicate chat_ids. (this is possible if configuration specified both username & fullname
        chat_ids_d = dict((x.id, x) for x in chat_ids)

        session.add_all(iter(chat_ids_d.values()))
        session.commit()


def _guess_task_name(manager):
    for task in manager.tasks:
        if _get_config(manager, task) is not None:
            break
    else:
        task = None
    return task


def _get_config(manager, task):
    return manager.config['tasks'][task].get(_PLUGIN_NAME)


@with_session()
def do_cli(manager, args, session=None):
    """
    :type manager: flexget.Manager

    """
    task_name = _guess_task_name(manager)
    config = _get_config(manager, task_name)
    plugin_info = plugin.get_plugin_by_name(_PLUGIN_NAME)
    send_telegram = plugin_info.instance
    """:type: SendTelegram"""

    if args.action == 'bootstrap':
        res = send_telegram.bootstrap(session, config)
    elif args.action == 'test-msg':
        res = send_telegram.test_msg(session, config)
    else:
        raise RuntimeError('unknown action')

    sys.exit(int(not res))


@event('plugin.register')
def register_plugin():
    plugin.register(SendTelegram, _PLUGIN_NAME, api_ver=2)


@event('options.register')
def register_parser_arguments():
    parser = options.register_command(_PLUGIN_NAME, do_cli, help='{0} cli'.format(_PLUGIN_NAME))
    """:type: options.CoreArgumentParser"""
    subp = parser.add_subparsers(dest='action')
    bsp = subp.add_parser('bootstrap', help='bootstrap the plugin according to config')
    bsp.add_argument('--tasks', )
    subp.add_parser('test-msg', help='send test message to all configured recipients')
