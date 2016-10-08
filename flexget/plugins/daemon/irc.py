from __future__ import unicode_literals, division, absolute_import, with_statement
from builtins import *  # pylint: disable=unused-import, redefined-builtin
from past.builtins import basestring

import os
import re
import threading
import logging
from xml.etree.ElementTree import parse
import io
from uuid import uuid4
import time
import urllib
from datetime import datetime, timedelta

from flexget.entry import Entry
from flexget.config_schema import register_config_key
from flexget.event import event
from flexget.manager import manager
from flexget.config_schema import one_or_more
from flexget.utils import requests
from flexget.utils.tools import get_config_hash

try:
    from irc_bot.irc_bot import IRCBot
    from irc_bot.irc_bot import partial
    from irc_bot import irc_bot
except ImportError as e:
    irc_bot = None
    IRCBot = object

log = logging.getLogger('irc')

MESSAGE_CLEAN = re.compile("\x0f|\x1f|\x02|\x03(?:[\d]{1,2}(?:,[\d]{1,2})?)?", re.MULTILINE | re.UNICODE)
URL_MATCHER = re.compile(r'(https?://[\da-z\.-]+\.[a-z\.]{2,6}[/\w\.-\?&]*/?)', re.MULTILINE | re.UNICODE)

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
                    'tracker_file': {'type': 'string'},
                    'server': {'type': 'string'},
                    'port': {'type': 'integer'},
                    'nickname': {'type': 'string'},
                    'channels': one_or_more(channel_pattern),
                    'nickserv_password': {'type': 'string'},
                    'invite_nickname': {'type': 'string'},
                    'invite_message': {'type': 'string'},
                    'task': one_or_more({
                        'type': 'string'
                    }),
                    'task_re': {
                        'type': 'object',
                        'additionalProperties': one_or_more({
                            'type': 'object',
                            'properties': {
                                'regexp': {'type': 'string'},
                                'field': {'type': 'string'}
                            },
                            'required': ['regexp', 'field'],
                            'additionalProperties': False
                        })
                    },
                    'queue_size': {'type': 'integer', 'default': 1},
                    'use_ssl': {'type': 'boolean', 'default': False},
                    'task_delay': {'type': 'integer'},
                },
                'anyOf': [
                    {'required': ['server', 'channels']},
                    {'required': ['tracker_file']}
                ],
                'error_anyOf': 'Must specify a tracker file or server and channel(s)',
                'oneOf': [
                    {'required': ['task']},
                    {'required': ['task_re']}
                ],
                'error_oneOf': 'Must specify a task',
                'required': ['port'],
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
# To avoid having to restart the connections whenever the config updated event is fired (which is apparently a lot)
config_hash = {}


def create_thread(name, conn):
    """
    Creates a new thread and starts it
    :param conn: IRCConnection or IRCConnectionManager object
    :return: Thread
    """
    thread = threading.Thread(target=conn.start, name=name)
    thread.setDaemon(True)
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


class TrackerFileError(Exception):
    """Exception thrown when parsing the tracker file fails"""


class MissingConfigOption(Exception):
    """Exception thrown when a config option specified in the tracker file is not on the irc config"""


