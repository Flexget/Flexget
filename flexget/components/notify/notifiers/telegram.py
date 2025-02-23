from __future__ import annotations

import asyncio
from collections import defaultdict
from importlib.metadata import PackageNotFoundError, version
from pathlib import Path
from textwrap import wrap
from typing import TYPE_CHECKING

import sqlalchemy
from loguru import logger
from packaging.version import Version
from sqlalchemy import Column, Integer, String

from flexget import db_schema, plugin
from flexget.event import event
from flexget.manager import Session
from flexget.plugin import PluginError

if TYPE_CHECKING:
    from collections.abc import AsyncGenerator

try:
    if Version(version("python-telegram-bot")) < Version('21.9'):
        raise plugin.PluginWarning('obsolete python-telegram-bot pkg')
except PackageNotFoundError:
    pass
else:
    import telegram
    from telegram.error import ChatMigrated, NetworkError, TelegramError
    from telegram.ext import ApplicationBuilder

try:
    from PIL import Image
except ImportError:
    Image = None

_PLUGIN_NAME = 'telegram'
_TEXT_LIMIT = 4096
_PARSERS = {'html': 'HTML', 'markdown': 'MarkdownV2', 'markdown_legacy': 'Markdown'}

_DISABLE_PREVIEWS_ATTR = 'disable_previews'
_TOKEN_ATTR = 'bot_token'
_PARSE_ATTR = 'parse_mode'
_RCPTS_ATTR = 'recipients'
_CHATID_ATTR = 'chat_id'
_USERNAME_ATTR = 'username'
_FULLNAME_ATTR = 'fullname'
_FIRSTNAME_ATTR = 'first'
_SURNAME_ATTR = 'sur'
_GROUP_ATTR = 'group'
_SOCKSPROXY_ATTR = 'socks_proxy'
_IMAGES_ATTR = 'images'

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
        x = [f'id={self.id}']
        if self.username:
            x.append(f'username={self.username}')
        if self.firstname:
            x.append(f'firstname={self.firstname}')
        if self.surname:
            x.append(f'surname={self.surname}')
        if self.group:
            x.append(f'group={self.group}')
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
              images:
                - image1.png
                - image2.jpg
              recipients:
                - chat_id: ask @raw_data_bot (most recommended)
                - username: my-user-name
                - group: my-group-name
                - fullname:
                    first: my-first-name
                    sur: my-sur-name
              socks_proxy: socks5://user:pass@host:port


    Configuration notes::

    You may use any combination of recipients types (`username`, `group` or `fullname`) - 0 or more of each (but you
    need at least one total...).

    `parse_mode`::
    Optional. Whether the template uses `markdown` or `html` formatting.

    NOTE: The markdown parser will fall back to basic parsing if there is a parsing error. This can be cause due to
    unclosed tags (watch out for wandering underscore when using markdown)

    `chat_id` vs. `username` vs. `fullname`::

    The `chat_id` approach is the most recommended, because with this approach, you don't have to send a message to get
    the chat ID before the program runs. In addition, it is the most stable. Even if you change your name, the program
    will still work properly. `chat_id` can be a user's or a group's (including private groups). If the chat is a group,
    the chat id is negative. If it is a single person, then positive.

    """

    _token = None
    _chat_ids_from_config = None
    _usernames = None
    _fullnames = None
    _groups = None
    _images = None
    _bot = None

    schema = {
        'type': 'object',
        'properties': {
            _TOKEN_ATTR: {'type': 'string'},
            _PARSE_ATTR: {'type': 'string', 'enum': list(_PARSERS.keys())},
            _DISABLE_PREVIEWS_ATTR: {'type': 'boolean', 'default': False},
            _RCPTS_ATTR: {
                'type': 'array',
                'minItems': 1,
                'items': {
                    'oneOf': [
                        {
                            'type': 'object',
                            'properties': {_CHATID_ATTR: {'type': 'integer'}},
                            'required': [_CHATID_ATTR],
                            'additionalProperties': False,
                        },
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
            _SOCKSPROXY_ATTR: {'type': 'string'},
            _IMAGES_ATTR: {'type': 'array', 'items': {'type': 'string'}},
        },
        'required': [_TOKEN_ATTR, _RCPTS_ATTR],
        'additionalProperties': False,
    }

    def notify(self, title: str, message: str, config: dict) -> None:
        self._load_config(config)
        asyncio.run(self.main(message))

    async def main(self, message: str) -> None:
        """Send a Telegram notification."""
        async with (
            ApplicationBuilder()
            .token(self._token)
            .proxy(self.socks_proxy)
            .get_updates_proxy(self.socks_proxy)
            .build()
            .bot as bot
        ):
            self._bot = bot
            await self._check_token()
            session = Session()
            chat_ids = await self._get_chat_ids_and_update_db(session)
            if not chat_ids:
                return
            await self._send_msgs(message, chat_ids, session)
            if self._images and message:
                await self._send_images(chat_ids, session)

    def _load_config(self, config: dict) -> None:
        self._token = config[_TOKEN_ATTR]
        self._parse_mode = config.get(_PARSE_ATTR)
        self._disable_previews = config[_DISABLE_PREVIEWS_ATTR]
        result = defaultdict(list)
        for i in config[_RCPTS_ATTR]:
            for k, v in i.items():
                result[k].append(v)
        self._chat_ids_from_config = set(result[_CHATID_ATTR])
        self._usernames = result[_USERNAME_ATTR]
        self._fullnames = [(d[_FIRSTNAME_ATTR], d[_SURNAME_ATTR]) for d in result[_FULLNAME_ATTR]]
        self._groups = result[_GROUP_ATTR]
        self.socks_proxy = config.get(_SOCKSPROXY_ATTR)
        self._images = config.get(_IMAGES_ATTR)
        logger.debug(
            'token={}, parse_mode={}, disable_previews={}, usernames={}, fullnames={}, groups={}, images={}',
            self._token,
            self._parse_mode,
            self._disable_previews,
            self._usernames,
            self._fullnames,
            self._groups,
            self._images,
        )

    async def _check_token(self) -> None:
        try:
            await self._bot.get_me()
        except UnicodeDecodeError as e:
            logger.trace(f'bot.get_me() raised: {e!r}')
            raise plugin.PluginWarning('invalid bot token')
        except (NetworkError, TelegramError) as e:
            logger.error(
                'Could not connect Telegram servers at this time, please try again later: {}',
                e.message,
            )

    async def _replace_chat_id(
        self, old_id: int, new_id: int, session: sqlalchemy.orm.Session
    ) -> None:
        upd_usernames, upd_fullnames, upd_groups = await self._get_bot_updates()
        for group in upd_groups:
            grp = upd_groups.get(group)
            if grp.id == new_id:
                old_data = session.query(ChatIdEntry).filter(ChatIdEntry.id == old_id).first()
                session.delete(old_data)
                entry = ChatIdEntry(id=grp.id, group=grp.title)
                self._update_db(session, [entry])
                break

    async def _send_msgs(
        self, msg: str, chat_ids: set[int], session: sqlalchemy.orm.Session
    ) -> None:
        kwargs = {}
        if self._parse_mode:
            kwargs['parse_mode'] = _PARSERS[self._parse_mode]
        kwargs['disable_web_page_preview'] = self._disable_previews
        for chat_id in chat_ids:
            for paragraph in wrap(msg, _TEXT_LIMIT, replace_whitespace=False):
                try:
                    logger.debug('sending paragraph to telegram servers: {}', paragraph)
                    await self._bot.send_message(chat_id=chat_id, text=paragraph, **kwargs)
                except ChatMigrated as e:
                    logger.debug("Chat migrated to id {}", e.new_chat_id)
                    await self._bot.send_message(chat_id=e.new_chat_id, text=paragraph, **kwargs)
                    await self._replace_chat_id(chat_id, e.new_chat_id, session)
                except TelegramError as e:
                    if kwargs.get('parse_mode'):
                        logger.warning(
                            'Failed to render message using parse mode {}. Falling back to basic parsing: {}',
                            kwargs['parse_mode'],
                            e.message,
                        )
                        del kwargs['parse_mode']
                        await self._bot.send_message(chat_id=chat_id, text=paragraph, **kwargs)
                    else:
                        raise

    async def _send_images(self, chat_ids: set[int], session: sqlalchemy.orm.Session) -> None:
        for chat_id in chat_ids:
            for image in self._images:
                with Image.open(image) as photo:
                    width = photo.width
                    height = photo.height
                can_send_photo = width + height <= 10000 and width / height <= 20
                try:
                    await (
                        self._bot.send_photo(chat_id=chat_id, photo=Path(image))
                        if can_send_photo
                        else self._bot.send_document(chat_id=chat_id, document=Path(image))
                    )
                except ChatMigrated as e:
                    await (
                        self._bot.send_photo(chat_id=e.new_chat_id, photo=Path(image))
                        if can_send_photo
                        else self._bot.send_document(chat_id=e.new_chat_id, document=Path(image))
                    )
                    await self._replace_chat_id(chat_id, e.new_chat_id, session)

    async def _get_chat_ids_and_update_db(self, session: sqlalchemy.orm.Session) -> set[int]:
        usernames = list(self._usernames)
        fullnames = list(self._fullnames)
        groups = list(self._groups)
        chat_id_entries, has_new_chat_ids = await self._get_chat_id_entries(
            session, usernames, fullnames, groups
        )
        logger.debug('chat_id_entries={}', chat_id_entries)

        # TODO: The situation where the new chat_id from `ChatMigrated` exception needs to be written to the
        #  database if the chat_id specified directly in the configuration file is migrated is not considered.
        #  This will cause one more HTTP request to be sent each time the program runs. However, this situation
        #  only occurs when the chat_id directly specified in the configuration file is a group and it is migrated.
        chat_ids = {x.id for x in chat_id_entries} | self._chat_ids_from_config
        if not chat_ids:
            raise PluginError(
                'no chat id found, try manually sending the bot any message to initialize the chat'
            )
        if chat_id_entries:
            if usernames:
                logger.warning('no chat id found for usernames: {}', usernames)
            if fullnames:
                logger.warning('no chat id found for fullnames: {}', fullnames)
            if groups:
                logger.warning('no chat id found for groups: {}', groups)
            if has_new_chat_ids:
                self._update_db(session, chat_id_entries)
        return chat_ids

    async def _get_chat_id_entries(
        self,
        session: sqlalchemy.orm.Session,
        usernames: list[str],
        fullnames: list[tuple[str, str]],
        groups: list[str],
    ) -> tuple[list[ChatIdEntry], bool]:
        """Get chat ids for `usernames`, `fullnames` & `groups`.

        Entries with a matching chat ids will be removed from the input lists.
        """
        logger.debug('loading cached chat ids')
        chat_id_entries = self._get_cached_chat_id_entries(session, usernames, fullnames, groups)
        logger.debug(
            'found {} cached chat_ids: {}', len(chat_id_entries), [f'{x}' for x in chat_id_entries]
        )
        if not (usernames or fullnames or groups):
            logger.debug('all chat ids found in cache')
            return chat_id_entries, False
        logger.debug('loading new chat ids')
        new_chat_ids = [
            e async for e in self._get_new_chat_id_entries(usernames, fullnames, groups)
        ]
        logger.debug(
            'found {} new chat_ids: {}', len(new_chat_ids), [f'{x}' for x in new_chat_ids]
        )
        chat_id_entries += new_chat_ids
        return chat_id_entries, bool(new_chat_ids)

    @staticmethod
    def _get_cached_chat_id_entries(
        session: sqlalchemy.orm.Session,
        usernames: list[str],
        fullnames: list[tuple[str, str]],
        groups: list[str],
    ) -> list[ChatIdEntry]:
        """Get chat ids from the cache (DB). remove found entries from `usernames`, `fullnames` & `groups`."""
        chat_id_entries = []
        cached_usernames = {
            x.username: x
            for x in session.query(ChatIdEntry).filter(ChatIdEntry.username.is_not(None)).all()
        }
        cached_fullnames = {
            (x.firstname, x.surname): x
            for x in session.query(ChatIdEntry).filter(ChatIdEntry.firstname.is_not(None)).all()
        }
        cached_groups = {
            x.group: x
            for x in session.query(ChatIdEntry).filter(ChatIdEntry.group.is_not(None)).all()
        }

        len_ = len(usernames)
        for i, username in enumerate(reversed(usernames)):
            item = cached_usernames.get(username)
            if item:
                chat_id_entries.append(item)
                usernames.pop(len_ - i - 1)

        len_ = len(fullnames)
        for i, fullname in enumerate(reversed(fullnames)):
            item = cached_fullnames.get(fullname)
            if item:
                chat_id_entries.append(item)
                fullnames.pop(len_ - i - 1)

        len_ = len(groups)
        for i, grp in enumerate(reversed(groups)):
            item = cached_groups.get(grp)
            if item:
                chat_id_entries.append(item)
                groups.pop(len_ - i - 1)

        return chat_id_entries

    async def _get_new_chat_id_entries(
        self, usernames: list[str], fullnames: list[tuple[str, str]], groups: list[str]
    ) -> AsyncGenerator[ChatIdEntry, None]:
        """Get chat ids by querying the telegram `bot`."""
        upd_usernames, upd_fullnames, upd_groups = await self._get_bot_updates()

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

    async def _get_bot_updates(
        self,
    ) -> tuple[
        dict[str, telegram.Chat], dict[tuple[str, str], telegram.Chat], dict[str, telegram.Chat]
    ]:
        """Get updated chats info from telegram."""
        # highly unlikely, but if there are more than `telegram.constants.PollingLimit.MAX_LIMIT`
        # msgs waiting for the bot, we should not miss one
        total_updates = []
        last_update = 0
        while True:
            updates = await self._bot.get_updates(
                last_update, limit=telegram.constants.PollingLimit.MAX_LIMIT
            )
            total_updates.extend(updates)
            if len(updates) < telegram.constants.PollingLimit.MAX_LIMIT:
                break
            last_update = updates[-1].update_id

        usernames = {}
        fullnames = {}
        groups = {}
        for update in total_updates:
            if update.message:
                chat = update.message.chat
            elif update.edited_message:
                chat = update.edited_message.chat
            elif update.channel_post:
                chat = update.channel_post.chat
            else:
                logger.warning('Unknown update type encountered: {}', update)
                continue
            if chat.type == 'private':
                usernames[chat.username] = chat
                fullnames[(chat.first_name, chat.last_name)] = chat
            elif chat.type in ('group', 'supergroup', 'channel'):
                groups[chat.title] = chat
            else:
                logger.warning('unknown chat type: {}}}', type(chat))

        return usernames, fullnames, groups

    def _update_db(
        self, session: sqlalchemy.orm.Session, chat_id_entries: list[ChatIdEntry]
    ) -> None:
        """Update the DB with found `chat_ids`."""
        logger.info('saving updated chat_ids to db')

        # avoid duplicate chat_ids. (this is possible if configuration specified both username & fullname
        chat_id_mappings = {x.id: x for x in chat_id_entries}

        session.add_all(iter(chat_id_mappings.values()))
        session.commit()


@event('plugin.register')
def register_plugin():
    plugin.register(TelegramNotifier, _PLUGIN_NAME, api_ver=2, interfaces=['notifiers'])
