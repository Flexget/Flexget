import contextlib
import os
import re
import threading
import time
from datetime import datetime, timedelta
from urllib.parse import quote
from uuid import uuid4
from xml.etree.ElementTree import parse

from loguru import logger

from flexget.config_schema import one_or_more, register_config_key
from flexget.entry import Entry
from flexget.event import event
from flexget.manager import manager
from flexget.utils import requests
from flexget.utils.tools import get_config_hash

try:
    from irc_bot import utils as irc_bot
    from irc_bot.simple_irc_bot import SimpleIRCBot, partial
except ImportError:
    irc_bot = None
    SimpleIRCBot = object

logger = logger.bind(name='irc')

MESSAGE_CLEAN = re.compile(r'\x0f|\x1f|\x02|\x03(?:[\d]{1,2}(?:,[\d]{1,2})?)?', re.MULTILINE)
URL_MATCHER = re.compile(r'(https?://[\da-z\.-]+\.[a-z\.]{2,6}[/\w\.-\?&]*/?)', re.MULTILINE)

channel_pattern = {
    'type': 'string',
    'pattern': r'^([#&][^\x07\x2C\s]{0,200})',
    'error_pattern': 'channel name must start with # or & and contain no commas and whitespace',
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
                    'password': {'type': 'string'},
                    'channels': one_or_more(channel_pattern),
                    'nickserv_password': {'type': 'string'},
                    'invite_nickname': {'type': 'string'},
                    'invite_message': {'type': 'string'},
                    'task': one_or_more({'type': 'string'}),
                    'task_re': {
                        'type': 'array',
                        'items': {
                            'type': 'object',
                            'properties': {
                                'task': {'type': 'string'},
                                'patterns': {
                                    'type': 'array',
                                    'items': {
                                        'type': 'object',
                                        'properties': {
                                            'regexp': {'type': 'string', 'format': 'regex'},
                                            'field': {'type': 'string'},
                                        },
                                        'required': ['regexp', 'field'],
                                        'additionalProperties': False,
                                    },
                                },
                            },
                            'required': ['task', 'patterns'],
                            'additionalProperties': False,
                        },
                    },
                    'queue_size': {'type': 'integer', 'default': 1},
                    'use_ssl': {'type': 'boolean', 'default': False},
                    'task_delay': {'type': 'integer'},
                },
                'allOf': [
                    {
                        'anyOf': [
                            {'required': ['server', 'channels']},
                            {'required': ['tracker_file']},
                        ],
                        'error': 'Must specify a tracker file or server and channel(s)',
                    },
                    {
                        'anyOf': [{'required': ['task']}, {'required': ['task_re']}],
                        'error': 'Must specify a task',
                    },
                ],
                'required': ['port'],
                'additionalProperties': {'type': 'string'},
            },
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
    """Create a new thread and start it.

    :param conn: IRCConnection or IRCConnectionManager object
    :return: Thread
    """
    thread = threading.Thread(target=conn.start, name=name)
    thread.setDaemon(True)
    return thread


def irc_prefix(var):
    """Prefix a string with ``irc_``.

    :param var: Variable to prefix
    :return: Prefixed variable
    """
    if isinstance(var, str):
        return f'irc_{var.lower()}'
    return None


def strip_whitespace(value):
    """Remove leading and trailing whitespace from strings. Return value if not a string.

    :param value:
    :return: stripped string or value
    """
    if isinstance(value, str):
        return value.strip()
    return value


class TrackerFileParseError(Exception):
    """Exception thrown when parsing the tracker file fails."""


class TrackerFileError(Exception):
    """Exception thrown when parsing the tracker file fails."""


class MissingConfigOption(Exception):
    """Exception thrown when a config option specified in the tracker file is not on the irc config."""


