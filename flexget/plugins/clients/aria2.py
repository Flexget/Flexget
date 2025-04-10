import json
import os
import re
import ssl
import xmlrpc.client

import requests
from loguru import logger

from flexget import plugin
from flexget.event import event
from flexget.plugin import PluginError
from flexget.utils.template import RenderError

logger = logger.bind(name='aria2')


class RpcClient:
    def __init__(self, server, port, scheme, rpc_path, username, password, secret):
        if secret:
            self.token = 'token:' + secret
        else:
            self.token = ''
        userpass = f'{username}:{password}@' if username and password else ''
        self.url = f'{scheme}://{userpass}{server}:{port}/{rpc_path}'
        logger.debug('aria2 url: {}', self.url)

    def add_uri(self, uris, options):
        raise plugin.PluginError('Unsupported Operation')

    def add_torrent(self, torrent, options):
        raise plugin.PluginError('Unsupported Operation')


class JsonRpcClient(RpcClient):
    RPC_ID = 'FLEXGET'
    RPC_VERSION = '2.0'

    ADDURI_METHOD = 'aria2.addUri'
    GETGLOBALSTAT_METHOD = 'aria2.getGlobalStat'
    ADDTORRENT_METHOD = 'aria2.addTorrent'
    ADDMETALINK_METHOD = 'aria2.addMetalink'

    def __init__(self, server, port, scheme, rpc_path, username=None, password=None, secret=None):
        super().__init__(server, port, scheme, rpc_path, username, password, secret)
        # trigger _default_error_handle on failure
        self.get_global_stat()

    def _get_req_params(self, method, params=None):
        if params is None:
            params = []
        req_params = {
            'jsonrpc': JsonRpcClient.RPC_VERSION,
            'id': JsonRpcClient.RPC_ID,
            'method': method,
            'params': params,
        }
        if self.token:
            req_params['params'].insert(0, self.token)
        if not req_params['params']:
            del req_params['params']
        return req_params

    @staticmethod
    def _default_error_handle(code, message):
        logger.critical('Fault code {} message {}', code, message)
        raise plugin.PluginError(f'Fault code {code} message {message}', logger)

    @staticmethod
    def _default_success_handle(response):
        return response.text

    def _post(
        self, method, params, on_success=_default_success_handle, on_fail=_default_error_handle
    ):
        resp = requests.post(self.url, data=json.dumps(self._get_req_params(method, params)))
        result = resp.json()
        if 'error' in result:
            return on_fail(result['error']['code'], result['error']['message'])
        return on_success(resp)

    def add_uri(self, uris, options):
        # https://aria2.github.io/manual/en/html/aria2c.html#aria2.addUri
        return self._post(JsonRpcClient.ADDURI_METHOD, params=[[uris], options])

    def add_torrent(self, torrent, options):
        # https://aria2.github.io/manual/en/html/aria2c.html#aria2.addTorrent
        return self._post(JsonRpcClient.ADDTORRENT_METHOD, params=[torrent, options])

    def get_global_stat(self):
        # https://aria2.github.io/manual/en/html/aria2c.html#aria2.getGlobalStat
        return self._post(JsonRpcClient.GETGLOBALSTAT_METHOD, params=[])


class XmlRpcClient(RpcClient):
    def __init__(self, server, port, scheme, rpc_path, username=None, password=None, secret=None):
        schemes = {'http': None, 'https': ssl.SSLContext()}
        if scheme not in schemes:
            raise plugin.PluginError(f'Unknown scheme: {scheme}', logger)
        super().__init__(server, port, scheme, rpc_path, username, password, secret)
        try:
            self._aria2 = xmlrpc.client.ServerProxy(self.url, context=schemes[scheme]).aria2
        except xmlrpc.client.ProtocolError as exc:
            raise plugin.PluginError(
                f'Could not connect to aria2 at {self.url}. Protocol error {exc.errcode}: {exc.errmsg}',
                logger,
            ) from exc
        except xmlrpc.client.Fault as exc:
            raise plugin.PluginError(
                f'XML-RPC fault: Unable to connect to aria2 daemon at {self.url}: {exc.faultString}',
                logger,
            ) from exc
        except OSError as exc:
            raise plugin.PluginError(
                f'Socket connection issue with aria2 daemon at {self.url}: {exc}', logger
            ) from exc
        except Exception as exc:
            logger.opt(exception=True).debug('Unexpected error during aria2 connection')
            raise plugin.PluginError(
                'Unidentified error during connection to aria2 daemon', logger
            ) from exc

    def add_uri(self, uris, options):
        # https://aria2.github.io/manual/en/html/aria2c.html#aria2.addUri
        params = [[uris]]
        if options:
            params.append(options)
        if self.token:
            params.insert(0, self.token)
        return self._aria2.addUri(*params)

    def add_torrent(self, torrent, options):
        # https://aria2.github.io/manual/en/html/aria2c.html#aria2.addTorrent
        params = [torrent]
        if options:
            params.append(options)
        if self.token:
            params.insert(0, self.token)
        return self._aria2.addTorrent(*params)


