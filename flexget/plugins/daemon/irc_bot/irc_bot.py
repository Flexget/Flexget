from __future__ import unicode_literals, division, absolute_import
from builtins import *  # pylint: disable=unused-import, redefined-builtin
from future.utils import python_2_unicode_compatible
# -*- coding: utf-8 -*-

import asynchat
import asyncore
import bisect
import datetime
import errno
import functools
import hashlib
import logging
import re
import ssl
import socket
import uuid

from flexget.plugins.daemon.irc_bot.numeric_replies import REPLY_CODES

log = logging.getLogger('irc_bot')


def partial(func, *args, **kwargs):
    """helper function to make sure __name__ is set"""
    f = functools.partial(func, *args, **kwargs)
    functools.update_wrapper(f, func)
    return f


class EventHandler(object):
    def __init__(self, func, command=None, msg=None):
        self.func = func
        self.command = command
        self.msg = msg


def printable_unicode_list(unicode_list):
    return '[{}]'.format(', '.join(str(x) for x in unicode_list))


class QueuedCommand(object):
    def __init__(self, after, scheduled_time, command, persists=False):
        self.after = after
        self.scheduled_time = scheduled_time
        self.command = command
        self.persists = persists

    def __lt__(self, other):
        return self.scheduled_time < other.scheduled_time

    def __eq__(self, other):
        commands_match = self.command.__name__ == other.command.__name__
        if hasattr(self.command, 'args') and hasattr(other.command, 'args'):
            return commands_match and set(self.command.args) == set(other.command.args)
        else:
            return commands_match


class Schedule(object):

    def __init__(self):
        self.queue = []

    def execute(self):
        for queued_cmd in self.queue:
            if datetime.datetime.now() >= queued_cmd.scheduled_time:
                log.debug('Executing scheduled command %s', queued_cmd.command.__name__)
                queued_cmd.command()
                self.queue.pop(0)
                if queued_cmd.persists:
                    self.queue_command(queued_cmd.after, queued_cmd.command, queued_cmd.persists)
            else:
                break

    def queue_command(self, after, cmd, persists=False, unique=True):
        log.debug('Queueing command "%s" to execute in %s second(s)', cmd.__name__, after)
        timestamp = datetime.datetime.now() + datetime.timedelta(seconds=after)
        queued_command = QueuedCommand(after, timestamp, cmd, persists)
        if not unique or queued_command not in self.queue:
            bisect.insort(self.queue, queued_command)


def is_channel(string):
    """
    Return True if input string is a channel
    """
    return string and string[0] in "#&+!"


def strip_irc_colors(data):
    """Strip mirc colors from string. Expects data to be decoded."""
    return re.sub('[\x02\x0F\x16\x1D\x1F]|\x03(\d{1,2}(,\d{1,2})?)?', '', data)


def strip_invisible(data):
    """Strip stupid characters that have been colored 'invisible'. Assumes data has been decoded"""
    stripped_data = ''
    i = 0
    while i < len(data):
        c = data[i]
        if c == '\x03':
            match = re.match('^(\x03(?:(\d{1,2})(?:,(\d{1,2}))(.?)?)?)', data[i:])
            # if the colors match eg. \x031,1a, then "a" has same foreground and background color -> invisible
            if match and match.group(2) == match.group(3):
                if match.group(4) and ord(match.group(4)) > 31:
                    c = match.group(0)[:-1] + ' '
                else:
                    c = match.group(0)
                i += len(c) - 1
        i += 1
        stripped_data += c
    return stripped_data


