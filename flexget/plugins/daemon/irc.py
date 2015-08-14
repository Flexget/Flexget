from __future__ import unicode_literals, division, absolute_import, with_statement
import os
import re
import threading
import logging
from random import choice
from xml.etree import ElementTree as ET
import urllib

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
                    'tracker_file': {'type': 'string', 'format': 'file'},
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
                    'invite_nickname': {'type': 'string'},
                    'invite_message': {'type': 'string'},
                    'task': {'type': 'string'},
                    'queue_entries': {'type': 'integer', 'default': 1},
                },
                'required': ['task', 'server'],
                'additionalProperties': {'type': 'string'},
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
    MESSAGE_CLEAN = re.compile("\x0f|\x1f|\x02|\x03(?:[\d]{1,2}(?:,[\d]{1,2})?)?", re.MULTILINE | re.UNICODE)
    URL_MATCHER = re.compile(r'(https?:\/\/[\da-z\.-]+\.[a-z\.]{2,6}[\/\w\.-\?&]*\/?)', re.MULTILINE | re.UNICODE)

    def __init__(self, config, config_name):
        self.config = config
        self.connection_name = config_name
        self.server_list = []
        self.channel_list = []
        self.announcer_list = []
        self.ignore_lines = []
        self.message_regex = []

        # If we have a tracker config file, load it
        tracker_config_file = config.get('tracker_file')
        if tracker_config_file is not None:
            tracker_config_file = os.path.abspath(os.path.expanduser(tracker_config_file))
            if not os.path.exists(tracker_config_file):
                log.error('Unable to open tracker config file %s, ignoring' % tracker_config_file)
            else:
                with open(tracker_config_file, 'r') as f:
                    try:
                        tracker_config = ET.fromstring(f.read())
                    except Exception, e:
                        log.error('Unable to parse tracker config file %s: %s' % (tracker_config_file, e))
                    else:
                        self.tracker_config = tracker_config

        if self.tracker_config is not None:

            # Get the tracker name, for use in the connection name
            self.connection_name = self.tracker_config.get('longName', config_name)

            # Extract the IRC server information
            for server in self.tracker_config.find('servers'):
                self.server_list.extend(server.get('serverNames').split('|'))
                self.channel_list.extend(server.get('channelNames').split('|'))
                self.announcer_list.extend(server.get('announcerNames').split('|'))

            # Process ignore lines
            for regex_values in self.tracker_config.findall('parseinfo/ignore/regex'):
                rx = re.compile(regex_values.get('value'), re.UNICODE | re.MULTILINE)
                self.ignore_lines.append(rx)

            # Parse line patterns
            patterns = list(self.tracker_config.findall('parseinfo/multilinepatterns/extract')) + \
                       list(self.tracker_config.findall('parseinfo/linepatterns/extract'))
            for pattern in patterns:
                rx = re.compile(pattern.find('regex').get('value'), re.UNICODE | re.MULTILINE)
                vars = [var.get('name') for idx, var in enumerate(pattern.find('vars'))]
                self.message_regex.append((rx, vars))

        if not self.server_list or not self.channel_list:
            if self.tracker_config is not None:
                log.warning('No server or channel provided by tracker file, falling back to Flexget config options')
            self.server_list = [config.get('server')]
            channels = config.get('channels')
            if not isinstance(channels, basestring):
                channels = [channels]
            self.channel_list = channels

        log.debug('Servers: %s' % self.server_list)
        log.debug('Channels: %s' % self.channel_list)
        log.debug('Announcers: %s' % self.announcer_list)
        log.debug('Ignore Lines: %d' % len(self.ignore_lines))
        log.debug('Message Regexps: %d' % len(self.message_regex))

        # Init the IRC Bot
        server = choice(self.server_list)
        port = config.get('port', 6667)
        nickname = config.get('nickname', 'Flexget')
        SingleServerIRCBot.__init__(self, [(server, port)], nickname, nickname)
        self.stop_bot = False

        self.entry_queue = []
        self.line_cache = {}

    def start_interruptable(self, timeout=0.2):
        """Start the IRC connection in a interruptable state"""
        self._connect()
        while not self.stop_bot:
            self.reactor.process_once(timeout)
        self.disconnect()

    def run_tasks(self, entries):
        """
        Passes entries to the target task configured for this connection
        :param entries:
        :return:
        """
        from flexget.manager import manager

        log.info('Injecting %d entries into task %s' % (len(entries), self.config.get('task')))
        manager.execute(options={'tasks': [self.config.get('task')], 'cron': True, 'inject': entries}, priority=5)

    def queue_entry(self, entry):
        """
        Stores an entry in the connection entry queue, if the queue is over the size limit then submit them to the task
        :param entry: Entry to be queued
        :return:
        """
        self.entry_queue.append(entry)
        log.debug('Entry: %s', entry)
        if len(self.entry_queue) >= self.config.get('queue_entries', 1):
            self.run_tasks(self.entry_queue)
            self.entry_queue = []

    def parse_message(self, nickname, channel, message):
        """
        Parses a public message and generates an entry if needed
        :param nickname: Nickname of who sent the message
        :param channel: Channel where the message was receivied
        :param message: Message text
        :return:
        """

        # Clean up the message
        message = self.MESSAGE_CLEAN.sub('', message)

        # If we have announcers defined, ignore any messages not from them
        if len(self.announcer_list) and nickname not in self.announcer_list:
            log.debug('Ignoring message: from non-announcer %s' % nickname)
            return

        # If its listed in ignore lines, skip it
        for rx in self.ignore_lines:
            if rx.match(message):
                log.debug('Ignoring message: matched ignore line')
                return

        # Create the entry
        entry = Entry(irc_raw_message=message)

        # Run the config regex patterns over the message
        for rx, vals in self.message_regex:
            match = rx.search(message)
            if match:
                val_names = ['irc_%s' % val.lower() for val in vals]

                def clean_vals(x):
                    if isinstance(x, basestring):
                        return x.strip()
                    return x

                val_values = [clean_vals(x) for x in match.groups()]
                entry.update(dict(zip(val_names, val_values)))

        # Generate the entry and process it through the linematched rules
        if self.tracker_config is not None:
            entry = self.process_tracker_config_rules(entry)

        # If we have a torrentname, use it as the title
        entry['title'] = entry.get('irc_torrentname', message)

        # If we have a URL, use it
        if 'irc_torrenturl' in entry:
            entry['url'] = entry['irc_torrenturl']
        else:
            # find a url...
            url_match = self.URL_MATCHER.findall(message)
            if url_match:
                # We have a URL(s)!, generate an entry
                urls = list(url_match)
                url = urls[-1]
                entry.update({
                    'urls': urls,
                    'url': url,
                })

        log.debug('Entry after processing: %s' % dict(entry))
        return entry

    def process_tracker_config_rules(self, entry, rules=None):
        """
        Processes a Entry object with the linematched rules defined in a tracker config file
        :param entry: Entry to be updated
        :param rules: Ruleset to use.
        :return:
        """

        def prefix_var(var):
            return 'irc_%s' % var.lower()

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
                    if element.tag in ['var', 'varenc']:
                        varname = element.get('name')
                        if prefix_var(varname) in entry:
                            value = entry[prefix_var(varname)]
                        elif self.config.get(varname):
                            value = self.config.get(varname)
                        else:
                            log.error('Missing variable %s from config, skipping rule' % varname)
                            break
                        if element.tag == 'varenc':
                            value = urllib.quote(value)
                        result += value
                entry[prefix_var(rule.get('name'))] = result

            # Var Replace - replace text in a var
            elif rule.tag == 'varreplace':
                source_var = prefix_var(rule.get('srcvar'))
                target_var = prefix_var(rule.get('name'))
                regex = rule.get('regex')
                replace = rule.get('replace')
                entry[target_var] = re.sub(regex, replace, entry[source_var])

            # Extract - create multiple vars from a single regex
            elif rule.tag == 'extract':
                source_var = prefix_var(rule.get('srcvar'))
                if source_var not in entry:
                    if rule.get('optional', 'false') == 'false':
                        log.error('Error processing extract rule, non-optional value %s missing!' % source_var)
                    continue
                regex = rule.find('regex').get('value')
                group_names = [prefix_var(x.get('name')) for x in rule.find('vars')]
                match = re.search(regex, entry[source_var])
                if match:
                    entry.update(dict(zip(group_names, match.groups())))

            # Extract Tag - set a var if a regex matches a tag in a var
            elif rule.tag == 'extracttags':
                source_var = prefix_var(rule.get('srcvar'))
                split = rule.get('split')
                values = [x.strip() for x in entry[source_var].split(split)]
                for element in rule:
                    if element.tag == 'setvarif':
                        target_var = prefix_var(element.get('varName'))
                        regex = element.get('regex')
                        for val in values:
                            match = re.match(regex, val)
                            if match:
                                entry[target_var] = val

            # Set Regex - set a var if a regex matches
            elif rule.tag == 'setregex':
                source_var = prefix_var(rule.get('srcvar'))
                regex = rule.get('regex')
                target_var = prefix_var(rule.get('varName'))
                target_val = rule.get('newValue')
                if source_var in entry and re.match(regex, entry[source_var]):
                    entry[target_var] = target_val

            # If statement
            elif rule.tag == 'if':
                source_var = prefix_var(rule.get('srcvar'))
                regex = rule.get('regex')
                if source_var in entry and re.match(regex, entry[source_var]):
                    entry = self.process_tracker_config_rules(entry, rule)

            else:
                log.warning('Unsupported linematched tag: %s' % rule.tag)

        return entry

    def on_welcome(self, conn, event):
        log.info('IRC connected to %s' % self.connection_name)
        self.connection.execute_delayed(1, self.identify_with_nickserv)

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
            log.info('Identifying with NickServ as %s' % self._nickname)
            self.connection.privmsg('NickServ', 'IDENTIFY %s %s' % (self._nickname, nickserv_password))
        if self.config.get('invite_nickname'):
            self.connection.execute_delayed(5, self.request_channel_invite)
        else:
            self.connection.execute_delayed(5, self.join_channels)

    def request_channel_invite(self):
        """
        Requests an invite from the configured invite user.
        :return:
        """
        invite_nickname = self.config.get('invite_nickname')
        invite_message = self.config.get('invite_message')
        log.info('Requesting an invite to channels from %s' % invite_nickname)
        self.connection.privmsg(invite_nickname, invite_message)
        self.connection.execute_delayed(5, self.join_channels)

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

    def on_pubmsg(self, conn, event):
        nickname = event.source.split('!')[0]
        channel = event.target
        if channel not in self.line_cache:
            self.line_cache[channel] = {}
        if nickname not in self.line_cache[channel]:
            self.line_cache[channel][nickname] = []
        self.line_cache[channel][nickname].append(event.arguments[0])
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
        entry = self.parse_message(nickname, channel, lines.encode('utf-8'))
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
