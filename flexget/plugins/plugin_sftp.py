from __future__ import unicode_literals, division, absolute_import
from urlparse import urljoin, urlparse
from collections import namedtuple
from itertools import groupby
import logging
import os
from functools import partial
import time

from flexget import plugin
from flexget.event import event
from flexget.entry import Entry
from flexget.config_schema import one_or_more
from flexget.utils.template import render_from_entry, RenderError

log = logging.getLogger('sftp')

ConnectionConfig = namedtuple('ConnectionConfig', ['host', 'port', 'username', 'password',
                              'private_key', 'private_key_pass'])

# retry configuration contants
CONNECT_TRIES = 3
RETRY_INTERVAL = 15
RETRY_STEP = 5

# make separate os.path instances for local vs remote path styles
localpath = os.path
remotepath = os.path
remotepath.sep = '/' # pysftp forces *nix style separators

try:
    import pysftp
    logging.getLogger("paramiko").setLevel(logging.ERROR)
except:
    pysftp = None


def sftp_connect(conf):
    """
    Helper function to connect to an sftp server
    """
    sftp = None
    tries = CONNECT_TRIES
    retry_interval = RETRY_INTERVAL

    while not sftp:
        try:
            sftp = pysftp.Connection(host=conf.host, username=conf.username,
                                     private_key=conf.private_key, password=conf.password, 
                                     port=conf.port, private_key_pass=conf.private_key_pass)
            log.debug('Connected to %s' % conf.host)
        except Exception as e:
            if not tries:
                raise e
            else:
                log.debug('Caught exception: %s' % e)
                log.warn('Failed to connect to %s; waiting %d seconds before retrying.' % 
                         (conf.host, retry_interval))
                time.sleep(retry_interval)
                tries -= 1
                retry_interval += RETRY_STEP
    
    return sftp


def dependency_check():
    """
    Check if pysftp module is present
    """
    if not pysftp:
        raise plugin.DependencyError(issued_by='sftp', 
                                     missing='pysftp', 
                                     message='sftp plugin requires the pysftp Python module.')