class IRCConnection(SimpleIRCBot):
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
                value_name = param.get('name') if param.tag == 'textbox' else param.tag

                # Strip the gazelle prefix
                if value_name.startswith('gazelle_'):
                    value_name = value_name.replace('gazelle_', '')

                # Skip descriptions
                if 'description' in value_name:
                    continue

                if self.config.get(value_name) is None:
                    raise MissingConfigOption(
                        f'missing configuration option on irc config {self.connection_name}: {value_name}'
                    )

            # Get the tracker name, for use in the connection name
            self.connection_name = self.tracker_config.get('longName', config_name)

            # Extract the IRC server information
            for server in self.tracker_config.find('servers'):
                self.server_list.extend(server.get('serverNames').split(','))
                channel_list.extend(server.get('channelNames').split(','))
                self.announcer_list.extend(server.get('announcerNames').split(','))

            # Process ignore lines
            for regex_values in self.tracker_config.findall('parseinfo/ignore/regex'):
                rx = re.compile(regex_values.get('value'), re.MULTILINE)
                self.ignore_lines.append((rx, regex_values.get('expected') != 'false'))

            # Parse patterns
            self.multilinepatterns = self.parse_patterns(
                list(self.tracker_config.findall('parseinfo/multilinepatterns/extract'))
            )
            self.linepatterns = self.parse_patterns(
                list(self.tracker_config.findall('parseinfo/linepatterns/extract'))
            )

        # overwrite tracker config with flexget config
        if self.config.get('server'):
            self.server_list = [self.config['server']]
            logger.debug('Using server specified from config')
        channels = config.get('channels')
        if channels:
            channel_list = channels if isinstance(channels, list) else [channels]
            logger.debug('Using channel(s) specified from config')

        logger.debug('Servers: {}', self.server_list)
        logger.debug('Channels: {}', channel_list)
        logger.debug('Announcers: {}', self.announcer_list)
        logger.debug('Ignore Lines: {}', len(self.ignore_lines))
        logger.debug('Message Regexs: {}', len(self.multilinepatterns) + len(self.linepatterns))
        for rx, vals, optional in self.multilinepatterns:
            msg = '    Multilinepattern "{}" extracts {}'
            if optional:
                msg += ' (optional)'
            logger.debug(msg, rx.pattern, vals)
        for rx, vals, optional in self.linepatterns:
            msg = '    Linepattern "{}" extracts {}'
            if optional:
                msg += ' (optional)'
            logger.debug(msg, rx.pattern, vals)

        # Init the IRC Bot
        ircbot_config = {
            'servers': self.server_list,
            'port': config['port'],
            'channels': channel_list,
            'nickname': config.get('nickname', f'Flexget-{uuid4()!s}'),
            'password': config.get('password'),
            'invite_nickname': config.get('invite_nickname'),
            'invite_message': config.get('invite_message'),
            'nickserv_password': config.get('nickserv_password'),
            'use_ssl': config.get('use_ssl'),
        }
        SimpleIRCBot.__init__(self, ircbot_config)

        self.inject_before_shutdown = False
        self.entry_queue = []
        self.line_cache = {}
        self.processing_message = (
            False  # if set to True, it means there's a message processing queued
        )
        self.thread = create_thread(self.connection_name, self)

    @classmethod
    def read_tracker_config(cls, path):
        """Attempt to open and parse the .tracker file specified in path.

        :param path: path to .tracker file
        :return: the parsed XML
        """
        try:
            with open(path, 'rb') as xml_file:
                return parse(xml_file).getroot()
        except Exception as e:
            raise TrackerFileParseError(f'Unable to parse tracker config file {path}: {e}')

    @classmethod
    def retrieve_tracker_config(cls, tracker_config_file):
        """Attempt to retrieve the .tracker file from disk or github. Return the parsed XML.

        :param tracker_config_file: URL or path to .tracker file
        :return: parsed XML
        """
        base_url = (
            'https://raw.githubusercontent.com/autodl-community/autodl-trackers/master/trackers/'
        )
        tracker_config_file = os.path.expanduser(tracker_config_file)

        # First we attempt to find the file locally as-is
        if os.path.exists(tracker_config_file):
            logger.debug('Found tracker file: {}', tracker_config_file)
            return cls.read_tracker_config(tracker_config_file)

        if not tracker_config_file.endswith('.tracker'):
            tracker_config_file += '.tracker'

            # Maybe the file is missing extension?
            if os.path.exists(tracker_config_file):
                logger.debug('Found tracker file: {}', tracker_config_file)
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
                    logger.debug('Found tracker file: {}', found_path)
                    return cls.read_tracker_config(found_path)

        # Download from Github instead
        if not os.path.exists(base_dir):  # will only try to create the default `trackers` dir
            try:
                os.mkdir(base_dir)
            except OSError as e:
                raise TrackerFileError(e)
        logger.info(
            'Tracker file not found on disk. Attempting to fetch tracker config file from Github.'
        )
        tracker = None
        with contextlib.suppress(requests.RequestException, OSError):
            tracker = requests.get(base_url + tracker_config_file)
        if not tracker:
            try:
                logger.debug('Trying to search list of tracker files on Github')
                # Try to see if it's not found due to case sensitivity
                trackers = (
                    requests.get(
                        'https://api.github.com/repos/autodl-community/'
                        'autodl-trackers/git/trees/master?recursive=1'
                    )
                    .json()
                    .get('tree', [])
                )
                for t in trackers:
                    name = t.get('path', '')
                    if (
                        not name.endswith('.tracker')
                        or name.lower() != 'trackers/' + tracker_name.lower()
                    ):
                        continue
                    tracker = requests.get(base_url + name)
                    tracker_name = name
                    break
            except (requests.RequestException, OSError) as e:
                raise TrackerFileError(e)
        if not tracker:
            raise TrackerFileError(
                f'Unable to find {tracker_config_file} on disk or Github. Did you spell it correctly?'
            )

        # If we got this far, let's save our work :)
        save_path = os.path.join(base_dir, tracker_name)
        with open(save_path, 'wb') as tracker_file:
            tracker_file.writelines(tracker.iter_content(8192))
        return cls.read_tracker_config(save_path)

    def is_alive(self):
        return self.thread and self.thread.is_alive()

    def parse_patterns(self, patterns):
        """Parse the patterns and create a tuple with the compiled regex pattern and the variables it produces.

        :param patterns: list of regex patterns as .tracker XML
        :return: list of (regex, variables, optional)-pairs
        """
        result = []
        for pattern in patterns:
            rx = re.compile(pattern.find('regex').get('value'), re.MULTILINE)
            vals = [var.get('name') for idx, var in enumerate(pattern.find('vars'))]
            optional = pattern.get('optional', 'false').lower() == 'true'
            result.append((rx, vals, optional))
        return result

    def quit(self):
        """Quit the IRC bot.

        :return:
        """
        if self.inject_before_shutdown and self.entry_queue:
            self.run_tasks()
        SimpleIRCBot.quit(self)

    def run_tasks(self):
        """Pass entries to the target task(s) configured for this connection.

        :return:
        """
        tasks = self.config.get('task')
        tasks_re = self.config.get('task_re')
        if tasks:
            if isinstance(tasks, str):
                tasks = [tasks]
            logger.debug(
                'Injecting {} entries into tasks {}', len(self.entry_queue), ', '.join(tasks)
            )
            options = {
                'tasks': tasks,
                'cron': True,
                'inject': self.entry_queue,
                'allow_manual': True,
            }
            manager.execute(options=options, priority=5, suppress_warnings=['input'])

        if tasks_re:
            tasks_entry_map = {}
            for entry in self.entry_queue:
                matched = False
                for task_config in tasks_re:
                    pattern_match = 0
                    for pattern in task_config.get('patterns'):
                        if re.search(
                            pattern['regexp'], entry.get(pattern['field'], ''), re.IGNORECASE
                        ):
                            pattern_match += 1

                    # the entry is added to the task map if all of the defined regex matched
                    if len(task_config.get('patterns')) == pattern_match:
                        matched = True
                        if not tasks_entry_map.get(task_config.get('task')):
                            tasks_entry_map[task_config.get('task')] = []
                        tasks_entry_map[task_config.get('task')].append(entry)

                if not matched:
                    logger.debug('Entry "{}" did not match any task regexp.', entry['title'])

            for task, entries in tasks_entry_map.items():
                logger.debug('Injecting {} entries into task "{}"', len(entries), task)
                options = {'tasks': [task], 'cron': True, 'inject': entries, 'allow_manual': True}
                manager.execute(options=options, priority=5, suppress_warnings=['input'])

        self.entry_queue = []

    def queue_entry(self, entry):
        """Store an entry in the connection entry queue, if the queue is over the size limit then submit them.

        :param entry: Entry to be queued
        :return:
        """
        self.entry_queue.append(entry)
        logger.debug('Entry: {}', entry)
        if len(self.entry_queue) >= self.config['queue_size']:
            if self.config.get('task_delay'):
                self.schedule.queue_command(
                    self.config['task_delay'], self.run_tasks, unique=False
                )
            else:
                self.run_tasks()

    def match_message_patterns(self, patterns, msg):
        """Try to match the message to the list of patterns. Support multiline messages.

        :param patterns: list of (regex, variable)-pairs
        :param msg: The parsed IRC message
        :param multiline: True if msg is multiline
        :return: A dict of the variables and their extracted values
        """
        result = {}
        for rx, vals, _ in patterns:
            logger.debug('Using pattern {} to parse message vars', rx.pattern)
            match = rx.search(msg)
            if match:
                val_names = [irc_prefix(val.lower()) for val in vals]
                val_values = [strip_whitespace(x) or '' for x in match.groups()]
                result.update(dict(zip(val_names, val_values, strict=False)))
                logger.debug('Found: {}', dict(zip(val_names, val_values, strict=False)))
                break
            logger.debug('No matches found for {} in {}', rx.pattern, msg)
        return result

    def process_tracker_config_rules(self, entry, rules=None):
        """Process an Entry object with the linematched rules defined in a tracker config file.

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
            logger.debug('Processing rule {}', rule.tag)

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
                            logger.error(
                                'Missing variable {} from config, skipping rule',
                                irc_prefix(varname),
                            )
                            break
                        if element.tag == 'varenc':
                            value = quote(value.encode('utf-8'))
                        result += value
                    else:
                        logger.error('Unsupported var operation {}, skipping rule', element.tag)
                        break
                else:
                    # Only set the result if we processed all elements
                    logger.debug('Result for rule {}: {}={}', rule.tag, rule.get('name'), result)
                    fields[irc_prefix(rule.get('name'))] = result

            # Var Replace - replace text in a var
            elif rule.tag == 'varreplace':
                source_var = irc_prefix(rule.get('srcvar'))
                target_var = irc_prefix(rule.get('name'))
                regex = rule.get('regex')
                replace = rule.get('replace')
                if (
                    source_var
                    and target_var
                    and regex is not None
                    and replace is not None
                    and source_var in fields
                ):
                    fields[target_var] = re.sub(regex, replace, fields[source_var])
                    logger.debug('varreplace: {}={}', target_var, fields[target_var])
                else:
                    logger.error('Invalid varreplace options, skipping rule')

            # Extract - create multiple vars from a single regex
            elif rule.tag == 'extract':
                source_var = irc_prefix(rule.get('srcvar'))
                if source_var not in fields:
                    if rule.get('optional', 'false') == 'false':
                        logger.error(
                            'Error processing extract rule, non-optional value {} missing!',
                            source_var,
                        )
                    ignore_optionals.append(source_var)
                    continue
                if rule.find('regex') is not None:
                    regex = rule.find('regex').get('value')
                else:
                    logger.error('Regex option missing on extract rule, skipping rule')
                    continue
                group_names = [
                    irc_prefix(x.get('name')) for x in rule.find('vars') if x.tag == 'var'
                ]
                match = re.search(regex, fields[source_var])
                if match:
                    fields.update(dict(zip(group_names, match.groups(), strict=False)))
                else:
                    logger.debug('No match found for rule extract')

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
                                logger.debug('No matches found for regex {}', regex)
                        elif value is not None and new_value is not None:
                            if value in values:
                                fields[target_var] = new_value
                            else:
                                logger.debug(
                                    'No match found for value {} in {}', value, source_var
                                )
                        else:
                            logger.error(
                                'Missing regex/value/newValue for setvarif command, ignoring'
                            )

            # Extract One - extract one var from a list of regexes
            elif rule.tag == 'extractone':
                for element in rule:
                    if element.tag == 'extract':
                        source_var = irc_prefix(element.get('srcvar'))
                        if element.find('regex') is not None:
                            regex = element.find('regex').get('value')
                        else:
                            logger.error('Regex option missing on extract rule, skipping.')
                            continue
                        if element.find('vars') is not None:
                            vars = [irc_prefix(var.get('name')) for var in element.find('vars')]
                        else:
                            logger.error('No variable bindings found in extract rule, skipping.')
                            continue
                        match = re.match(regex, fields.get(source_var, ''))
                        if match:
                            fields.update(dict(zip(vars, match.groups(), strict=False)))
                        else:
                            logger.debug('No match for extract with regex: {}', regex)
                    else:
                        logger.error('Unsupported extractone tag: {}', element.tag)

            # Set Regex - set a var if a regex matches
            elif rule.tag == 'setregex':
                source_var = irc_prefix(rule.get('srcvar'))
                regex = rule.get('regex')
                target_var = irc_prefix(rule.get('varName'))
                target_val = rule.get('newValue')
                if source_var and regex and target_var and target_val:
                    if source_var in fields and re.search(regex, fields[source_var]):
                        fields[target_var] = target_val
                else:
                    logger.error('Option missing on setregex, skipping rule')

            # If statement
            elif rule.tag == 'if':
                source_var = irc_prefix(rule.get('srcvar'))
                regex = rule.get('regex')

                if source_var and regex:
                    if source_var in fields and re.match(regex, fields[source_var]):
                        fields.update(self.process_tracker_config_rules(fields, rule))
                else:
                    logger.error('Option missing for if statement, skipping rule')

            else:
                logger.warning('Unsupported linematched tag: {}', rule.tag)

        return fields

    def on_privmsg(self, msg):
        """Append messages for the specific channel in the line cache.

        Schedule a message processing after 1s to handle multiline announcements.
        :param msg: IRCMessage object
        :return:
        """
        nickname = msg.from_nick
        channel = msg.arguments[0]
        if not irc_bot.is_channel(channel):
            logger.debug('Received msg is not a channel msg: {}', msg)
            return
        # set some defaults
        self.line_cache.setdefault(channel, {})
        self.line_cache[channel].setdefault(nickname, [])

        self.line_cache[channel][nickname].append(msg.arguments[1])
        if not self.processing_message:
            # Schedule a parse of the message in 1 second (for multilines)
            self.schedule.queue_command(1, partial(self.process_message, nickname, channel))
            self.processing_message = True

    def process_message(self, nickname, channel):
        """Pop lines from the line cache and pass them to be parsed.

        :param str nickname: Nickname of who sent the message
        :param str channel: Channel where the message originated from
        :return: None
        """
        # If we have announcers defined, ignore any messages not from them
        if self.announcer_list and nickname not in self.announcer_list:
            logger.debug('Ignoring message: from non-announcer {}', nickname)
            self.processing_message = False
            return

        # Clean up the messages
        lines = [MESSAGE_CLEAN.sub('', line) for line in self.line_cache[channel][nickname]]

        logger.debug('Received line(s): {}', '\n'.join(lines))

        # Generate some entries
        if self.linepatterns:
            entries = self.entries_from_linepatterns(lines)
        elif self.multilinepatterns:
            entries, lines = self.entries_from_multilinepatterns(lines)
        else:
            entries = self.entries_from_lines(lines)

        for entry in entries:
            # Process the generated entry through the linematched rules
            if self.tracker_config is not None and entry:
                entry.update(self.process_tracker_config_rules(entry))
            elif self.tracker_config is not None:
                logger.error('Failed to parse message(s).')
                self.processing_message = False
                return

            entry['title'] = entry.get('irc_torrentname')

            entry['url'] = entry.get('irc_torrenturl')

            logger.debug('Entry after processing: {}', dict(entry))
            if not entry['url'] or not entry['title']:
                logger.error(
                    'Parsing message failed. Title={}, url={}.', entry['title'], entry['url']
                )
                continue

            logger.verbose('IRC message in {} generated an entry: {}', channel, entry)
            self.queue_entry(entry)

        # reset the line cache
        if self.multilinepatterns and lines:
            self.line_cache[channel][nickname] = lines
            logger.debug('Left over lines: {}', '\n'.join(lines))
        else:
            self.line_cache[channel][nickname] = []

        self.processing_message = False

    def entries_from_linepatterns(self, lines) -> list:
        """Return list of entries generated from lines.

        :param lines: list of lines from irc
        """
        entries = []
        for line in lines:
            # If it's listed in ignore lines, skip it
            ignore = False
            for rx, expected in self.ignore_lines:
                if rx.match(line) and expected:
                    logger.debug('Ignoring message: matched ignore line')
                    ignore = True
                    break
            if ignore:
                continue

            entry = Entry(irc_raw_message=line)

            match = self.match_message_patterns(self.linepatterns, line)

            # Generate the entry and process it through the linematched rules
            if not match:
                logger.error('Failed to parse message. Skipping: {}', line)
                continue

            entry.update(match)

            entries.append(entry)

        return entries

    def entries_from_multilinepatterns(self, lines) -> list:
        """Return list of entries generated from lines.

        :param lines: list of lines
        """
        entries = []
        rest = []  # contains the rest of the lines
        while len(lines) > 0:
            entry = Entry()
            raw_message = ''
            matched_lines = []
            for idx, (rx, vals, optional) in enumerate(self.multilinepatterns):
                logger.debug('Using pattern {} to parse message vars', rx.pattern)
                # find the next candidate line
                line = ''
                for candidate in list(lines):
                    # skip ignored lines
                    for ignore_rx, expected in self.ignore_lines:
                        if ignore_rx.match(candidate) and expected:
                            logger.debug('Ignoring message: matched ignore line')
                            lines.remove(candidate)
                            break
                    else:
                        line = candidate
                        break

                raw_message += '\n' + line
                match = self.match_message_patterns([(rx, vals, optional)], line)
                if match:
                    entry.update(match)
                    matched_lines.append(line)
                    lines.remove(line)
                elif optional:
                    logger.debug('No match for optional extract pattern found.')
                elif not line:
                    rest = matched_lines + lines
                    break
                elif (
                    idx == 0
                ):  # if it's the first regex that fails, then it's probably just garbage
                    logger.error('No matches found for pattern {}', rx.pattern)
                    lines.remove(line)
                    rest = lines
                    break
                else:
                    logger.error('No matches found for pattern {}', rx.pattern)
                    rest = lines
                    break

            else:
                entry['irc_raw_message'] = raw_message

                entries.append(entry)
                continue

        return entries, rest

    def entries_from_lines(self, lines) -> list:
        """Return list of entries generated from lines.

        :param lines: list of lines
        """
        entries = []
        for line in lines:
            entry = Entry(irc_raw_message=line)

            # Use the message as title
            entry['title'] = line

            # find a url...
            url_match = URL_MATCHER.findall(line)
            if url_match:
                # We have a URL(s)!, generate an entry
                urls = list(url_match)
                url = urls[-1]
                entry.update({'urls': urls, 'url': url})

            if not entry.get('url'):
                logger.error('Parsing message failed. No url found.')
                continue

            entries.append(entry)

        return entries

    def is_connected(self):
        return self.connected

    def stop(self, wait):
        if self.is_connected() and wait:
            self.inject_before_shutdown = True
        self.quit()


class IRCConnectionManager:
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
        """Check for dead threads and attempt to restart them.

        If the connection appears to be throttled, it won't attempt to reconnect for 30s.
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
                    except OSError as e:
                        logger.error(e)
                elif not conn.is_alive() and conn.running:
                    if conn_name not in schedule:
                        schedule[conn_name] = now + timedelta(seconds=5)
                    # add extra time if throttled
                    if conn.throttled:
                        schedule[conn_name] += timedelta(seconds=self.delay)

                    # is it time yet?
                    if schedule[conn_name] <= now:
                        logger.error(
                            'IRC connection for {} has died unexpectedly. Restarting it.',
                            conn_name,
                        )
                        try:
                            self.restart_connection(conn_name, conn.config)
                        except OSError as e:
                            logger.error(e)
                        # remove it from the schedule
                        del schedule[conn_name]

            time.sleep(1)

        self.stop_connections(self.wait)
        irc_connections = {}

    def restart_connections(self, name=None):
        if name:
            self.restart_connection(name)
        else:
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
        """Start all the irc connections. Stop the daemon if there are failures.

        :return:
        """
        # First we validate the config for all connections including their .tracker files
        for conn_name, config in self.config.items():
            try:
                logger.info('Starting IRC connection for {}', conn_name)
                conn = IRCConnection(config, conn_name)
                irc_connections[conn_name] = conn
                config_hash['names'][conn_name] = get_config_hash(config)
            except (MissingConfigOption, TrackerFileParseError, TrackerFileError, OSError) as e:
                logger.error(e)
                irc_connections.pop(conn_name, None)  # remove it from the list of connections

        # Now we can start
        for connection in irc_connections.values():
            connection.thread.start()

    def stop_connections(self, wait, name=None):
        if name:
            self.stop_connection(name, wait)
        else:
            for name in irc_connections:
                self.stop_connection(name, wait)

    def stop_connection(self, name, wait=False):
        if irc_connections[name].is_alive():
            irc_connections[name].stop(wait)
            irc_connections[name].thread.join(11)

    def stop(self, wait):
        self.wait = wait
        self.shutdown_event.set()

    def status(self, name=None):
        if name:
            if name not in irc_connections:
                raise ValueError(f'{name} is not a valid irc connection')
            status = [self.status_dict(name)]
        else:
            status = [self.status_dict(n) for n in irc_connections]
        return status

    def status_dict(self, name):
        status = {name: {}}
        connection = irc_connections[name]
        status[name]['alive'] = connection.is_alive()
        status[name]['channels'] = [{key: value} for key, value in connection.channels.items()]
        status[name]['connected_channels'] = connection.connected_channels
        status[name]['server'] = connection.servers[0]
        status[name]['port'] = connection.port

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
            except (MissingConfigOption, TrackerFileParseError, TrackerFileError, OSError) as e:
                logger.error('Failed to update config. Error when updating {}: {}', name, e)
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
    global irc_manager

    # Exit if we're not running daemon mode
    if not manager.is_daemon:
        return

    config = manager.config.get('irc')
    # No config, no connections
    if not config:
        logger.debug('No irc connections defined in the config')
        stop_irc(manager)
        return

    if irc_bot is None:
        logger.error(
            'ImportError: irc_bot module not found or version is too old. Shutting down daemon.'
        )
        stop_irc(manager)
        manager.shutdown(finish_queue=False)
        return

    config_hash.setdefault('names', {})
    new_config_hash = get_config_hash(config)

    if config_hash.get('config') == new_config_hash:
        logger.verbose('IRC config has not been changed. Not reloading any connections.')
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
        logger.info('Shutting down IRC.')
        irc_manager.stop(wait)
        # this check is necessary for when the irc manager is the one shutting down the daemon
        # a thread can't join itself
        if threading.current_thread() != irc_manager.thread:
            # It's important to give the threads time to shut down to avoid socket issues later (eg. quick restart)
            irc_manager.thread.join(len(irc_connections.keys()) * 11)


@event('config.register')
def register_plugin():
    register_config_key('irc', schema)