class IRCBot(asynchat.async_chat):
    ac_in_buffer_size = 8192
    ac_out_buffer_size = 8192

    def __init__(self, config):
        asynchat.async_chat.__init__(self)
        self.server = config['server']
        self.port = config['port']
        self.channels = config['channels']
        self.nickname = config.get('nickname', 'Flexget-%s' % uuid.uuid4())
        self.invite_nickname = config.get('invite_nickname')
        self.invite_message = config.get('invite_message')
        self.nickserv_password = config.get('nickserv_password')
        self.use_ssl = config.get('use_ssl', False)

        self.connected_channels = []
        self.real_nickname = self.nickname
        self.set_terminator(b'\r\n')
        self.create_socket(socket.AF_INET, socket.SOCK_STREAM)
        log.info('Connecting to %s', (self.server, self.port))
        self.connect((self.server, self.port))
        self.buffer = ''
        self.connection_attempts = 1
        self.max_connection_delay = 300  # 5 minutes
        self.throttled = False
        self.schedule = Schedule()
        self.running = True
        self.connecting_to_channels = True
        self.reconnecting = False
        self.event_handlers = {}

        # add event handlers
        self.add_event_handler(self.on_nicknotregistered, 'ERRNICKNOTREGISTERED')
        self.add_event_handler(self.on_inviteonly, 'ERRINVITEONLYCHAN')
        self.add_event_handler(self.on_error, 'ERROR')
        self.add_event_handler(self.on_ping, 'PING')
        self.add_event_handler(self.on_invite, 'INVITE')
        self.add_event_handler(self.on_rplmotdend, ['RPLMOTDEND', 'ERRNOMOTD'])
        self.add_event_handler(self.on_privmsg, 'PRIVMSG')
        self.add_event_handler(self.on_join, 'JOIN')
        self.add_event_handler(self.on_kick, 'KICK')
        self.add_event_handler(self.on_banned, 'ERRBANNEDFROMCHAN')
        self.add_event_handler(self.on_welcome, 'RPLWELCOME')
        self.add_event_handler(self.on_nickinuse, 'ERRNICKNAMEINUSE')
        self.add_event_handler(self.on_nosuchnick, 'ERRNOSUCHNICK')

    def handle_expt_event(self):
        error = self.socket.getsockopt(socket.SOL_SOCKET, socket.SO_ERROR)
        if error == errno.ECONNREFUSED:
            log.error('Connection refused. Check server connection config.')
            self.close()
            return
        elif error == errno.ETIMEDOUT:
            log.error('Connection timed out.')
        self.handle_error()

    def _handshake(self):
        try:
            self.socket.do_handshake(block=True)
        except (ssl.SSLWantReadError, ssl.SSLWantWriteError):
            pass

    def handle_read(self):
        while True:
            try:
                asynchat.async_chat.handle_read(self)
            except (ssl.SSLWantReadError, ssl.SSLWantWriteError):
                self._handshake()
            else:
                break

    def handle_connect(self):
        if self.use_ssl:
            try:
                self.socket.setblocking(True)
                self.socket = ssl.wrap_socket(self.socket)
            except (ssl.SSLWantReadError, ssl.SSLWantWriteError) as e:
                log.debug(e)
                self._handshake()
            except ssl.SSLError as e:
                log.error(e)
                self.exit()
                return
            self.socket.setblocking(False)

        self.reconnecting = False
        log.info('Connected to server %s', self.server)
        self.write('USER %s %s %s :%s' % (self.real_nickname, '8', '*', self.real_nickname))
        self.nick(self.real_nickname)

    def handle_error(self):
        if not self.reconnecting:
            self.reconnecting = True
            delay = min(self.connection_attempts ** 2, self.max_connection_delay)
            log.error('Unknown error occurred. Attempting to restart connection in %s seconds.', delay)
            self.schedule.queue_command(delay, partial(self.reconnect))

    def handle_close(self):
        # only handle close event if we're not actually just shutting down
        if self.running:
            self.handle_error()

    def exit(self):
        log.info('Shutting down connection to %s:%s', self.server, self.port)
        self.running = False
        self.close()

    def reconnect(self):
        self.reconnecting = False
        self.connection_attempts += 1
        self.create_socket(socket.AF_INET, socket.SOCK_STREAM)
        self.connect((self.server, self.port))

    def keepalive(self):
        self.write('PING %s' % self.server)

    def join(self, channels):
        for channel in channels:
            if channel in self.connected_channels:
                continue
            log.info('Joining channel: %s', channel)
            self.write('JOIN %s' % channel)

    def found_terminator(self):
        lines = self._process_message(self.buffer)
        self.buffer = ''
        self.parse_message(lines)

    def collect_incoming_data(self, data):
        """Buffer the data"""
        try:
            data = data.decode('utf-8')
        except UnicodeDecodeError as e:
            log.warning('%s. Will attempt to use latin-1 decoding instead.', e)
            data = data.decode('latin-1')

        self.buffer += strip_irc_colors(strip_invisible(data))

    def _process_message(self, msg):
        messages = []
        for m in msg.split('\r\n'):
            messages.append(IRCMessage(m))
        return messages

    def parse_message(self, lines):
        log.debug('Received: %s', printable_unicode_list(lines))
        for line in lines:
            self.handle_event(line)

    def on_nicknotregistered(self, msg):
        log.error(msg.arguments[2])
        self.quit()

    def on_inviteonly(self, msg):
        self.schedule.queue_command(5, partial(self.join, self.channels))

    def on_error(self, msg):
        log.error('Received error message from %s: %s', self.server, msg.arguments[0])
        if 'throttled' in msg.raw or 'throttling' in msg.raw:
            self.throttled = True

    def on_ping(self, msg):
        self.write('PONG :%s' % msg.arguments[0])

    def on_invite(self, msg):
        if self.nickname == msg.arguments[0] and msg.arguments[1] in self.channels:
            self.join([msg.arguments[1]])

    def on_rplmotdend(self, msg):
        log.debug('Successfully connected to %s', self.server)
        self.identify_with_nickserv()

    def on_privmsg(self, msg):
        if is_channel(msg.arguments[0]):
            log.debug('Public message in channel %s received', msg.arguments[0])
        else:
            log.debug('Private message from %s received', msg.from_nick)
        raise NotImplementedError()

    def on_join(self, msg):
        if msg.from_nick == self.real_nickname:
            log.info('Joined channel %s', msg.arguments[0])
            self.connected_channels.append(msg.arguments[0])
        if not set(self.channels) - set(self.connected_channels):
            self.connecting_to_channels = False

    def on_kick(self, msg):
        if msg.arguments[1] == self.real_nickname:
            log.error('Kicked from channel %s by %s', msg.arguments[0], msg.from_nick)
            self.connected_channels.remove(msg.arguments[0])

    def on_banned(self, msg):
        log.error('Banned from channel %s', msg.arguments[1])
        try:
            self.channels.remove(msg.arguments[1])
        except ValueError:
            pass
    
    def on_welcome(self, msg):
        # Save the nick from server as it may have changed it
        self.real_nickname = msg.arguments[0]
        self.throttled = False
        # Queue the heartbeat
        self.schedule.queue_command(2 * 60, self.keepalive, persists=True)
    
    def on_nickinuse(self, msg):
        if self.real_nickname == msg.arguments[1]:
            self.real_nickname += '_'
            self.write('NICK %s' % self.real_nickname)

    def on_nosuchnick(self, msg):
        log.error('%s: %s', msg.arguments[2], msg.arguments[1])

    def send_privmsg(self, to, msg):
        self.write('PRIVMSG %s :%s' % (to, msg))

    def nick(self, nickname):
        self.write('NICK %s' % nickname)

    def write(self, msg):
        log.debug('SENT: %s', msg)
        unencoded_msg = msg + '\r\n'
        self.send(unencoded_msg.encode())

    def quit(self):
        self.write('QUIT :I\'m outta here!')
        self.exit()

    def start(self):
        while self.running:
            self.schedule.execute()
            asyncore.poll(timeout=1, map={self.socket: self})
            if set(self.channels) - set(self.connected_channels) and not self.connecting_to_channels:
                self.schedule.queue_command(5, partial(self.join, self.channels))

    def identify_with_nickserv(self):
        """
        Identifies the connection with Nickserv, ghosting to recover the nickname if required
        :return:
        """
        if self.nickserv_password:
            # If we've not got our peferred nickname and NickServ is configured, ghost the connection
            if self.nickname != self.real_nickname:
                log.info('Ghosting old connection')
                self.send_privmsg('NickServ', 'GHOST %s %s' % (self.nickname, self.nickserv_password))
                self.nick(self.nickname)

            # Identify with NickServ
            log.info('Identifying with NickServ as %s', self.nickname)
            self.send_privmsg('NickServ', 'IDENTIFY %s' % self.nickserv_password)
        if self.invite_nickname:
            self.schedule.queue_command(5, self.request_channel_invite)
        else:
            self.schedule.queue_command(5, partial(self.join, self.channels))

    def request_channel_invite(self):
        """
        Requests an invite from the configured invite user.
        :return:
        """
        log.info('Requesting an invite to channels %s from %s', self.channels, self.invite_nickname)
        self.send_privmsg(self.invite_nickname, self.invite_message)
        self.schedule.queue_command(5, partial(self.join, self.channels))

    def add_event_handler(self, func, command=None, msg=None):
        if not isinstance(command, list):
            command = [command] if command else []
        if not isinstance(msg, list):
            msg = [msg] if msg else []

        log.debug('Adding event handler %s for (command=%s, msg=%s)', func.__name__, command, msg)
        hash = hashlib.md5('.'.join(sorted(command) + sorted(msg)).encode('utf-8'))
        self.event_handlers[hash] = EventHandler(func, command, msg)

    def handle_event(self, msg):
        """Call the proper function that has been set to handle the input message type eg. RPLMOTD"""
        for regexp, event in self.event_handlers.items():
            if event.command:
                for cmd in event.command:
                    cmd = cmd.rstrip('$') + '$'
                    if re.match(cmd, msg.command, re.IGNORECASE):
                        event.func(msg)
            elif event.msg:
                for m in event.msg:
                    m = m.rstrip('$') + '$'
                    if re.match(m, msg.raw, re.IGNORECASE):
                        event.func(msg)


