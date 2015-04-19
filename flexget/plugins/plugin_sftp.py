from __future__ import unicode_literals, division, absolute_import
from urlparse import urljoin, urlparse
from collections import defaultdict, namedtuple
import logging
import os
import time
from functools import partial

from flexget import plugin
from flexget.event import event
from flexget.entry import Entry
from flexget.config_schema import one_or_more
from flexget.utils.template import render_from_entry, RenderError

log = logging.getLogger('sftp')

ConenctionConfig = namedtuple('ConenctionConfig', ['host', 'port', 'username', 'password', \
                              'private_key', 'private_key_pass'])

try:
    import pysftp
    logging.getLogger("paramiko").setLevel(logging.WARNING)
except:
    pysftp = None

def sftp_connect(conf):
    """
    Helper function to connect to an sftp server
    """

    sftp = pysftp.Connection(host=conf.host, username=conf.username,
                             private_key=conf.private_key, password=conf.password, 
                             port=conf.port, private_key_pass=conf.private_key_pass)
    log.debug('Connected to %s' % conf.host)

    
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

    config
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
    dirs:
        List of directories to download

    Example:

      sftp_list:
          config:
              host: example.com
              username: ieaston
              private_key: /Users/uername/.ssh/id_rsa
              recursive: False
              get_size: True
              files_only: False
          dirs:
              - '/path/to/list/'
    """

    schema = {
        'type': 'object',
        'properties': {
            'config': {
                'type': 'object',
                'properties': {
                    'username': {'type': 'string'},
                    'password': {'type': 'string'},
                    'host': {'type': 'string'},
                    'port': {'type': 'integer'},
                    'files_only': {'type': 'boolean', 'default': True},
                    'recursive': {'type': 'boolean', 'default': False},
                    'get_size': {'type': 'boolean', 'default': True},
                    'private_key': {'type': 'string'},
                    'private_key_pass': {'type': 'string'}
                },
                'additionProperties': False,
                'required': ['host', 'username'],
            },
            'dirs': one_or_more({'type': 'string'}),
        },
        'required': ['config'],
        'additionalProperties': False
    }

    def prepare_config(self, config):
        """
        Sets defaults for the provided configuration
        """
        config['config'].setdefault('port', 22)
        config['config'].setdefault('password', None)
        config['config'].setdefault('private_key', None)
        config['config'].setdefault('private_key_pass', None)
        config['config'].setdefault('dirs', ['.'])
        config.setdefault('dirs', ['.'])

        return config

    def on_task_input(self, task, config):
        """
        Input task handler
        """

        dependency_check()
        
        config = self.prepare_config(config)
        connection_config = config['config']

        host = connection_config['host']
        port = connection_config['port']
        username = connection_config['username']
        password = connection_config['password']
        private_key = connection_config['private_key']
        private_key_pass = connection_config['private_key_pass']
        
        dirs = config['dirs']
        files_only = connection_config['files_only']
        recursive = connection_config['recursive']
        get_size = connection_config['get_size']

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

        conn_conf = ConenctionConfig(host, port, username, password, private_key, private_key_pass)
        
        try:
            sftp = sftp_connect(conn_conf)
        except Exception as e:
            log.error('Failed to connect to %s (%s)' % (conf.host, e))
            return

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
            node_size = lambda f: sizes.append(file_size(f))
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
            title = os.path.basename(path)

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
            'delete_origin': {'type': 'boolean', 'default' : False}
        },
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
        try:
            private_key = entry['private_key']
        except KeyError:
            private_key = None
        try:
            private_key = entry['private_key_pass']
        except KeyError:
            private_key_pass = None

        sftp_config = ConenctionConfig(host, port, username, password, private_key, private_key_pass)

        return sftp_config


    def prepare_config(self, config, task):
        """
        Sets defaults for the provided configuration
        """
        config.setdefault('to', os.path.join(task.manager.config_base, 'temp'))

        return config

    def download_entry(self, entry, config, sftp):
        """
        Downloads the file(s) described in entry
        """

        path = urlparse(entry['url']).path or '.'
        delete_origin = config['delete_origin']

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

        if not os.path.exists(to):
            os.makedirs(to)

        os.chdir(to)

        if sftp.isdir(path):
            base_path = os.path.normpath(os.path.join(path, '..'))
            dir_name = os.path.basename(path)

            log.verbose('Downloading directory %s' % path)
            try:
                sftp.cwd(base_path)
                sftp.get_r(dir_name, to)
            except Exception as e:
                error = 'Failed to download directory %s (%s)' % (path, e)
                log.error(error)
                entry.fail(error)
                return

            if delete_origin:
                log.debug('Attempting to delete directory %s' % path)
                try:
                    sftp.rmdir(dir_name)
                except Exception as e:
                    log.error('Failed to delete directory %s' % e)
                    return

        elif sftp.isfile(path):
            destination = os.path.join(to, os.path.basename(path))

            log.verbose('Downloading file %s' % path)
            try:
                sftp.get(path, destination)
            except Exception as e:
                error = 'Failed to download file %s (%s)' % (path, e)
                log.error(error)
                entry.fail(error)
                return

            if delete_origin:
                try:
                    sftp.remove(path)
                except Exception as e:
                    log.error('Failed to delete file %s (%s)' % (path, e))
                    return
        else:
            log.warn('Skipping unknown file %s' % path)


    def on_task_download(self, task, config):
        """
        Task handler for sftp_download plugin
        """
        dependency_check()
        config = self.prepare_config(config, task)

        downloads = defaultdict(list)

        # Group entries by their connection config
        for entry in task.accepted:
            sftp_config = self.get_sftp_config(entry)
            downloads[sftp_config].append(entry)

        # Download entries by host so we can reuse the connection
        for sftp_config, entries in downloads.iteritems():
            error_message = None
            try:
                sftp = sftp_connect(sftp_config)
            except Exception as e:
                error_message = 'Failed to connect to %s (%s)' % (conf.host, e)
                log.error(error_message)

            for entry in entries:
                if sftp:
                    self.download_entry(entry, config, sftp)
                else:
                    entry.fail(error_message)
                    continue
            sftp.close()

    def on_task_output(self, task, config):
        """Count this as an output plugin."""


@event('plugin.register')
def register_plugin():
    plugin.register(SftpList, 'sftp_list', api_ver=2)
    plugin.register(SftpDownload, 'sftp_download', api_ver=2)