class IRCConnection(IRCBot):
    def __init__(self, config, config_name):
        self.config = config
        self.connection_name = config_name
        self.tracker_config = None
        self.server_list = []
        self.announcer_list = []
        self.ignore_lines = []
        self.message_regex = []

        # If we have a tracker config file, load it
        tracker_config_file = config.get('tracker_file')
        if tracker_config_file:
            self.tracker_config = self.retrieve_tracker_config(tracker_config_file)

        channel_list = []
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
                if 'description' in value_name:
                    continue

                if self.config.get(value_name) is None:
                    raise MissingConfigOption('missing configuration option on irc config %s: %s' %
                                              (self.connection_name, value_name))

            # Get the tracker name, for use in the connection name
            self.connection_name = self.tracker_config.get('longName', config_name)

            # Extract the IRC server information
            for server in self.tracker_config.find('servers'):
                self.server_list.extend(server.get('serverNames').split(','))
                channel_list.extend(server.get('channelNames').split(','))
                self.announcer_list.extend(server.get('announcerNames').split(','))

            # Process ignore lines
            for regex_values in self.tracker_config.findall('parseinfo/ignore/regex'):
                rx = re.compile(regex_values.get('value'), re.UNICODE | re.MULTILINE)
                self.ignore_lines.append((rx, regex_values.get('expected') != 'false'))

            # Parse patterns
            self.multilinepatterns = self.parse_patterns(list(
                self.tracker_config.findall('parseinfo/multilinepatterns/extract')))
            self.linepatterns = self.parse_patterns(list(
                self.tracker_config.findall('parseinfo/linepatterns/extract')))

        # overwrite tracker config with flexget config
        if self.config.get('server'):
            self.server_list = [self.config['server']]
            log.debug('Using server specified from config')
        channels = config.get('channels')
        if channels:
            channel_list = channels if isinstance(channels, list) else [channels]
            log.debug('Using channel(s) specified from config')

        log.debug('Servers: %s', self.server_list)
        log.debug('Channels: %s', channel_list)
        log.debug('Announcers: %s', self.announcer_list)
        log.debug('Ignore Lines: %d', len(self.ignore_lines))
        log.debug('Message Regexs: %d', len(self.multilinepatterns) + len(self.linepatterns))
        for rx, vals in self.multilinepatterns:
            log.debug('    Multilinepattern "%s" extracts %s', rx.pattern, vals)
        for rx, vals in self.linepatterns:
            log.debug('    Linepattern "%s" extracts %s', rx.pattern, vals)

        # Init the IRC Bot
        ircbot_config = {'servers': self.server_list, 'port': config['port'], 'channels': channel_list,
                         'nickname': config.get('nickname', 'Flexget-%s' % str(uuid4())),
                         'invite_nickname': config.get('invite_nickname'),
                         'invite_message': config.get('invite_message'),
                         'nickserv_password': config.get('nickserv_password'),
                         'use_ssl': config.get('use_ssl')}
        IRCBot.__init__(self, ircbot_config)

        self.inject_before_shutdown = False
        self.entry_queue = []
        self.line_cache = {}
        self.thread = create_thread(self.connection_name, self)

    @classmethod
    def read_tracker_config(cls, path):
        """
        Attempts to open and parse the .tracker file specified in path
        :param path: path to .tracker file
        :return: the parsed XML
        """
        try:
            tracker_config = parse(path).getroot()
        except Exception as e:
            raise TrackerFileParseError('Unable to parse tracker config file %s: %s' % (path, e))
        else:
            return tracker_config

    @classmethod
    def retrieve_tracker_config(cls, tracker_config_file):
        """
        Will attempt to retrieve the .tracker file from disk or github. Returns the parsed XML.
        :param tracker_config_file: URL or path to .tracker file
        :return: parsed XML
        """
        base_url = 'https://raw.githubusercontent.com/autodl-community/autodl-trackers/master/'
        tracker_config_file = os.path.expanduser(tracker_config_file)

        # First we attempt to find the file locally as-is
        if os.path.exists(tracker_config_file):
            log.debug('Found tracker file: %s', tracker_config_file)
            return cls.read_tracker_config(tracker_config_file)

        if not tracker_config_file.endswith('.tracker'):
            tracker_config_file += '.tracker'

            # Maybe the file is missing extension?
            if os.path.exists(tracker_config_file):
                log.debug('Found tracker file: %s', tracker_config_file)
                return cls.read_tracker_config(tracker_config_file.rsplit('.tracker')[0])

        # Check that containing dir exists, otherwise default to flexget_config_dir/trackers
        if os.path.exists(os.path.dirname(tracker_config_file)):
            base_dir = os.path.dirname(tracker_config_file)
        else:
            base_dir = os.path.abspath(os.path.join(manager.config_base, 'trackers'))
        # Find the filenames for easy use later
        tracker_name = os.path.basename(tracker_config_file)
        tracker_name_no_ext = os.path.splitext(tracker_name)[0]
        # One last try with case insensitive search!
        if os.path.exists(base_dir):
            files = os.listdir(base_dir)
            for f in files:
                if tracker_name_no_ext.lower() in f.lower():
                    found_path = os.path.join(base_dir, f)
                    log.debug('Found tracker file: %s', found_path)
                    return cls.read_tracker_config(found_path)

        # Download from Github instead
        if not os.path.exists(base_dir):  # will only try to create the default `trackers` dir
            try:
                os.mkdir(base_dir)
            except IOError as e:
                raise TrackerFileError(e)
        log.info('Tracker file not found on disk. Attempting to fetch tracker config file from Github.')
        tracker = None
        try:
            tracker = requests.get(base_url + tracker_config_file)
        except (requests.RequestException, IOError):
            pass
        if not tracker:
            try:
                log.debug('Trying to search list of tracker files on Github')
                # Try to see if it's not found due to case sensitivity
                trackers = requests.get('https://api.github.com/repos/autodl-community/'
                                        'autodl-trackers/git/trees/master?recursive=1').json().get('tree', [])
                for tracker in trackers:
                    name = tracker.get('path', '')
                    if not name.endswith('.tracker') or name.lower() != tracker_name.lower():
                        continue
                    tracker = requests.get(base_url + name)
                    tracker_name = name
                    break
            except (requests.RequestException, IOError) as e:
                raise TrackerFileError(e)
        if not tracker:
            raise TrackerFileError('Unable to find %s on disk or Github' % tracker_config_file)

        # If we got this far, let's save our work :)
        save_path = os.path.join(base_dir, tracker_name)
        with io.open(save_path, 'wb') as tracker_file:
            for chunk in tracker.iter_content(8192):
                tracker_file.write(chunk)
        return cls.read_tracker_config(save_path)

    def is_alive(self):
        return self.thread and self.thread.is_alive()

    def parse_patterns(self, patterns):
        """
        Parses the patterns and creates a tuple with the compiled regex pattern and the variables it produces
        :param patterns: list of regex patterns as .tracker XML
        :return: list of (regex, variables)-pairs
        """
        result = []
        for pattern in patterns:
            rx = re.compile(pattern.find('regex').get('value'), re.UNICODE | re.MULTILINE)
            vals = [var.get('name') for idx, var in enumerate(pattern.find('vars'))]
            result.append((rx, vals))
        return result

    def quit(self):
        """
        Quit the IRC bot
        :return:
        """
        if self.inject_before_shutdown and self.entry_queue:
            self.run_tasks()
        IRCBot.quit(self)

    def run_tasks(self):
        """
        Passes entries to the target task(s) configured for this connection
        :return:
        """
        tasks = self.config.get('task')
        tasks_re = self.config.get('task_re')
        if tasks:
            if isinstance(tasks, basestring):
                tasks = [tasks]
            log.info('Injecting %d entries into tasks %s', len(self.entry_queue), ', '.join(tasks))
            manager.execute(options={'tasks': tasks, 'cron': True, 'inject': self.entry_queue, 'allow_manual': True},
                            priority=5)

        if tasks_re:
            tasks_entry_map = {}
            for entry in self.entry_queue:
                matched = False
                for task, config in tasks_re.items():
                    if isinstance(config, dict):
                        config = [config]
                    for c in config:
                        if re.search(c['regexp'], entry.get(c['field'], ''), re.IGNORECASE):
                            matched = True
                            if not tasks_entry_map.get(task):
                                tasks_entry_map[task] = []
                            tasks_entry_map[task].append(entry)
                if not matched:
                    log.info('Entry "%s" did not match any task regexp.', entry['title'])

            for task, entries in tasks_entry_map.items():
                log.info('Injecting %d entries into task "%s"', len(entries), task)
                manager.execute(options={'tasks': [task], 'cron': True, 'inject': entries, 'allow_manual': True},
                                priority=5)

        self.entry_queue = []

    def queue_entry(self, entry):
        """
        Stores an entry in the connection entry queue, if the queue is over the size limit then submit them
        :param entry: Entry to be queued
        :return:
        """
        self.entry_queue.append(entry)
        log.debug('Entry: %s', entry)
        if len(self.entry_queue) >= self.config['queue_size']:
            if self.config.get('task_delay'):
                self.schedule.queue_command(self.config['task_delay'], self.run_tasks, unique=False)
            else:
                self.run_tasks()

    def parse_privmsg(self, nickname, channel, message):
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
        for (rx, expected) in self.ignore_lines:
            if rx.match(message) and expected:
                log.debug('Ignoring message: matched ignore line')
                return

        # Create the entry
        entry = Entry(irc_raw_message=message)

        # Run the config regex patterns over the message
        matched_linepatterns = self.match_message_patterns(self.linepatterns, message)
        matched_multilinepatterns = self.match_message_patterns(self.multilinepatterns, message, multiline=True)

        if matched_linepatterns:
            match_found = True
            entry.update(matched_linepatterns)
        elif matched_multilinepatterns:
            match_found = True
            entry.update(matched_multilinepatterns)
        else:
            log.warning('Received message doesn\'t match any regexes.')
            return None

        # Generate the entry and process it through the linematched rules
        if self.tracker_config is not None and match_found:
            entry.update(self.process_tracker_config_rules(entry))
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

    def match_message_patterns(self, patterns, msg, multiline=False):
        """
        Tries to match the message to the list of patterns. Supports multiline messages.
        :param patterns: list of (regex, variable)-pairs
        :param msg: The parsed IRC message
        :param multiline: True if msg is multiline
        :return: A dict of the variables and their extracted values
        """
        result = {}
        for rx, vals in patterns:
            log.debug('Using pattern %s to parse message vars', rx.pattern)
            match = rx.search(msg)
            if match:
                val_names = [irc_prefix(val.lower()) for val in vals]
                val_values = [strip_whitespace(x) for x in match.groups()]
                result.update(dict(zip(val_names, val_values)))
                log.debug('Found: %s', dict(zip(val_names, val_values)))
                if not multiline:
                    break
            else:
                log.debug('No matches found')
        return result

    def process_tracker_config_rules(self, entry, rules=None):
        """
        Processes an Entry object with the linematched rules defined in a tracker config file
        :param entry: Entry to be updated
        :param rules: Ruleset to use.
        :return:
        """

        ignore_optionals = []

        if rules is None:
            rules = self.tracker_config.find('parseinfo/linematched')

        # Make sure all irc fields from entry are in `fields`
        fields = {key: val for key, val in entry.items() if key.startswith('irc_')}

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
                        if irc_prefix(varname) in fields:
                            value = fields[irc_prefix(varname)]
                        elif self.config.get(varname):
                            value = self.config.get(varname)
                        else:
                            log.error('Missing variable %s from config, skipping rule', varname)
                            break
                        if element.tag == 'varenc':
                            value = urllib.quote(value.encode('utf-8'))
                        result += value
                    else:
                        log.error('Unsupported var operation %s, skipping rule', element.tag)
                        break
                else:
                    # Only set the result if we processed all elements
                    log.debug('Result for rule %s: %s=%s', rule.tag, rule.get('name'), result)
                    fields[irc_prefix(rule.get('name'))] = result

            # Var Replace - replace text in a var
            elif rule.tag == 'varreplace':
                source_var = irc_prefix(rule.get('srcvar'))
                target_var = irc_prefix(rule.get('name'))
                regex = rule.get('regex')
                replace = rule.get('replace')
                if source_var and target_var and regex is not None and replace is not None and source_var in fields:
                    fields[target_var] = re.sub(regex, replace, fields[source_var])
                    log.debug('varreplace: %s=%s', target_var, fields[target_var])
                else:
                    log.error('Invalid varreplace options, skipping rule')

            # Extract - create multiple vars from a single regex
            elif rule.tag == 'extract':
                source_var = irc_prefix(rule.get('srcvar'))
                if source_var not in fields:
                    if rule.get('optional', 'false') == 'false':
                        log.error('Error processing extract rule, non-optional value %s missing!', source_var)
                    ignore_optionals.append(source_var)
                    continue
                if rule.find('regex') is not None:
                    regex = rule.find('regex').get('value')
                else:
                    log.error('Regex option missing on extract rule, skipping rule')
                    continue
                group_names = [irc_prefix(x.get('name')) for x in rule.find('vars') if x.tag == 'var']
                match = re.search(regex, fields[source_var])
                if match:
                    fields.update(dict(zip(group_names, match.groups())))
                else:
                    log.debug('No match found for rule extract')

            # Extract Tag - set a var if a regex matches a tag in a var
            elif rule.tag == 'extracttags':
                source_var = irc_prefix(rule.get('srcvar'))
                split = rule.get('split')
                if source_var in ignore_optionals:
                    continue
                values = [strip_whitespace(x) for x in fields[source_var].split(split)]
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
                                    fields[target_var] = val
                                    found_match = True
                            if not found_match:
                                log.debug('No matches found for regex %s', regex)
                        elif value is not None and new_value is not None:
                            if value in values:
                                fields[target_var] = new_value
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
                        match = re.match(regex, fields.get(source_var, ''))
                        if match:
                            fields.update(dict(zip(vars, match.groups())))
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
                    if source_var in fields and re.match(regex, fields[source_var]):
                        fields[target_var] = target_val
                else:
                    log.error('Option missing on setregex, skipping rule')

            # If statement
            elif rule.tag == 'if':
                source_var = irc_prefix(rule.get('srcvar'))
                regex = rule.get('regex')

                if source_var and regex:
                    if source_var in fields and re.match(regex, fields[source_var]):
                        fields.update(self.process_tracker_config_rules(fields, rule))
                else:
                    log.error('Option missing for if statement, skipping rule')

            else:
                log.warning('Unsupported linematched tag: %s', rule.tag)

        return fields

    def on_privmsg(self, msg):
        """
        Appends messages for the specific channel in the line cache. Schedules a message processing after 1s to
        handle multiline announcements. Might fail since 1s delay is arbitrarily chosen
        :param msg: IRCMessage object
        :return:
        """
        nickname = msg.from_nick
        channel = msg.arguments[0]
        if not irc_bot.is_channel(channel):
            log.debug('Received msg is not a channel msg: %s', msg)
            return
        if channel not in self.line_cache:
            self.line_cache[channel] = {}
        if nickname not in self.line_cache[channel]:
            self.line_cache[channel][nickname] = []
        self.line_cache[channel][nickname].append(msg.arguments[1])
        if len(self.line_cache[channel][nickname]) == 1:
            # Schedule a parse of the message in 1 second (for multilines)
            self.schedule.queue_command(1, partial(self.process_message, nickname, channel))

    def process_message(self, nickname, channel):
        """
        Pops lines from the line cache and passes them to be parsed
        :param nickname: Nickname of who sent hte message
        :param channel: Channel where the message originated from
        :return: None
        """
        lines = u'\n'.join(self.line_cache[channel][nickname])
        self.line_cache[channel][nickname] = []
        log.debug('Received line: %s', lines)
        entry = self.parse_privmsg(nickname, channel, lines)
        if entry:
            log.verbose('IRC message in %s generated an entry: %s', channel, entry)
            self.queue_entry(entry)

    def is_connected(self):
        return self.connected

    def stop(self, wait):
        if self.is_connected() and wait:
            self.inject_before_shutdown = True
        self.quit()


