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
import socket
import threading
import uuid

from flexget.utils.irc.numeric_replies import REPLY_CODES

log = logging.getLogger('irc_bot')

event_handlers = {}


class EventHandler(object):

    def __init__(self, func, command=None, msg=None):
        self.func = func.__name__
        self.command = command
        self.msg = msg


def event(command=None, msg=None):
    if not isinstance(command, list):
        command = [command] if command else []
    if not isinstance(msg, list):
        msg = [msg] if msg else []

    def decorator(func):
        log.debug('Adding event handler %s for (command=%s, msg=%s)', func.__name__, command, msg)
        hash = hashlib.md5('.'.join(sorted(command) + sorted(msg)).encode('utf-8'))
        event_handlers[hash] = EventHandler(func, command, msg)
        return func
    return decorator


def handle_event(msg, obj):
    for regexp, _event in event_handlers.items():
        if _event.command:
            for cmd in _event.command:
                cmd = cmd.rstrip('$') + '$'
                if re.match(cmd, msg.command, re.IGNORECASE):
                    if callable(getattr(obj, _event.func)):
                        getattr(obj, _event.func)(msg)
        elif _event.msg:
            for m in _event.msg:
                m = m.rstrip('$') + '$'
                if re.match(m, msg.raw, re.IGNORECASE):
                    if callable(getattr(obj, _event.func)):
                        getattr(obj, _event.func)(msg)


def printable_unicode_list(unicode_list):
    return '[{}]'.format(', '.join(str(x) for x in unicode_list))


class QueuedCommand(object):
    def __init__(self, after, scheduled_time, command, name, persists=False):
        self.name = name
        self.after = after
        self.scheduled_time = scheduled_time
        self.command = command
        self.persists = persists

    def __lt__(self, other):
        return self.scheduled_time < other.scheduled_time

    def __eq__(self, other):
        return self.name == other.name


class Schedule(object):

    def __init__(self):
        self.queue = []

    def execute(self):
        for queued_cmd in self.queue:
            if datetime.datetime.now() >= queued_cmd.scheduled_time:
                log.debug('Executing scheduled command %s', queued_cmd.name)
                queued_cmd.command()
                self.queue.pop(0)
                if queued_cmd.persists:
                    self.queue_command(queued_cmd.after, queued_cmd.command, queued_cmd.name, queued_cmd.persists)
            else:
                break

    def queue_command(self, after, cmd, name, persists=False):
        timestamp = datetime.datetime.now() + datetime.timedelta(seconds=after)
        queued_command = QueuedCommand(after, timestamp, cmd, name, persists)
        if queued_command not in self.queue:
            bisect.insort(self.queue, queued_command)

    def remove(self, name):
        try:
            self.queue.remove(name)
        except ValueError:
            pass


