import os
import re
import xmlrpc.client
from socket import error as socket_error

from loguru import logger

from flexget import plugin
from flexget.event import event
from flexget.utils.template import RenderError

logger = logger.bind(name='aria2')


class OutputAria2:
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
            'username': {'type': 'string', 'default': ''},  # NOTE: To be deprecated by aria2
            'password': {'type': 'string', 'default': ''},
            'path': {'type': 'string'},
            'filename': {'type': 'string'},
            'add_extension': {
                'oneOf': [
                    {'type': 'string'},
                    {'type': 'boolean'},
                ],
                'default': 'no',
            },
            'options': {
                'type': 'object',
                'additionalProperties': {'oneOf': [{'type': 'string'}, {'type': 'integer'}]},
            },
        },
        'required': ['path'],
        'additionalProperties': False,
    }

    def aria2_connection(self, server, port, username=None, password=None):
        if username and password:
            userpass = '%s:%s@' % (username, password)
        else:
            userpass = ''
        url = 'http://%s%s:%s/rpc' % (userpass, server, port)
        logger.debug('aria2 url: {}', url)
        logger.info('Connecting to daemon at {}', url)
        try:
            return xmlrpc.client.ServerProxy(url).aria2
        except xmlrpc.client.ProtocolError as err:
            raise plugin.PluginError(
                'Could not connect to aria2 at %s. Protocol error %s: %s'
                % (url, err.errcode, err.errmsg),
                logger,
            )
        except xmlrpc.client.Fault as err:
            raise plugin.PluginError(
                'XML-RPC fault: Unable to connect to aria2 daemon at %s: %s'
                % (url, err.faultString),
                logger,
            )
        except socket_error as e:
            raise plugin.PluginError(
                'Socket connection issue with aria2 daemon at %s: %s' % (url, e), logger
            )
        except:
            logger.opt(exception=True).debug('Unexpected error during aria2 connection')
            raise plugin.PluginError(
                'Unidentified error during connection to aria2 daemon', logger
            )

    def prepare_config(self, config):
        config.setdefault('server', 'localhost')
        config.setdefault('port', 6800)
        config.setdefault('username', '')
        config.setdefault('password', '')
        config.setdefault('secret', '')
        config.setdefault('options', {})
        config.setdefault('add_extension', False)
        return config

    def on_task_output(self, task, config):
        # don't add when learning
        if task.options.learn:
            return
        config = self.prepare_config(config)
        aria2 = self.aria2_connection(
            config['server'], config['port'], config['username'], config['password']
        )
        for entry in task.accepted:
            if task.options.test:
                logger.verbose('Would add `{}` to aria2.', entry['title'])
                continue
            try:
                self.add_entry(aria2, entry, config, task)
            except socket_error as se:
                entry.fail('Unable to reach Aria2: %s' % se)
            except xmlrpc.client.Fault as err:
                logger.critical('Fault code {} message {}', err.faultCode, err.faultString)
                entry.fail('Aria2 communication Fault')
            except Exception as e:
                logger.opt(exception=True).debug('Exception type {}', type(e))
                raise

    def add_entry(self, aria2, entry, config, task):
        """
        Add entry to Aria2
        """
        options = config['options']
        try:
            path = entry.get('path', config.get('path', None))
            options['dir'] = os.path.expanduser(entry.render(path).rstrip('/'))
        except RenderError as e:
            entry.fail('failed to render \'path\': %s' % e)
            return

        filename = entry.get('content_filename', config.get('filename', None))
        add_extension = entry.get('content_extension', config.get('add_extension', False))

        if filename:
            if add_extension:
                ext = None
                if isinstance(add_extension, bool):
                    logger.debug('Getting filename from `{}`', entry['url'])
                    content_disposition = None
                    try:
                        with task.requests.get(
                            entry['url'], headers=None, stream=True
                        ) as response:
                            content_disposition = response.headers.get('content-disposition', None)
                    except Exception as e:
                        logger.warning('Not possible to retrive file info from `{}`', entry['url'])
                        entry.fail('Not possible to retrive file info from `%s`' % entry['url'])
                        return

                    if content_disposition:
                        fname_match = re.findall(
                            r'filename=["\']?([^"\']+)["\']?', content_disposition
                        )
                        if fname_match:
                            fname = fname_match[0]
                            fname_info = os.path.splitext(fname)
                            if len(fname_info) == 2:
                                ext = fname_info[1]
                                logger.debug(
                                    'Filename from `{}` is {} with ext `{}`',
                                    entry['url'],
                                    fname,
                                    ext,
                                )

                else:
                    ext = add_extension if add_extension[0] == '.' else '.' + add_extension

                if not ext:
                    logger.warning('Not possible to retrive extension')
                    entry.fail('Not possible to retrive extension')
                    return

                logger.debug('Adding extension `{}` to file `{}`', ext, filename)

                filename += ext

            try:
                options['out'] = os.path.expanduser(entry.render(filename))
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
                return aria2.addTorrent(
                    secret, xmlrpc.client.Binary(open(torrent_file, mode='rb').read()), [], options
                )
            return aria2.addTorrent(
                xmlrpc.client.Binary(open(torrent_file, mode='rb').read()), [], options
            )
        # handle everything else (except metalink -- which is unsupported)
        # so magnets, https, http, ftp .. etc
        if secret:
            return aria2.addUri(secret, [entry['url']], options)
        return aria2.addUri([entry['url']], options)


@event('plugin.register')
def register_plugin():
    plugin.register(OutputAria2, 'aria2', api_ver=2)