class IRCConnectionManager(object):
    def __init__(self, config):
        self.config = config
        self.shutdown_event = threading.Event()
        self.wait = False
        self.delay = 30
        self.thread = create_thread('irc_manager', self)
        self.thread.start()

    def is_alive(self):
        return self.thread and self.thread.is_alive()

    def start(self):
        """
        Checks for dead threads and attempts to restart them. If the connection appears to be throttled, it won't
        attempt to reconnect for 30s.
        :return:
        """
        global irc_connections
        self.start_connections()

        schedule = {}  # used to keep track of reconnection schedules

        while not self.shutdown_event.is_set():
            for conn_name, conn in irc_connections.items():
                # Don't want to revive if connection was closed cleanly
                if not conn.running:
                    continue

                now = datetime.now()
                # Attempt to revive the thread if it has died. conn.running will be True if it died unexpectedly.
                if not conn and self.config.get(conn_name):
                    try:
                        self.restart_connection(conn_name, self.config[conn_name])
                    except IOError as e:
                        log.error(e)
                elif not conn.is_alive() and conn.running:
                    if conn_name not in schedule:
                        schedule[conn_name] = now + timedelta(seconds=5)
                    # add extra time if throttled
                    if conn.throttled:
                        schedule[conn_name] += timedelta(seconds=self.delay)

                    # is it time yet?
                    if schedule[conn_name] <= now:
                        log.error('IRC connection for %s has died unexpectedly. Restarting it.', conn_name)
                        try:
                            self.restart_connection(conn_name, conn.config)
                        except IOError as e:
                            log.error(e)
                        # remove it from the schedule
                        del schedule[conn_name]

            time.sleep(1)

        self.stop_connections(self.wait)
        irc_connections = {}

    def restart_connections(self):
        for name, connection in irc_connections.items():
            self.restart_connection(name, connection.config)

    def restart_connection(self, name, config=None):
        if not config:
            config = irc_connections[name].config
        if irc_connections[name].is_alive():
            self.stop_connection(name)
        irc_connections[name] = IRCConnection(config, name)
        irc_connections[name].thread.start()

    def start_connections(self):
        """
        Start all the irc connections. Stop the daemon if there are failures.
        :return:
        """

        # First we validate the config for all connections including their .tracker files
        for conn_name, config in self.config.items():
            try:
                log.info('Starting IRC connection for %s', conn_name)
                conn = IRCConnection(config, conn_name)
                irc_connections[conn_name] = conn
                config_hash['names'][conn_name] = get_config_hash(config)
            except (MissingConfigOption, TrackerFileParseError, TrackerFileError, IOError) as e:
                log.error(e)
                if conn_name in irc_connections:
                    del irc_connections[conn_name]  # remove it from the list of connections

        # Now we can start
        for conn_name, connection in irc_connections.items():
            connection.thread.start()

    def stop_connections(self, wait):
        for name in irc_connections.keys():
            self.stop_connection(name, wait)

    def stop_connection(self, name, wait=False):
        if irc_connections[name].is_alive():
            irc_connections[name].stop(wait)
            irc_connections[name].thread.join(11)

    def stop(self, wait):
        self.wait = wait
        self.shutdown_event.set()

    def status_all(self):
        status = {}
        for name in irc_connections.keys():
            status.update(self.status(name))
        return status

    def status(self, name):
        if name not in irc_connections:
            raise ValueError('%s is not a valid irc connection' % name)
        status = {name: {}}
        connection = irc_connections[name]
        status[name]['thread'] = 'alive' if connection.is_alive() else 'dead'
        status[name]['channels'] = connection.channels
        status[name]['connected_channels'] = connection.connected_channels
        status[name]['server'] = (connection.servers[0], connection.port)

        return status

    def update_config(self, config):
        new_irc_connections = {}
        removed_connections = set(self.config.keys()) - set(config.keys())
        for name, conf in config.items():
            hash = get_config_hash(conf)
            if name in self.config and config_hash['names'].get(name) == hash:
                continue
            try:
                new_irc_connections[name] = IRCConnection(conf, name)
                config_hash['names'][name] = hash
            except (MissingConfigOption, TrackerFileParseError, TrackerFileError, IOError) as e:
                log.error('Failed to update config. Error when updating %s: %s', name, e)
                return

        # stop connections that have been removed from config
        for name in removed_connections:
            self.stop_connection(name)
            del irc_connections[name]

        # and (re)start the new ones
        for name, connection in new_irc_connections.items():
            if name in irc_connections:
                self.stop_connection(name)
            irc_connections[name] = connection
            connection.thread.start()

        self.config = config


