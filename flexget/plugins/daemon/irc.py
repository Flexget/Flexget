from __future__ import unicode_literals, division, absolute_import
import re
import threading
import logging

from irc.bot import SingleServerIRCBot

from flexget.entry import Entry
from flexget.config_schema import register_config_key, format_checker
from flexget.event import event


log = logging.getLogger('irc')

schema = {
    'oneOf': [
        {
            'type': 'object',
            'items': {
                'properties': {
                    'server': {'type': 'string'},
                    'port': {'type': 'integer', 'default': 6667},
                    'nick': {'type': 'string', 'default': 'Flexget'},
                    'channels': {
                        'oneOf': [
                            {'type': 'list',
                             'items': {'type': 'string', 'format': 'irc_channel'},
                             },
                            {'type': 'string', 'format': 'irc_channel'},
                        ]
                    },
                    'nickserv_password': {'type': 'string'},
                    'task': {'type': 'string'},
                    'queue_entries': {'type': 'integer', 'default': 1},
                    'multi_lines': {'type': 'integer', 'default': 1},
                    'title_regexp': {'type': 'string'},
                },
                'required': ['task', 'server'],
                'additionalProperties': False,
            }
        },
        {'type': 'boolean', 'enum': [False]},
    ],
}

# Global that holds all the IRCConnection instances
irc = []


@format_checker.checks('irc_channel', raises=ValueError)
def is_irc_channel(instance):
    if not isinstance(instance, basestring) or instance[0] not in '#&!+.~' or not instance.isalnum():
        raise ValueError('%s isn\'t a valid IRC channel name.' % instance)


class IRCConnection(SingleServerIRCBot):
    def __init__(self, config, config_name):
        self.config = config

        # Init the IRC Bot
        server = config.get('server')
        port = config.get('port', 6667)
        nickname = config.get('nickname', 'Flexget')
        SingleServerIRCBot.__init__(self, [(server, port)], nickname, nickname)
        self.stop_bot = False

        # Init some settings from the config/tracker config
        self.connection_name = config_name

        self.entry_queue = []
        self.line_cache = []

    def start_interruptable(self, timeout=0.2):
        """Start the IRC connection in a interruptable state"""
        self._connect()
        while not self.stop_bot:
            self.reactor.process_once(timeout)
        self.disconnect()

    def run_tasks(self, entries):
        """
        Passes entries to the target task
        """
        from flexget.manager import manager

        log.info('Injecting %d entries into task %s' % (len(entries), self.config.get('task')))
        manager.execute(options={'tasks': [self.config.get('task')], 'cron': True, 'inject': entries}, priority=5)

    def queue_entry(self, entry):
        """
        Stores an entry in the connection entry queue, if the queue is over the size limit then submit them to the task
        """
        self.entry_queue.append(entry)
        log.debug('Entry: %s', entry)
        if len(self.entry_queue) >= self.config.get('queue_entries', 1):
            self.run_tasks(self.entry_queue)
            self.entry_queue = []

    def parse_message(self, nickname, channel, message):
        """
        Parse the IRC message using either a tracker config or basic regexp
        """

        # find a url...
        url_match = re.findall(r'(https?:\/\/[\da-z\.-]+\.[a-z\.]{2,6}[\/\w \.-\?&]*\/?)', message, re.MULTILINE)
        if url_match:
            # We have a URL(s)!, generate an entry
            if len(url_match) > 1:
                urls = list(url_match)
                url = urls[0]
            else:
                url = url_match[0]
                urls = []

            # If we have a regexp for the title, attempt to match
            title_regexp = self.config.get('title_regexp')
            if title_regexp:
                title_match = re.search(title_regexp, message)
                if title_match:
                    title = title_match.group(0)
                else:
                    title = message
            else:
                title = message

            # Return the entry object
            return Entry(title=title, url=url, urls=urls)

    def on_welcome(self, conn, event):
        log.info('IRC connected to %s' % self.connection_name)

        nickserv_password = self.config.get('nickserv_password')
        if nickserv_password:
        # If we've not got our peferred nickname and NickServ is configured, ghost the connection
            if conn.get_nickname() != self._nickname:
                log.info('Ghosting old connection')
                conn.privmsg('NickServ', 'GHOST %s %s' % (self._nickname, nickserv_password))
                conn.nick(self._nickname)
        
            # Identify with NickServ
            log.info('Identifying with NickServ as %s' % self._nickname)
            conn.privmsg('NickServ', 'IDENTIFY %s %s' % (self._nickname, nickserv_password))

        # Join Channels
        channels = self.config.get('channels', [])
        if not isinstance(channels, list):
            channels = [channels]
        for channel in channels:
            # If the channel name doesn't start with a normal prefix, add hash
            log.info('Joining channel %s' % channel)
            conn.join(channel)

    def on_pubmsg(self, conn, event):

        # Cache upto multi_lines value then pass them all for parsing
        multilines = self.config.get('multi_lines', 1)
        self.line_cache.append(event.arguments[0])
        if len(self.line_cache) >= multilines:
            entry = self.parse_message(event.source, event.target, ' '.join(self.line_cache))
            self.line_cache = []
            if entry:
                self.queue_entry(entry)


@event('manager.daemon.started')
def irc_start(manager):
    irc_update_config(manager)


@event('manager.config_updated')
def irc_update_config(manager):
    global irc

    # Exit if we're not running daemon mode
    if not manager.is_daemon:
        return

    # No config, no connections
    if 'irc' not in manager.config:
        log.info('No irc connections defined in the config')

    config = manager.config.get('irc')

    # Config for IRC has been removed, shutdown all instances
    stop_irc(manager)

    for key, connection in config.items():
        log.info('Starting IRC connection for %s' % key)
        conn = IRCConnection(connection, key)
        thread = threading.Thread(target=conn.start_interruptable, name=key)
        irc.append((conn, thread))
        thread.start()


@event('manager.shutdown_requested')
def shutdown_requested(manager):
    stop_irc(manager)


@event('manager.shutdown')
def stop_irc(manager):
    global irc

    for conn, thread in irc:
        if conn.connection.is_connected():
            conn.stop_bot = True
            thread.join()
    irc = []


@event('config.register')
def register_plugin():
    register_config_key('irc', schema)