class SftpList(object):
    """
    Generate entries from SFTP. This plugin requires the pysftp Python module and its dependencies.

    Configuration:

    host:                 Host to connect to
    port:                 Port the remote SSH server is listening on. Defaults to port 22.
    username:             Username to log in as
    password:             The password to use. Optional if a private key is provided.
    private_key:          Path to the private key (if any) to log into the SSH server
    private_key_pass:     Password for the private key (if needed)
    recursive:            Indicates whether the listing should be recursive
    get_size:             Indicates whetern to calculate the size of the remote file/directory.
                          WARNING: This can be very slow when computing the size of directories!
    files_only:           Indicates wheter to omit diredtories from the results.
    dirs:                 List of directories to download

    Example:

      sftp_list:
          host: example.com
          username: Username
          private_key: /Users/username/.ssh/id_rsa
          recursive: False
          get_size: True
          files_only: False
          dirs: 
              - '/path/to/list/'
              - '/another/path/'
    """

    schema = {
        'type': 'object',
        'properties': {
            'host': {'type': 'string'},
            'username': {'type': 'string'},
            'password': {'type': 'string'},
            'port': {'type': 'integer', 'default': 22},
            'files_only': {'type': 'boolean', 'default': True},
            'recursive': {'type': 'boolean', 'default': False},
            'get_size': {'type': 'boolean', 'default': True},
            'private_key': {'type': 'string'},
            'private_key_pass': {'type': 'string'},
            'dirs': one_or_more({'type': 'string'})
        },
        'additionProperties': False,
        'required': ['host', 'username']
    }

    def prepare_config(self, config):
        """
        Sets defaults for the provided configuration
        """
        config.setdefault('port', 22)
        config.setdefault('password', None)
        config.setdefault('private_key', None)
        config.setdefault('private_key_pass', None)
        config.setdefault('dirs', ['.'])    

        return config

    def on_task_input(self, task, config):
        """
        Input task handler
        """

        dependency_check()

        config = self.prepare_config(config)

        host = config['host']
        port = config['port']
        username = config['username']
        password = config['password']
        private_key = config['private_key']
        private_key_pass = config['private_key_pass']
        files_only = config['files_only']
        recursive = config['recursive']
        get_size = config['get_size']
        dirs = config['dirs']
        if not isinstance(dirs, list):
            dirs = [dirs]

        login_str = ''
        port_str = ''
        
        if username and password:
            login_str = '%s:%s@' % (username, password)
        elif username:
            login_str = '%s@' % username

        if port and port != 22:
            port_str = ':%d' % port

        url_prefix = 'sftp://%s%s%s/' % (login_str, host, port_str)
        
        log.debug('Connecting to %s' % host)

        conn_conf = ConnectionConfig(host, port, username, password, private_key, private_key_pass)
        
        try:
            sftp = sftp_connect(conn_conf)
        except Exception as e:
            raise plugin.PluginError('Failed to connect to %s (%s)' % (host, e))

        entries = []

        def file_size(path):
            """
            Helper function to get the size of a node
            """
            return sftp.lstat(path).st_size

        def dir_size(path):
            """
            Walk a directory to get its size
            """
            sizes = []

            def node_size(f): 
                sizes.append(file_size(f))

            sftp.walktree(path, node_size, node_size, node_size, True)
            size = sum(sizes)

            return size

        def handle_node(path, size_handler, is_dir):
            """
            Generic helper function for handling a remote file system node
            """
            if is_dir and files_only:
                return

            url = urljoin(url_prefix, sftp.normalize(path))
            title = remotepath.basename(path)

            entry = Entry(title, url)

            if get_size:
                try:
                    size = size_handler(path)
                except Exception as e:
                    log.error('Failed to get size for %s (%s)' % (path, e))
                    size = -1
                entry['content_size'] = size

            if private_key:
                entry['private_key'] = private_key
                if private_key_pass:
                    entry['private_key_pass'] = private_key_pass

            entries.append(entry)

        # create helper functions to handle files and directories
        handle_file = partial(handle_node, size_handler=file_size, is_dir=False)
        handle_dir = partial(handle_node, size_handler=dir_size, is_dir=True)

        def handle_unknown(path):
            """
            Skip unknown files
            """
            log.warn('Skipping unknown file: %s' % path)

        # the business end
        for dir in dirs:
            try:
                sftp.walktree(dir, handle_file, handle_dir, handle_unknown, recursive)
            except IOError as e:
                log.error('Failed to open %s (%s)' % (dir, e))
                continue

        sftp.close()

        return entries


