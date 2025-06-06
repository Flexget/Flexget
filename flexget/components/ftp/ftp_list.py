import ftplib
from pathlib import Path

from loguru import logger

from flexget import plugin
from flexget.config_schema import one_or_more
from flexget.entry import Entry
from flexget.event import event
from flexget.plugin import DependencyError, PluginError

try:
    import ftputil
    import ftputil.session
    from ftputil.error import FTPOSError

    imported = True
except ImportError:
    imported = False

logger = logger.bind(name='ftp_list')


class ReuseTLSSessionFTP(ftplib.FTP_TLS):
    """Explicit FTPS, with shared TLS session.

    This is a workaround for https://github.com/python/cpython/issues/63699.
    """

    def ntransfercmd(self, cmd, rest=None):
        """Initiate a transfer using shared TLS session over the data connection."""
        conn, size = ftplib.FTP.ntransfercmd(self, cmd, rest)
        if self._prot_p:
            conn = self.context.wrap_socket(
                conn, server_hostname=self.host, session=self.sock.session
            )
        return conn, size


class FTPList:
    def __init__(self):
        self.username = None
        self.password = None
        self.host = None
        self.port = None
        self.encoding = None
        self.FTP = None

    schema = {
        'type': 'object',
        'properties': {
            'username': {'type': 'string'},
            'password': {'type': 'string'},
            'host': {'type': 'string'},
            'port': {'type': 'integer'},
            'ssl': {'type': 'boolean'},
            'encoding': {'type': 'string'},
            'dirs': one_or_more({'type': 'string'}),
            'recursion': {'type': 'boolean'},
            'recursion_depth': {'type': 'integer'},
            'retrieve': one_or_more(
                {'type': 'string', 'enum': ['files', 'dirs', 'symlinks']}, unique_items=True
            ),
        },
        'required': ['username', 'host'],
    }

    @staticmethod
    def prepare_config(config):
        config.setdefault('retrieve', ['files'])
        config.setdefault('ssl', False)
        config.setdefault('dirs', [''])
        config.setdefault('port', 21)
        config.setdefault('encoding', 'utf-8')
        config.setdefault('recursion', False)
        if not isinstance(config['dirs'], list):
            config['dirs'] = [config['dirs']]
        if not isinstance(config['retrieve'], list):
            config['retrieve'] = [config['retrieve']]
        return config

    def _to_entry(self, path):
        entry = Entry()

        title = self.FTP.path.basename(path)
        location = self.FTP.path.abspath(path)

        entry['title'] = title
        entry['location'] = Path(location)
        entry['url'] = f'ftp://{self.username}:{self.password}@{self.host}:{self.port}/{location}'
        entry['filename'] = title

        logger.debug('adding entry {}', entry)
        if entry.isvalid():
            return entry
        logger.warning('tried to return an illegal entry: {}', entry)
        return None

    def get_content(self, path, recursion, recursion_depth, content_types):
        content_list = []
        with self.FTP as ftp:
            if not ftp.path.isdir(path):
                logger.warning('Directory {} is not a valid dir, skipping', path)
                return []
            if recursion:
                for base, dirs, files in ftp.walk(path):
                    current_depth = base.count('/')
                    if current_depth > recursion_depth != -1:
                        logger.debug(
                            'recursion depth limit of {} reached, continuing', current_depth
                        )
                        continue
                    if 'files' in content_types or 'symlinks' in content_types:
                        for _file in files:
                            content = ftp.path.join(base, _file)
                            if (ftp.path.isfile(content) and 'files' in content_types) or (
                                ftp.path.islink(path) and 'symlinks' in content_types
                            ):
                                logger.debug(
                                    'type match successful for file {}, trying to create entry',
                                    _file,
                                )
                                content_list.append(content)
                    if 'dirs' in content_types or 'symlinks' in content_types:
                        for _dir in dirs:
                            content = ftp.path.join(base, _dir)
                            if (ftp.path.isdir(content) and 'dirs' in content_types) or (
                                ftp.path.islink(path) and 'symlinks' in content_types
                            ):
                                logger.debug(
                                    'type match successful for dir {}, trying to create entry',
                                    _dir,
                                )
                                content_list.append(content)
            else:
                for _object in ftp.listdir(path):
                    content = ftp.path.join('./', path, _object)
                    if (
                        ('files' in content_types and ftp.path.isfile(content))
                        or ('dirs' in content_types and ftp.path.isdir(content))
                        or ('symlinks' in content_types and ftp.path.islink(content))
                    ):
                        logger.debug(
                            'type match successful for object {}, trying to create entry', content
                        )
                        content_list.append(content)
        return content_list

    def on_task_input(self, task, config):
        if not imported:
            raise DependencyError('ftp_list', 'ftp_list', 'ftputil is required for this plugin')
        config = self.prepare_config(config)

        self.username = config.get('username')
        self.password = config.get('password')
        self.host = config.get('host')
        self.port = config.get('port')
        self.encoding = config.get('encoding')

        directories = config.get('dirs')
        recursion = config.get('recursion')
        content_types = config.get('retrieve')
        recursion_depth = -1 if recursion else 0

        base_class = ReuseTLSSessionFTP if config.get('ssl') else ftplib.FTP
        session_factory = ftputil.session.session_factory(
            base_class=base_class, port=self.port, encoding=self.encoding
        )
        logger.verbose(
            'trying to establish connection to FTP: {}:{}@{}:{}',
            self.username,
            self.password,
            self.host,
            self.port,
        )
        try:
            self.FTP = ftputil.FTPHost(
                self.host, self.username, self.password, session_factory=session_factory
            )
        except FTPOSError as e:
            raise PluginError(f'Could not connect to FTP: {e}')

        return [
            self._to_entry(content)
            for d in directories
            for content in self.get_content(d, recursion, recursion_depth, content_types)
        ]


@event('plugin.register')
def register_plugin():
    plugin.register(FTPList, 'ftp_list', api_ver=2)