def is_channel(string):
    """
    Return True if input string is a channel
    """
    return string and string[0] in "#&+!"


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

        self.connected_channels = []
        self.autojoin_channels = []
        self.real_nickname = self.nickname
        self.set_terminator(b'\r\n')
        self.create_socket(socket.AF_INET, socket.SOCK_STREAM)
        log.info('Connecting to %s', (self.server, self.port))
        self.connect((self.server, self.port))
        self.buffer = ''
        self.connection_attempts = 0
        self.max_connection_delay = 300  # 5 minutes
        self.throttled = False
        self.schedule = Schedule()

    def handle_expt_event(self):
        error = self.socket.getsockopt(socket.SOL_SOCKET, socket.SO_ERROR)
        if error == errno.ECONNREFUSED:
            log.error('Connection refused. Check server connection config.')
            self.close()
            return
        elif error == errno.ETIMEDOUT:
            log.error('Connection timed out.')
        self.handle_error()

    def handle_connect(self):
        log.info('Connected to server %s', self.server)
        self.write('USER %s %s %s :%s' % (self.real_nickname, '8', '*', self.real_nickname))
        self.nick(self.real_nickname)

    def handle_error(self):
        exc_info = sys.exc_info()
        raise exc_info[0], exc_info[1], exc_info[2]
        delay = min(self.connection_attempts ** 2, self.max_connection_delay)
        log.error('Unknown error occurred. Attempting to restart connection in %s seconds.', delay)
        self.schedule.queue_command(delay, functools.partial(self.reconnect), 'reconnect')

    def handle_close(self):
        # only handle close event if we're not actually just shutting down
        if not self.shutdown_event.is_set():
            self.handle_error()

    def exit(self):
        self.shutdown_event.set()
        self.close()

    def reconnect(self):
        self.connection_attempts += 1
        self.create_socket(socket.AF_INET, socket.SOCK_STREAM)
        self.connect((self.server, self.port))

    def keepalive(self):
        self.write('PING %s' % self.server)

    def join(self, channels):
        for channel in channels:
            log.info('Joining channel: %s', channel)
            self.write('JOIN %s' % channel)

    def found_terminator(self):
        lines = [self._process_message(self.buffer)]
        self.buffer = ''
        self.parse_message(lines)

    def collect_incoming_data(self, data):
        """Buffer the data"""
        self.buffer += data.decode('utf-8')

    def _process_message(self, msg):
        return IRCMessage(msg)

    def parse_message(self, lines):
        log.debug('Received: %s', printable_unicode_list(lines))
        for line in lines:
            handle_event(line, self)

    @event('ERRINVITEONLYCHAN')
    def on_inviteonly(self, msg):
        self.schedule.queue_command(5, functools.partial(self.join, self.channels), 'join')

    @event('ERROR')
    def on_error(self, msg):
        log.error('Received error message from %s: %s', self.server, msg.arguments[0])
        if 'throttled' in msg or 'throttling' in msg:
            self.throttled = True

    @event('PING')
    def on_ping(self, msg):
        self.write('PONG :%s' % msg.arguments[0])

    @event('INVITE')
    def on_invite(self, msg):
        if self.nickname == msg.arguments[0]:
            self.join([msg.arguments[1]])

    @event(['RPLMOTDEND', 'ERRNOMOTD'])
    def on_rplmotdend(self, msg):
        log.debug('Successfully connected to %s', self.server)
        self.identify_with_nickserv()

    @event('PRIVMSG')
    def on_privmsg(self, msg):
        if is_channel(msg.arguments[0]):
            log.debug('Public message in channel %s received', msg.arguments[0])
        else:
            log.debug('Private message from %s received', msg.from_nick)
        raise NotImplementedError()

    @event('JOIN')
    def on_join(self, msg):
        if msg.from_nick == self.real_nickname:
            log.info('Joined channel %s', msg.arguments[0])
            self.connected_channels.append(msg.arguments[0])
            self.autojoin_channels.append(msg.arguments[0])

    @event('KICK')
    def on_kick(self, msg):
        if msg.arguments[1] == self.real_nickname:
            log.error('Kicked from channel %s by %s', msg.arguments[0], msg.from_nick)
            self.connected_channels.remove(msg.arguments[0])

    @event('ERRBANNEDFROMCHAN')
    def on_banned(self, msg):
        log.error('Banned from channel %s', msg.arguments[1])
        try:
            self.channels.remove(msg.arguments[1])
            self.autojoin_channels.remove(msg.arguments[1])
        except ValueError:
            pass
    
    @event('RPLWELCOME')
    def on_welcome(self, msg):
        # Save the nick from server as it may have changed it
        self.real_nickname = msg.arguments[0]
        self.throttled = False
        # Queue the heartbeat
        self.schedule.queue_command(2 * 60, self.keepalive, 'keepalive', persists=True)
    
    @event('ERRNICKNAMEINUSE')
    def on_nickinuse(self, msg):
        if self.real_nickname == msg.arguments[1]:
            self.real_nickname += '_'
            self.write('NICK %s' % self.real_nickname)

    @event('ERRNOSUCHNICK')
    def on_nosuchnick(self, msg):
        log.error('%s: %s', msg.arguments[2], msg.arguments[1])

    def send_privmsg(self, to, msg):
        self.write('PRIVMSG %s :%s' % (to, msg))

    def nick(self, nickname):
        self.write('NICK %s' % nickname)

    def write(self, msg):
        log.debug('SENT: %s', msg)
        self.send(msg + '\r\n')

    def quit(self):
        self.write('QUIT :I\'m outta here!')
        self.exit()

    def start(self):
        self.shutdown_event = threading.Event()
        while not self.shutdown_event.is_set():
            self.schedule.execute()
            asyncore.poll(timeout=1, map={self.socket: self})
            self.reconnect_channels()

    def reconnect_channels(self):
        disconnected_channels = list(set(self.autojoin_channels) - set(self.connected_channels))
        if disconnected_channels:
            self.schedule.queue_command(5, functools.partial(self.join, disconnected_channels), 'join')

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
            self.schedule.queue_command(5, self.request_channel_invite, 'request_channel_invite')
        else:
            self.schedule.queue_command(5, functools.partial(self.join, self.channels), 'join')

    def request_channel_invite(self):
        """
        Requests an invite from the configured invite user.
        :return:
        """
        log.info('Requesting an invite to channels %s from %s', self.channels, self.invite_nickname)
        self.send_privmsg(self.invite_nickname, self.invite_message)
        self.schedule.queue_command(5, functools.partial(self.join, self.channels), 'join')


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