class SftpDownload(object):
    """
    Download files from a SFTP server. This plugin requires the pysftp Python module and its 
    dependencies.

    Configuration:

    to:                 Destination path; supports Jinja2 templating on the input entry. Fields such
                        as series_name must be populated prior to input into this plugin using
                        metainfo_series or similar.
    recursive:          Indicates wether to download directory contents recursively.
    delete_origin:      Indicates wether to delete the remote files(s) once they've been downloaded.

    Example:

      sftp_download:
          to: '/Volumes/External/Drobo/downloads'
          delete_origin: False
    """

    schema = {
        'type': 'object',
        'properties': {
            'to': {'type': 'string', 'format': 'path'},
            'recursive': {'type': 'boolean', 'default': True},
            'delete_origin': {'type': 'boolean', 'default': False}
        },
        'required': ['to'],
        'additionalProperties': False
    }

    def get_sftp_config(self, entry):
        """
        Parses a url and returns a hashable config, source path, and destination path
        """
        # parse url
        parsed = urlparse(entry['url'])
        host = parsed.hostname
        username = parsed.username or None
        password = parsed.password or None
        port = parsed.port or 22

        # get private key info if it exists
        private_key = entry.get('private_key')
        private_key_pass = entry.get('private_key_pass')

        if parsed.scheme == 'sftp':
            config = ConnectionConfig(host, port, username, password, private_key, private_key_pass)
        else:
            log.warn('Scheme does not match SFTP: %s' % entry['url'])
            config = None

        return config

    def download_file(self, path, dest, sftp, delete_origin):
        """
        Download a file from path to dest
        """
        dir_name = remotepath.dirname(path)
        dest_relpath = localpath.join(*remotepath.split(path)) # convert remote path style to local style
        destination = localpath.join(dest, dest_relpath)
        dest_dir = localpath.dirname(destination)

        if localpath.exists(destination):
            log.verbose('Destination file already exists. Skipping %s' % path)
            return
        
        if not localpath.exists(dest_dir):
            os.makedirs(dest_dir)

        log.verbose('Downloading file %s to %s' % (path, destination))

        try:
            sftp.get(path, destination)
        except Exception as e:
            log.error('Failed to download %s (%s)' % (path, e))
            if remotepath.exists(destination):
                log.debug('Removing partially downloaded file %s' % destination)
                os.remove(destination)
            raise e

        if delete_origin:
            log.debug('Deleting remote file %s' % path)
            try:
                sftp.remove(path)
            except Exception as e:
                log.error('Failed to delete file %s (%s)' % (path, e))
                return

            self.remove_dir(sftp, dir_name)

    def handle_dir(self, path):
        """
        Dummy directory handler. Does nothing.
        """
        pass

    def handle_unknown(self, path):
        """
        Dummy unknown file handler. Warns about unknown files.
        """
        log.warn('Skipping unknown file %s' % path)

    def remove_dir(self, sftp, path):
        """
        Remove a directory if it's empty
        """
        if sftp.exists(path) and not sftp.listdir(path):
            log.debug('Attempting to delete directory %s' % path)
            try:
                sftp.rmdir(path)
            except Exception as e:
                log.error('Failed to delete directory %s (%s)' % (path, e))

    def download_entry(self, entry, config, sftp):
        """
        Downloads the file(s) described in entry
        """

        path = urlparse(entry['url']).path or '.'
        delete_origin = config['delete_origin']
        recursive = config['recursive']

        to = config['to']
        if to:
            try:
                to = render_from_entry(to, entry)
            except RenderError as e:
                log.error('Could not render path: %s' % to)
                entry.fail(e)
                return

        if not sftp.lexists(path):
            log.error('Remote path does not exist: %s' % path)
            return

        if sftp.isfile(path):
            source_file = remotepath.basename(path)
            source_dir = remotepath.dirname(path)
            try:
                sftp.cwd(source_dir)
                self.download_file(source_file, to, sftp, delete_origin)
            except Exception as e:
                error = 'Failed to download file %s (%s)' % (path, e)
                log.error(error)
                entry.fail(error)
        elif sftp.isdir(path):
            base_path = remotepath.normpath(remotepath.join(path, '..'))
            dir_name = remotepath.basename(path)
            handle_file = partial(self.download_file, dest=to, sftp=sftp, delete_origin=delete_origin)

            try:
                sftp.cwd(base_path)
                sftp.walktree(dir_name, handle_file, self.handle_dir, self.handle_unknown, recursive)
            except Exception as e:
                error = 'Failed to download directory %s (%s)' % (path, e)
                log.error(error)
                entry.fail(error)
                
                return

            if delete_origin:
                self.remove_dir(sftp, path)
        else:
            log.warn('Skipping unknown file %s' % path)

    def on_task_download(self, task, config):
        """
        Task handler for sftp_download plugin
        """
        dependency_check()

        # Download entries by host so we can reuse the connection
        for sftp_config, entries in groupby(task.accepted, self.get_sftp_config):
            if not sftp_config:
                continue

            error_message = None
            sftp = None
            try:
                sftp = sftp_connect(sftp_config)
            except Exception as e:
                error_message = 'Failed to connect to %s (%s)' % (sftp_config.host, e)
                log.error(error_message)

            for entry in entries:
                if sftp:
                    self.download_entry(entry, config, sftp)
                else:
                    entry.fail(error_message)
            if sftp:
                sftp.close()

    def on_task_output(self, task, config):
        """Count this as an output plugin."""


@event('plugin.register')
def register_plugin():
    plugin.register(SftpList, 'sftp_list', api_ver=2)
    plugin.register(SftpDownload, 'sftp_download', api_ver=2)
