from __future__ import unicode_literals, division, absolute_import
from builtins import *  # noqa pylint: disable=unused-import, redefined-builtin

import logging
import os
import xmlrpc.client
from socket import error as socket_error

from flexget import plugin
from flexget.event import event
from flexget.utils.template import RenderError

log = logging.getLogger('aria2')


class OutputAria2(object):
    """
    Simple Aria2 output

    Example::

        aria2:
          path: ~/downloads/

    """

    schema = {
        'type': 'object',
        'properties': {
            'server': {'type': 'string', 'default': 'localhost'},
            'port': {'type': 'integer', 'default': 6800},
            'secret': {'type': 'string', 'default': ''},
            'username': {'type': 'string', 'default': ''}, # NOTE: To be deprecated by aria2
            'password': {'type': 'string', 'default': ''},
            'path': {'type': 'string'},
            'filename': {'type': 'string'},
            'options': {
                'type': 'object',
                'additionalProperties': {'oneOf': [{'type': 'string'}, {'type': 'integer'}]}
            }

        },
        'required': ['path'],
        'additionalProperties': False
    }

    def aria2_connection(self, server, port, username=None, password=None):
        if username and password:
            userpass = '%s:%s@' % (username, password)
        else:
            userpass = ''
        url = 'http://%s%s:%s/rpc' % (userpass, server, port)
        log.debug('aria2 url: %s' % url)
        log.info('Connecting to daemon at %s', url)
        try:
            return xmlrpc.client.ServerProxy(url).aria2
        except xmlrpc.client.ProtocolError as err:
            raise plugin.PluginError('Could not connect to aria2 at %s. Protocol error %s: %s'
                              % (url, err.errcode, err.errmsg), log)
        except xmlrpc.client.Fault as err:
            raise plugin.PluginError('XML-RPC fault: Unable to connect to aria2 daemon at %s: %s'
                              % (url, err.faultString), log)
        except socket_error as e:
            raise plugin.PluginError('Socket connection issue with aria2 daemon at %s: %s' % (url, e), log)
        except:
            log.debug('Unexpected error during aria2 connection', exc_info=True)
            raise plugin.PluginError('Unidentified error during connection to aria2 daemon', log)

    def prepare_config(self, config):
        config.setdefault('server', 'localhost')
        config.setdefault('port', 6800)
        config.setdefault('username', '')
        config.setdefault('password', '')
        config.setdefault('secret', '')
        config.setdefault('options', {})
        return config

    def on_task_output(self, task, config):
        # don't add when learning
        if task.options.learn:
            return
        config = self.prepare_config(config)
        aria2 = self.aria2_connection(config['server'], config['port'],
                                      config['username'], config['password'])
        for entry in task.accepted:
            if task.options.test:
                log.verbose('Would add `%s` to aria2.', entry['title'])
                continue
            try:
                self.add_entry(aria2, entry, config)
            except socket_error as se:
                entry.fail('Unable to reach Aria2: %s' % se)
            except xmlrpc.client.Fault as err:
                log.critical('Fault code %s message %s', err.faultCode, err.faultString)
                entry.fail('Aria2 communication Fault')
            except Exception as e:
                log.debug('Exception type %s', type(e), exc_info=True)
                raise

    def add_entry(self, aria2, entry, config):
        """
        Add entry to Aria2
        """
        options = config['options']
        try:
            options['dir'] = os.path.expanduser(entry.render(config['path']).rstrip('/'))
        except RenderError as e:
            entry.fail('failed to render \'path\': %s' % e)
            return
        if 'filename' in config:
             try:
                 options['out'] = os.path.expanduser(entry.render(config['filename']))
             except RenderError as e:
                 entry.fail('failed to render \'filename\': %s' % e)
                 return
        secret = None
        if config['secret']:
            secret = 'token:%s' % config['secret']
        # handle torrent files
        if 'torrent' in entry:
            if 'file' in entry:
                torrent_file = entry['file']
            elif 'location' in entry:
                # in case download plugin moved the file elsewhere
                torrent_file = entry['location']
            else:
                entry.fail('Cannot find torrent file')
                return
            if secret:
                return aria2.addTorrent(secret, xmlrpc.client.Binary(open(torrent_file, mode='rb').read()), [], options)
            return aria2.addTorrent(xmlrpc.client.Binary(open(torrent_file, mode='rb').read()), [], options)
        # handle everything else (except metalink -- which is unsupported)
        # so magnets, https, http, ftp .. etc
        if secret:
            return aria2.addUri(secret, [entry['url']], options)
        return aria2.addUri([entry['url']], options)


@event('plugin.register')
def register_plugin():
    plugin.register(OutputAria2, 'aria2', api_ver=2)