@python_2_unicode_compatible
class IRCMessage(object):

    def __init__(self, msg):
        rfc_1459 = "^(@(?P<tags>[^ ]*) )?(:(?P<prefix>[^ ]+) +)?(?P<command>[^ ]+)( *(?P<arguments> .+))?"
        msg_contents = re.match(rfc_1459, msg)

        self.raw = msg
        self.tags = msg_contents.group('tags')
        self.prefix = msg_contents.group('prefix')
        self.from_nick = self.prefix.split('!')[0] if self.prefix and '!' in self.prefix else None
        self.command = msg_contents.group('command')
        if self.command.isdigit() and self.command in REPLY_CODES.keys():
            self.command = REPLY_CODES[self.command]
        if msg_contents.group('arguments'):
            args, sep, ext = msg_contents.group('arguments').partition(' :')
            self.arguments = args.split()
            if sep:
                self.arguments.append(ext)
        else:
            self.arguments = []

    def __repr__(self):
        return self.__str__()

    def __str__(self):
        printable_arguments = printable_unicode_list(self.arguments)
        tmpl = (
            "command: {}, "
            "prefix: {}, "
            "tags: {}, "
            "arguments: {}, "
            "from_nick: {}, "
            "raw: {}"
        )
        return tmpl.format(self.command, self.prefix, self.tags, printable_arguments, self.from_nick, self.raw)