RPC_CLIENTS = {'xml': XmlRpcClient, 'json': JsonRpcClient}


class OutputAria2:
    """Simple Aria2 output.

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
            # NOTE: To be deprecated by aria2
            'username': {'type': 'string', 'default': ''},
            'password': {'type': 'string', 'default': ''},
            'scheme': {'type': 'string', 'default': 'http'},
            # NOTE: xml/json
            'rpc_mode': {'type': 'string', 'default': 'xml', 'enum': list(RPC_CLIENTS)},
            'rpc_path': {'type': 'string', 'default': 'rpc'},
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
                'additionalProperties': {
                    'oneOf': [{'type': 'string'}, {'type': 'number'}, {'type': 'boolean'}]
                },
            },
        },
        'required': ['path'],
        'additionalProperties': False,
    }

    def prepare_config(self, config):
        config.setdefault('server', 'localhost')
        config.setdefault('port', 6800)
        config.setdefault('username', '')
        config.setdefault('password', '')
        config.setdefault('scheme', 'http')
        config.setdefault('rpc_mode', 'xml')
        config.setdefault('rpc_path', 'rpc')
        config.setdefault('secret', '')
        config.setdefault('options', {})
        config.setdefault('add_extension', False)
        options = config['options']
        for key in options:
            if isinstance(options[key], bool):
                options[key] = str(options[key]).lower()
            elif not isinstance(options[key], str):
                options[key] = str(options[key])
        return config

    def on_task_output(self, task, config):
        # don't add when learning
        if task.options.learn:
            return
        config = self.prepare_config(config)
        if config['rpc_mode'] not in RPC_CLIENTS:
            raise PluginError(f'Unknown rpc_mode: {config["rpc_mode"]}')
        aria2 = RPC_CLIENTS[config['rpc_mode']](
            config['server'],
            config['port'],
            config['scheme'],
            config['rpc_path'],
            config['username'],
            config['password'],
            config['secret'],
        )

        for entry in task.accepted:
            if task.options.test:
                logger.verbose('Would add `{}` to aria2.', entry['title'])
                continue
            try:
                self.add_entry(aria2, entry, config, task)
            except OSError as se:
                entry.fail(f'Unable to reach Aria2: {se}')
            except xmlrpc.client.Fault as err:
                logger.critical('Fault code {} message {}', err.faultCode, err.faultString)
                entry.fail('Aria2 communication Fault')
            except Exception as e:
                logger.opt(exception=True).debug('Exception type {}', type(e))
                raise

    def add_entry(self, aria2: RpcClient, entry, config, task):
        """Add entry to Aria2."""
        options = config['options']
        try:
            path = entry.get('path', config.get('path', None))
            options['dir'] = os.path.expanduser(entry.render(path).rstrip('/'))
        except RenderError as e:
            entry.fail(f"failed to render 'path': {e}")
            return None

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
                    except Exception:
                        logger.warning('Not possible to retrive file info from `{}`', entry['url'])
                        entry.fail(
                            'Not possible to retrive file info from `{}`'.format(entry['url'])
                        )
                        return None

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
                    return None

                logger.debug('Adding extension `{}` to file `{}`', ext, filename)

                filename += ext

            try:
                options['out'] = os.path.expanduser(entry.render(filename))
            except RenderError as e:
                entry.fail(f"failed to render 'filename': {e}")
                return None

        # handle torrent files
        if 'torrent' in entry:
            if 'file' in entry:
                torrent_file = entry['file']
            elif 'location' in entry:
                # in case download plugin moved the file elsewhere
                torrent_file = entry['location']
            else:
                entry.fail('Cannot find torrent file')
                return None
            return aria2.add_torrent(
                xmlrpc.client.Binary(open(torrent_file, mode='rb').read()), options
            )
        # handle everything else (except metalink -- which is unsupported)
        # so magnets, https, http, ftp .. etc
        return aria2.add_uri(entry['url'], options)


@event('plugin.register')
def register_plugin():
    plugin.register(OutputAria2, 'aria2', api_ver=2)
