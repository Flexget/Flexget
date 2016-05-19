from __future__ import unicode_literals, division, absolute_import, with_statement
from builtins import *  # pylint: disable=unused-import, redefined-builtin
from past.builtins import basestring

import os
import re
import threading
import logging
from random import choice
from xml.etree.ElementTree import fromstring
import urllib
from uuid import uuid4
import time

from flexget.entry import Entry
from flexget.config_schema import register_config_key
from flexget.event import event
from flexget.plugin import PluginError, DependencyError
from flexget.manager import manager

log = logging.getLogger('irc')

MESSAGE_CLEAN = re.compile("\x0f|\x1f|\x02|\x03(?:[\d]{1,2}(?:,[\d]{1,2})?)?", re.MULTILINE | re.UNICODE)
URL_MATCHER = re.compile(r'(https?://[\da-z\.-]+\.[a-z\.]{2,6}[/\w\.-\?&]*/?)', re.MULTILINE | re.UNICODE)
EXECUTION_DELAY = 5  # number of seconds for command execution delay

channel_pattern = {
    'type': 'string', 'pattern': '^([#&][^\x07\x2C\s]{0,200})',
    'error_pattern': 'channel name must start with # or & and contain no commas and whitespace'
}
schema = {
    'oneOf': [
        {
            'type': 'object',
            'additionalProperties': {
                'type': 'object',
                'properties': {
                    'tracker_file': {'type': 'string', 'format': 'file'},
                    'server': {'type': 'string'},
                    'port': {'type': 'integer', 'default': 6667},
                    'nickname': {'type': 'string'},
                    'channels': {
                        'oneOf': [
                            {'type': 'array',
                             'items': channel_pattern
                             },
                            channel_pattern
                        ],
                    },
                    'nickserv_password': {'type': 'string'},
                    'invite_nickname': {'type': 'string'},
                    'invite_message': {'type': 'string'},
                    'task': {
                        'oneOf': [
                            {'type': 'string'},
                            {'type': 'array', 'items': {'type': 'string'}},
                        ]
                    },
                    'queue_size': {'type': 'integer', 'default': 1},
                },
                'anyOf': [
                    {'required': ['server', 'channels']},
                    {'required': ['tracker_file']}
                ],
                'error_anyOf': 'Must specify a tracker file or server and channel(s)',
                'required': ['task'],
                'additionalProperties': {'type': 'string'},
            }
        },
        {'type': 'boolean', 'enum': [False]},
    ]
}

# Global that holds all the IRCConnection instances
irc_connections = {}
# The manager object and thread
irc_manager = None


def spawn_thread(name, conn):
    """
    Creates a new thread and starts it
    :param conn: IRCConnection or IRCConnectionManager object
    :return: Thread
    """
    thread = threading.Thread(target=conn.start_interruptable, name=name)
    thread.start()
    return thread


def irc_prefix(var):
    """
    Prefix a string with the irc_
    :param var: Variable to prefix
    :return: Prefixed variable
    """
    if isinstance(var, basestring):
        return 'irc_%s' % var.lower()


def strip_whitespace(value):
    """
    Remove leading and trailing whitespace from strings. Return value if not a string.
    :param value:
    :return: stripped string or value
    """
    if isinstance(value, basestring):
        return value.strip()
    return value


class TrackerFileParseError(Exception):
    """Exception thrown when parsing the tracker file fails"""