@event('manager.daemon.started')
def irc_start(manager):
    irc_update_config(manager)


@event('manager.config_updated')
def irc_update_config(manager):
    global irc_manager, config_hash

    # Exit if we're not running daemon mode
    if not manager.is_daemon:
        return

    config = manager.config.get('irc')
    # No config, no connections
    if not config:
        log.debug('No irc connections defined in the config')
        stop_irc(manager)
        return

    if irc_bot is None:
        log.error('ImportError: irc_bot module not found. Shutting down daemon.')
        stop_irc(manager)
        manager.shutdown(finish_queue=False)
        return

    config_hash.setdefault('names', {})
    new_config_hash = get_config_hash(config)

    if config_hash.get('config') == new_config_hash:
        log.verbose('IRC config has not been changed. Not reloading any connections.')
        return
    config_hash['manager'] = new_config_hash

    if irc_manager is not None and irc_manager.is_alive():
        irc_manager.update_config(config)
    else:
        irc_manager = IRCConnectionManager(config)


@event('manager.shutdown_requested')
def shutdown_requested(manager):
    stop_irc(manager, wait=True)


@event('manager.shutdown')
def stop_irc(manager, wait=False):
    if irc_manager is not None and irc_manager.is_alive():
        log.info('Shutting down IRC.')
        irc_manager.stop(wait)
        # this check is necessary for when the irc manager is the one shutting down the daemon
        # a thread can't join itself
        if not threading.current_thread() == irc_manager.thread:
            # It's important to give the threads time to shut down to avoid socket issues later (eg. quick restart)
            irc_manager.thread.join(len(irc_connections.keys()) * 11)


@event('config.register')
def register_plugin():
    register_config_key('irc', schema)