def install_ircconnection():
    class IRCConnection(SingleServerIRCBot):

        def __init__(self, config, config_name):
            self.config = config
            self.connection_name = config_name
            self.tracker_config = None
            self.server_list = []
            self.channel_list = []
            self.announcer_list = []
            self.ignore_lines = []
            self.message_regex = []

            # If we have a tracker config file, load it
            tracker_config_file = config.get('tracker_file')
            if tracker_config_file:
                tracker_config_file = os.path.abspath(os.path.expanduser(tracker_config_file))
                if not os.path.exists(tracker_config_file):
                    raise TrackerFileParseError('Unable to open tracker config file %s', tracker_config_file)
                else:
                    with open(tracker_config_file, 'r') as f:
                        try:
                            tracker_config = fromstring(f.read())
                        except Exception as e:
                            raise TrackerFileParseError('Unable to parse tracker config file %s: %s',
                                                        tracker_config_file, e)
                        else:
                            self.tracker_config = tracker_config

            if self.tracker_config is not None:

                # Validate config with the settings in the torrent file
                for param in self.tracker_config.find('settings'):

                    # Handle textbox entries
                    if param.tag == 'textbox':
                        value_name = param.get('name')
                    else:
                        value_name = param.tag

                    # Strip the gazelle prefix
                    if value_name.startswith('gazelle_'):
                        value_name = value_name.replace('gazelle_', '')

                    # Skip descriptions
                    if value_name in ['description']:
                        continue

                    if self.config.get(value_name) is None:
                        raise PluginError('missing configuration option on irc config %s - %s' % (self.connection_name,
                                                                                                  value_name))

                # Get the tracker name, for use in the connection name
                self.connection_name = self.tracker_config.get('longName', config_name)

                # Extract the IRC server information
                for server in self.tracker_config.find('servers'):
                    self.server_list.extend(server.get('serverNames').split(','))
                    self.channel_list.extend(server.get('channelNames').split(','))
                    self.announcer_list.extend(server.get('announcerNames').split(','))

                # Process ignore lines
                for regex_values in self.tracker_config.findall('parseinfo/ignore/regex'):
                    rx = re.compile(regex_values.get('value'), re.UNICODE | re.MULTILINE)
                    self.ignore_lines.append(rx)

                # Parse line patterns
                patterns = list(self.tracker_config.findall('parseinfo/multilinepatterns/extract')) + \
                    list(self.tracker_config.findall('parseinfo/linepatterns/extract'))
                for pattern in patterns:
                    rx = re.compile(pattern.find('regex').get('value'), re.UNICODE | re.MULTILINE)
                    vals = [var.get('name') for idx, var in enumerate(pattern.find('vars'))]
                    self.message_regex.append((rx, vals))

            # overwrite tracker config with flexget config
            if self.config.get('server'):
                self.server_list = [self.config['server']]
                log.debug('Using server specified from config')
            channels = config.get('channels')
            if channels:
                self.channel_list = channels if isinstance(channels, list) else [channels]
                log.debug('Using channel(s) specified from config')

            log.debug('Servers: %s', self.server_list)
            log.debug('Channels: %s', self.channel_list)
            log.debug('Announcers: %s', self.announcer_list)
            log.debug('Ignore Lines: %d', len(self.ignore_lines))
            log.debug('Message Regexs: %d', len(self.message_regex))
            for rx, vals in self.message_regex:
                log.debug('    Pattern "%s" extracts %s', rx.pattern, vals)

            # Init the IRC Bot
            server = choice(self.server_list)
            port = config.get('port', 6667)
            nickname = config.get('nickname', 'Flexget-%s' % str(uuid4()))
            super(IRCConnection, self).__init__([(server, port)], nickname, nickname)
            self.connection.add_global_handler('nicknameinuse', self.on_nicknameinuse)
            self.connection.add_global_handler('error', self.on_error)
            self.shutdown_event = threading.Event()
            self.connection_attempts = 0
            self.inject_before_shutdown = False
            self.entry_queue = []
            self.line_cache = {}

            self.start_thread()

        def start_thread(self):
            self.thread = spawn_thread(self.connection_name, self)

        def is_alive(self):
            return self.thread and self.thread.is_alive()

        def check_connection_and_reconnect(self):
            if not self.is_connected() and self.connection_attempts < 5:
                time.sleep(self.connection_attempts * 2)
                self._connect()
            elif not self.is_connected():
                server = self.server_list[0]
                log.error('Failed to connect to %s:%s after %s attempts. Stopping thread.', server.host, server.port,
                          self.connection_attempts)
                self.shutdown_event.set()
            elif self.connection_attempts > 0:
                self.connection_attempts = 0

        def start_interruptable(self, timeout=0.2):
            """
            Start the IRC bot
            :param timeout: Maximum wait time between process cycles
            :return:
            """
            self._connect()
            while not self.shutdown_event.is_set():
                self.check_connection_and_reconnect()
                self.reactor.process_once(timeout)
            if self.inject_before_shutdown and self.entry_queue:
                self.run_tasks()
            self.disconnect()
            log.info('Shutting down IRC connection for %s', self.connection_name)

        def _connect(self):
            """
            Establish a connection to the server at the front of the server_list.
            """
            server = self.server_list[0]
            try:
                self.connection_attempts += 1
                self.connect(server.host, server.port, self._nickname,
                    server.password, ircname=self._realname)
            except ServerConnectionError as e:
                log.error('Connection to %s on port %s failed: %s. Please recheck your config.', server.host,
                          server.port, e)

        def run_tasks(self):
            """
            Passes entries to the target task configured for this connection
            :param entries:
            :return:
            """
            tasks = self.config.get('task')
            if isinstance(tasks, basestring):
                tasks = [tasks]

            log.info('Injecting %d entries into tasks %s', len(self.entry_queue), ', '.join(tasks))
            manager.execute(options={'tasks': tasks, 'cron': True, 'inject': self.entry_queue}, priority=5)

        def queue_entry(self, entry):
            """
            Stores an entry in the connection entry queue, if the queue is over the size limit then submit them
            :param entry: Entry to be queued
            :return:
            """
            self.entry_queue.append(entry)
            log.debug('Entry: %s', entry)
            if len(self.entry_queue) >= self.config['queue_size']:
                self.run_tasks()
                self.entry_queue = []

        def parse_message(self, nickname, channel, message):
            """
            Parses a public message and generates an entry if the message matches the regex or contains a url
            :param nickname: Nickname of who sent the message
            :param channel: Channel where the message was receivied
            :param message: Message text
            :return:
            """

            # Clean up the message
            message = MESSAGE_CLEAN.sub('', message)

            # If we have announcers defined, ignore any messages not from them
            if self.announcer_list and nickname not in self.announcer_list:
                log.debug('Ignoring message: from non-announcer %s', nickname)
                return

            # If it's listed in ignore lines, skip it
            for rx in self.ignore_lines:
                if rx.match(message):
                    log.debug('Ignoring message: matched ignore line')
                    return

            # Create the entry
            entry = Entry(irc_raw_message=message)

            match_found = False
            # Run the config regex patterns over the message
            for rx, vals in self.message_regex:
                log.debug('Using pattern %s to parse message vars', rx.pattern)
                match = rx.search(message)
                if match:
                    val_names = [irc_prefix(val.lower()) for val in vals]
                    val_values = [strip_whitespace(x) for x in match.groups()]
                    entry.update(dict(zip(val_names, val_values)))
                    log.debug('Found: %s', dict(zip(val_names, val_values)))
                    match_found = True
                    break
                else:
                    log.debug('No matches found')

            # Generate the entry and process it through the linematched rules
            if self.tracker_config is not None and match_found:
                self.process_tracker_config_rules(entry)
            elif self.tracker_config is not None:
                log.error('Failed to parse message. Skipping.')
                return None

            # If we have a torrentname, use it as the title
            entry['title'] = entry.get('irc_torrentname', message)

            # If we have a URL, use it
            if 'irc_torrenturl' in entry:
                entry['url'] = entry['irc_torrenturl']
            else:
                # find a url...
                url_match = URL_MATCHER.findall(message)
                if url_match:
                    # We have a URL(s)!, generate an entry
                    urls = list(url_match)
                    url = urls[-1]
                    entry.update({
                        'urls': urls,
                        'url': url,
                    })

            log.debug('Entry after processing: %s', dict(entry))
            if not entry.get('url'):
                log.error('Parsing message failed. No url found.')
                return None
            return entry

        def process_tracker_config_rules(self, entry, rules=None):
            """
            Processes an Entry object with the linematched rules defined in a tracker config file
            :param entry: Entry to be updated
            :param rules: Ruleset to use.
            :return:
            """

            if rules is None:
                rules = self.tracker_config.find('parseinfo/linematched')

            for rule in rules:
                log.debug('Processing rule %s' % rule.tag)

                # Var - concat a var from other vars
                if rule.tag == 'var':
                    result = ''
                    for element in rule:
                        if element.tag == 'string':
                            result += element.get('value')
                        elif element.tag in ['var', 'varenc']:
                            varname = element.get('name')
                            if irc_prefix(varname) in entry:
                                value = entry[irc_prefix(varname)]
                            elif self.config.get(varname):
                                value = self.config.get(varname)
                            else:
                                log.error('Missing variable %s from config, skipping rule', varname)
                                break
                            if element.tag == 'varenc':
                                value = urllib.quote(value)
                            result += value
                        else:
                            log.error('Unsupported var operation %s, skipping rule', element.tag)
                            break
                    else:
                        # Only set the result if we processed all elements
                        log.debug('Result for rule %s: %s=%s', rule.tag, rule.get('name'), result)
                        entry[irc_prefix(rule.get('name'))] = result

                # Var Replace - replace text in a var
                elif rule.tag == 'varreplace':
                    source_var = irc_prefix(rule.get('srcvar'))
                    target_var = irc_prefix(rule.get('name'))
                    regex = rule.get('regex')
                    replace = rule.get('replace')
                    if source_var and target_var and regex is not None and replace is not None:
                        entry[target_var] = re.sub(regex, replace, entry[source_var])
                        log.debug('varreplace: %s=%s', target_var, entry[target_var])
                    else:
                        log.error('Invalid varreplace options, skipping rule')

                # Extract - create multiple vars from a single regex
                elif rule.tag == 'extract':
                    source_var = irc_prefix(rule.get('srcvar'))
                    if source_var not in entry:
                        if rule.get('optional', 'false') == 'false':
                            log.error('Error processing extract rule, non-optional value %s missing!', source_var)
                        continue
                    if rule.find('regex') is not None:
                        regex = rule.find('regex').get('value')
                    else:
                        log.error('Regex option missing on extract rule, skipping rule')
                        continue
                    group_names = [irc_prefix(x.get('name')) for x in rule.find('vars') if x.tag == 'var']
                    match = re.search(regex, entry[source_var])
                    if match:
                        entry.update(dict(zip(group_names, match.groups())))
                    else:
                        log.debug('No match found for rule extract')

                # Extract Tag - set a var if a regex matches a tag in a var
                elif rule.tag == 'extracttags':
                    source_var = irc_prefix(rule.get('srcvar'))
                    split = rule.get('split')
                    values = [strip_whitespace(x) for x in entry[source_var].split(split)]
                    for element in rule:
                        if element.tag == 'setvarif':
                            target_var = irc_prefix(element.get('varName'))
                            regex = element.get('regex')
                            value = element.get('value')
                            new_value = element.get('newValue')
                            if regex is not None:
                                found_match = False
                                for val in values:
                                    match = re.match(regex, val)
                                    if match:
                                        entry[target_var] = val
                                        found_match = True
                                if not found_match:
                                    log.debug('No matches found for regex %s', regex)
                            elif value is not None and new_value is not None:
                                if value in values:
                                    entry[target_var] = new_value
                                else:
                                    log.debug('No match found for value %s in %s', value, source_var)
                            else:
                                log.error('Missing regex/value/newValue for setvarif command, ignoring')

                # Extract One - extract one var from a list of regexes
                elif rule.tag == 'extractone':
                    for element in rule:
                        if element.tag == 'extract':
                            source_var = irc_prefix(element.get('srcvar'))
                            if element.find('regex') is not None:
                                regex = element.find('regex').get('value')
                            else:
                                log.error('Regex option missing on extract rule, skipping.')
                                continue
                            if element.find('vars') is not None:
                                vars = [irc_prefix(var.get('name')) for var in element.find('vars')]
                            else:
                                log.error('No variable bindings found in extract rule, skipping.')
                                continue
                            match = re.match(regex, entry.get(source_var, ''))
                            if match:
                                entry.update(dict(zip(vars, match.groups())))
                            else:
                                log.debug('No match for extract with regex: %s', regex)
                        else:
                            log.error('Unsupported extractone tag: %s', element.tag)

                # Set Regex - set a var if a regex matches
                elif rule.tag == 'setregex':
                    source_var = irc_prefix(rule.get('srcvar'))
                    regex = rule.get('regex')
                    target_var = irc_prefix(rule.get('varName'))
                    target_val = rule.get('newValue')
                    if source_var and regex and target_var and target_val:
                        if source_var in entry and re.match(regex, entry[source_var]):
                            entry[target_var] = target_val
                    else:
                        log.error('Option missing on setregex, skipping rule')

                # If statement
                elif rule.tag == 'if':
                    source_var = irc_prefix(rule.get('srcvar'))
                    regex = rule.get('regex')

                    if source_var and regex:
                        if source_var in entry and re.match(regex, entry[source_var]):
                            self.process_tracker_config_rules(entry, rule)
                    else:
                        log.error('Option missing for if statement, skipping rule')

                else:
                    log.warning('Unsupported linematched tag: %s', rule.tag)

        def on_welcome(self, conn, irc_event):
            log.info('IRC connected to %s', self.connection_name)
            self.connection.execute_delayed(1, self.identify_with_nickserv)

        def on_nicknameinuse(self, conn, irc_event):
            conn.nick(conn.get_nickname() + "_")

        def identify_with_nickserv(self):
            """
            Identifies the connection with Nickserv, ghosting to recover the nickname if required
            :return:
            """
            nickserv_password = self.config.get('nickserv_password')
            if nickserv_password:
                # If we've not got our peferred nickname and NickServ is configured, ghost the connection
                if self.connection.get_nickname() != self._nickname:
                    log.info('Ghosting old connection')
                    self.connection.privmsg('NickServ', 'GHOST %s %s' % (self._nickname, nickserv_password))
                    self.connection.nick(self._nickname)

                # Identify with NickServ
                log.info('Identifying with NickServ as %s', self._nickname)
                self.connection.privmsg('NickServ', 'IDENTIFY %s' % nickserv_password)
            if self.config.get('invite_nickname'):
                self.connection.execute_delayed(EXECUTION_DELAY, self.request_channel_invite)
            else:
                self.connection.execute_delayed(EXECUTION_DELAY, self.join_channels)

        def request_channel_invite(self):
            """
            Requests an invite from the configured invite user.
            :return:
            """
            invite_nickname = self.config.get('invite_nickname')
            invite_message = self.config.get('invite_message')
            log.info('Requesting an invite to channels from %s', invite_nickname)
            self.connection.privmsg(invite_nickname, invite_message)
            self.connection.execute_delayed(EXECUTION_DELAY, self.join_channels)

        def join_channels(self):
            """
            Joins any channels configured if not already in them
            :return:
            """
            # Queue to join channels, we want to wait for NickServ to work before joining
            for channel in self.channel_list:
                if channel not in self.channels:
                    log.info('Joining channel %s' % channel)
                    self.connection.join(channel)

        def on_pubmsg(self, conn, irc_event):
            nickname = irc_event.source.split('!')[0]
            channel = irc_event.target
            if channel not in self.line_cache:
                self.line_cache[channel] = {}
            if nickname not in self.line_cache[channel]:
                self.line_cache[channel][nickname] = []
            self.line_cache[channel][nickname].append(irc_event.arguments[0])
            if len(self.line_cache[channel][nickname]) == 1:
                # Schedule a parse of the message in 1 second (for multilines)
                conn.execute_delayed(1, self.process_message, (nickname, channel))

        def process_message(self, nickname, channel):
            """
            Pops lines from the line cache and passes them to be parsed
            :param nickname: Nickname of who sent hte message
            :param channel: Channel where the message originated from
            :return: None
            """
            lines = u'\n'.join(self.line_cache[channel][nickname])
            self.line_cache[channel][nickname] = []
            log.debug('Received lines: %s', lines)
            entry = self.parse_message(nickname, channel, lines)
            if entry:
                log.verbose('IRC message in %s generated an entry: %s', channel, entry)
                self.queue_entry(entry)

        def on_error(self, conn, irc_event):
            log.error('Error message received: %s', irc_event)

        def is_connected(self):
            return self.connection.is_connected()

        def stop(self, wait):
            if self.is_connected():
                if wait:
                    self.inject_before_shutdown = True
                self.shutdown_event.set()

    @event('manager.daemon.started')
    def irc_start(manager):
        irc_update_config(manager)

    @event('manager.config_updated')
    def irc_update_config(manager):
        global irc_manager

        # Exit if we're not running daemon mode
        if not manager.is_daemon:
            return

        config = manager.config.get('irc')

        if not irc_exists and config:
            log.error('irc module required to use the daemon irc plugin. Install with `pip install irc`.')
            sys.exit(-1)

        # Config for IRC has been removed, shutdown all instances
        stop_irc(manager)

        # No config, no connections
        if not config:
            log.info('No irc connections defined in the config')
            return

        irc_manager = IRCConnectionManager(config)

    class IRCConnectionManager(object):

        def __init__(self, config):
            self.config = config
            self.shutdown_event = threading.Event()
            self.wait = False
            self.restart_log = {}
            self.warning_delay = 30
            self.max_delay = 300  # 5 minutes
            self.thread = spawn_thread('irc_manager', self)

        def is_alive(self):
            return self.thread and self.thread.is_alive()

        def start_interruptable(self):
            """
            Checks for dead threads and attempts to restart them. Uses a pseudo exponential backoff strategy for
            reconnecting to avoid being throttled by the IRC server(s).
            :return:
            """
            global irc_connections

            self.start_connections()

            while not self.shutdown_event.is_set():
                for conn_name, conn in irc_connections.items():
                    if not conn and self.config.get(conn_name):
                        new_conn = IRCConnection(self.config[conn_name], conn_name)
                        irc_connections[conn_name] = new_conn
                    elif not conn.is_alive() and self.restart_log[conn_name]['delay'] <= 0:
                        log.error('IRC connection for %s has died unexpectedly. Restarting it.', conn_name)
                        self.restart_log[conn_name]['attempts'] += 1
                        self.restart_log[conn_name]['delay'] = min(pow(2, self.restart_log[conn_name]['attempts']),
                                                                   self.max_delay)
                        conn.start_thread()

                    if self.restart_log[conn_name]['delay'] > 0:
                        # reduce delay with 0.2 seconds. This is not meant to be precise, merely to avoid throttling.
                        self.restart_log[conn_name]['delay'] -= 0.2
                    elif self.restart_log[conn_name]['attempts'] > 0:
                        log.info('IRC connection for %s has been successfully restarted.', conn_name)
                        self.restart_log[conn_name] = {'attempts': 0, 'delay': 0}
                time.sleep(0.2)

            self.stop_connections(self.wait)

        def start_connections(self):
            global irc_connections

            for conn_name, connection in self.config.items():
                log.info('Starting IRC connection for %s', conn_name)
                conn = IRCConnection(connection, conn_name)
                irc_connections[conn_name] = conn
                self.restart_log[conn_name] = {'attempts': 0, 'delay': 0}

        def stop_connections(self, wait):
            global irc_connections

            for conn_name, conn in irc_connections.items():
                conn.stop(wait)
                conn.thread.join()
            irc_connections = {}

        def restart_connection(self, conn_name):
            global irc_connections

            if not irc_connections[conn_name].is_alive():
                irc_connections[conn_name][0].start_thread()

        def stop(self, wait):
            self.wait = wait
            self.shutdown_event.set()

    @event('manager.shutdown_requested')
    def shutdown_requested(manager):
        stop_irc(manager, wait=True)

    @event('manager.shutdown')
    def stop_irc(manager, wait=False):
        global irc_manager

        if irc_manager and irc_manager.is_alive():
            log.info('Shutting down IRC.')
            irc_manager.stop(wait)
            irc_manager.thread.join(10)


try:
    from irc.bot import SingleServerIRCBot
    from irc.client import ServerConnectionError
    irc_exists = True
except ImportError:
    irc_exists = False
else:
    install_ircconnection()


@event('config.register')
def register_plugin():
    register_config_key('irc', schema)
