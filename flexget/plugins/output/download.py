import hashlib
import mimetypes
import os
import shutil
import socket
import sys
import tempfile
from cgi import parse_header
from http.client import BadStatusLine
from urllib.parse import unquote

from loguru import logger
from requests import RequestException

from flexget import options, plugin
from flexget.event import event
from flexget.utils.pathscrub import pathscrub
from flexget.utils.template import RenderError
from flexget.utils.tools import decode_html

logger = logger.bind(name='download')


class PluginDownload:
    """
    Downloads content from entry url and writes it into a file.

    Example::

      download: ~/torrents/

    Allow HTML content:

    By default download plugin reports failure if received content
    is a html. Usually this is some sort of custom error page without
    proper http code and thus entry is assumed to be downloaded
    incorrectly.

    In the rare case you actually need to retrieve html-pages you must
    disable this feature.

    Example::

      download:
        path: ~/something/
        fail_html: no

    You may use commandline parameter --dl-path to temporarily override
    all paths to another location.
    """

    schema = {
        'oneOf': [
            {
                'title': 'specify options',
                'type': 'object',
                'properties': {
                    'path': {'type': 'string', 'format': 'path'},
                    'fail_html': {'type': 'boolean', 'default': True},
                    'overwrite': {'type': 'boolean', 'default': False},
                    'temp': {'type': 'string', 'format': 'path'},
                    'filename': {'type': 'string'},
                },
                'additionalProperties': False,
            },
            {'title': 'specify path', 'type': 'string', 'format': 'path'},
            {'title': 'no options', 'type': 'boolean', 'enum': [True]},
        ]
    }

    def process_config(self, config):
        """Return plugin configuration in advanced form"""
        if isinstance(config, str):
            config = {'path': config}
        if not isinstance(config, dict):
            config = {}
        if not config.get('path'):
            config['require_path'] = True
        config.setdefault('fail_html', True)
        return config

    def on_task_download(self, task, config):
        config = self.process_config(config)

        # set temporary download path based on user's config setting or use fallback
        tmp = config.get('temp', os.path.join(task.manager.config_base, 'temp'))

        self.get_temp_files(
            task,
            require_path=config.get('require_path', False),
            fail_html=config['fail_html'],
            tmp_path=tmp,
        )

    def get_temp_file(
        self,
        task,
        entry,
        require_path=False,
        handle_magnets=False,
        fail_html=True,
        tmp_path=tempfile.gettempdir(),
    ):
        """
        Download entry content and store in temporary folder.
        Fails entry with a reason if there was problem.

        :param bool require_path:
          whether or not entries without 'path' field are ignored
        :param bool handle_magnets:
          when used any of urls containing magnet link will replace url,
          otherwise warning is printed.
        :param fail_html:
          fail entries which url respond with html content
        :param tmp_path:
          path to use for temporary files while downloading
        """
        if entry.get('urls'):
            urls = entry.get('urls')
        else:
            urls = [entry['url']]
        errors = []
        for url in urls:
            if url.startswith('magnet:'):
                if handle_magnets:
                    # Set magnet link as main url, so a torrent client plugin can grab it
                    logger.debug('Accepting magnet url for {}', entry['title'])
                    entry['url'] = url
                    break
                else:
                    logger.warning('Can\'t download magnet url')
                    errors.append('Magnet URL')
                    continue
            if require_path and 'path' not in entry:
                # Don't fail here, there might be a magnet later in the list of urls
                logger.debug('Skipping url {} because there is no path for download', url)
                continue
            error = self.process_entry(task, entry, url, tmp_path)

            # disallow html content
            html_mimes = ['html', 'text/html']
            if entry.get('mime-type') in html_mimes and fail_html:
                error = (
                    'Unexpected html content received from `%s` - maybe a login page?'
                    % entry['url']
                )
                self.cleanup_temp_file(entry)

            if not error:
                # Set the main url, so we know where this file actually came from
                logger.debug('Successfully retrieved {} from {}', entry['title'], url)
                entry['url'] = url
                break
            else:
                errors.append(error)
        else:
            # check if entry must have a path (download: yes)
            if require_path and 'path' not in entry:
                logger.error("{} can't be downloaded, no path specified for entry", entry['title'])
                entry.fail('no path specified for entry')
            else:
                entry.fail(', '.join(errors))

    def save_error_page(self, entry, task, page):
        received = os.path.join(task.manager.config_base, 'received', task.name)
        if not os.path.isdir(received):
            os.makedirs(received)
        filename = os.path.join(received, pathscrub('%s.error' % entry['title'], filename=True))
        logger.error(
            'Error retrieving {}, the error page has been saved to {}', entry['title'], filename
        )
        with open(filename, 'wb') as outfile:
            outfile.write(page)

    def get_temp_files(
        self,
        task,
        require_path=False,
        handle_magnets=False,
        fail_html=True,
        tmp_path=tempfile.gettempdir(),
    ):
        """Download all task content and store in temporary folder.

        :param bool require_path:
          whether or not entries without 'path' field are ignored
        :param bool handle_magnets:
          when used any of urls containing magnet link will replace url,
          otherwise warning is printed.
        :param fail_html:
          fail entries which url respond with html content
        :param tmp_path:
          path to use for temporary files while downloading
        """
        for entry in task.accepted:
            self.get_temp_file(task, entry, require_path, handle_magnets, fail_html, tmp_path)

    # TODO: a bit silly method, should be get rid of now with simplier exceptions ?
    def process_entry(self, task, entry, url, tmp_path):
        """
        Processes `entry` by using `url`. Does not use entry['url'].
        Does not fail the `entry` if there is a network issue, instead just logs and returns a string error.

        :param task: Task
        :param entry: Entry
        :param url: Url to try download
        :param tmp_path: Path to store temporary files
        :return: String error, if failed.
        """
        try:
            if task.options.test:
                logger.info('Would download: {}', entry['title'])
            else:
                if not task.manager.unit_test:
                    logger.info('Downloading: {}', entry['title'])
                self.download_entry(task, entry, url, tmp_path)
        except RequestException as e:
            logger.warning('RequestException {}, while downloading {}', e, url)
            return 'Network error during request: %s' % e
        except BadStatusLine as e:
            logger.warning('Failed to reach server. Reason: {}', getattr(e, 'message', 'N/A'))
            return 'BadStatusLine'
        except OSError as e:
            if hasattr(e, 'reason'):
                logger.warning('Failed to reach server. Reason: {}', e.reason)
            elif hasattr(e, 'code'):
                logger.warning("The server couldn't fulfill the request. Error code: {}", e.code)
            logger.opt(exception=True).debug('OSError')
            return 'OSError'
        except ValueError as e:
            # Probably unknown url type
            msg = 'ValueError %s' % e
            logger.warning(msg)
            logger.opt(exception=True).debug(msg)
            return msg

    def download_entry(self, task, entry, url, tmp_path):
        """Downloads `entry` by using `url`.

        :raises: Several types of exceptions ...
        :raises: PluginWarning
        """

        logger.debug("Downloading url '{}'", url)

        # get content
        auth = None
        if 'download_auth' in entry:
            auth = entry['download_auth']
            logger.debug(
                'Custom auth enabled for {} download: {}', entry['title'], entry['download_auth']
            )

        headers = task.requests.headers
        if 'download_headers' in entry:
            headers.update(entry['download_headers'])
            logger.debug(
                'Custom headers enabled for {} download: {}',
                entry['title'],
                entry['download_headers'],
            )

        try:
            response = task.requests.get(url, auth=auth, raise_status=False, headers=headers)
        except UnicodeError:
            logger.error('Unicode error while encoding url {}', url)
            return
        if response.status_code != 200:
            logger.debug('Got {} response from server. Saving error page.', response.status_code)
            # Save the error page
            if response.content:
                self.save_error_page(entry, task, response.content)
            # Raise the error
            response.raise_for_status()
            return

        # expand ~ in temp path
        # TODO jinja?
        try:
            tmp_path = os.path.expanduser(tmp_path)
        except RenderError as e:
            entry.fail('Could not set temp path. Error during string replacement: %s' % e)
            return

        # Clean illegal characters from temp path name
        tmp_path = pathscrub(tmp_path)

        # create if missing
        if not os.path.isdir(tmp_path):
            logger.debug('creating tmp_path {}', tmp_path)
            os.mkdir(tmp_path)

        # check for write-access
        if not os.access(tmp_path, os.W_OK):
            raise plugin.PluginError('Not allowed to write to temp directory `%s`' % tmp_path)

        # download and write data into a temp file
        tmp_dir = tempfile.mkdtemp(dir=tmp_path)
        fname = hashlib.md5(url.encode('utf-8', 'replace')).hexdigest()
        datafile = os.path.join(tmp_dir, fname)
        outfile = open(datafile, 'wb')
        try:
            for chunk in response.iter_content(chunk_size=150 * 1024, decode_unicode=False):
                outfile.write(chunk)
        except Exception as e:
            # don't leave futile files behind
            # outfile has to be closed before we can delete it on Windows
            outfile.close()
            logger.debug('Download interrupted, removing datafile')
            os.remove(datafile)
            if isinstance(e, socket.timeout):
                logger.error('Timeout while downloading file')
            else:
                raise
        else:
            outfile.close()
            # Do a sanity check on downloaded file
            if os.path.getsize(datafile) == 0:
                entry.fail('File %s is 0 bytes in size' % datafile)
                os.remove(datafile)
                return
            # store temp filename into entry so other plugins may read and modify content
            # temp file is moved into final destination at self.output
            entry['file'] = datafile
            logger.debug('{} field file set to: {}', entry['title'], entry['file'])

        if 'content-type' in response.headers:
            entry['mime-type'] = str(parse_header(response.headers['content-type'])[0])
        else:
            entry['mime-type'] = "unknown/unknown"

        content_encoding = response.headers.get('content-encoding', '')
        decompress = 'gzip' in content_encoding or 'deflate' in content_encoding
        if 'content-length' in response.headers and not decompress:
            entry['content-length'] = int(response.headers['content-length'])

        # prefer content-disposition naming, note: content-disposition can be disabled completely
        # by setting entry field `content-disposition` to False
        if entry.get('content-disposition', True):
            self.filename_from_headers(entry, response)
        else:
            logger.info('Content-disposition disabled for {}', entry['title'])
        self.filename_ext_from_mime(entry)

        if not entry.get('filename'):
            filename = unquote(url.rsplit('/', 1)[1])
            logger.debug('No filename - setting from url: {}', filename)
            entry['filename'] = filename
        logger.debug('Finishing download_entry() with filename {}', entry.get('filename'))

    def filename_from_headers(self, entry, response):
        """Checks entry filename if it's found from content-disposition"""
        if not response.headers.get('content-disposition'):
            # No content disposition header, nothing we can do
            return
        filename = parse_header(response.headers['content-disposition'])[1].get('filename')

        if filename:
            filename = decode_html(filename)
            logger.debug('Found filename from headers: {}', filename)
            if 'filename' in entry:
                logger.debug(
                    'Overriding filename {} with {} from content-disposition',
                    entry['filename'],
                    filename,
                )
            entry['filename'] = filename

    def filename_ext_from_mime(self, entry):
        """Tries to set filename extension from mime-type"""
        extensions = mimetypes.guess_all_extensions(entry['mime-type'], strict=False)
        if extensions:
            logger.debug('Mimetype guess for {} is {} ', entry['mime-type'], extensions)
            if entry.get('filename'):
                if any(entry['filename'].endswith(extension) for extension in extensions):
                    logger.debug('Filename {} extension matches to mime-type', entry['filename'])
                else:
                    # mimetypes library has no concept of a 'prefered' extension when there are multiple possibilites
                    # this causes the first to be used which is not always desirable, e.g. 'ksh' for 'text/plain'
                    extension = mimetypes.guess_extension(entry['mime-type'], strict=False)
                    logger.debug(
                        'Adding mime-type extension {} to {}', extension, entry['filename']
                    )
                    entry['filename'] = entry['filename'] + extension
        else:
            logger.debug("Python doesn't know extension for mime-type: {}", entry['mime-type'])

    def on_task_output(self, task, config):
        """Move downloaded content from temp folder to final destination"""
        config = self.process_config(config)
        for entry in task.accepted:
            try:
                self.output(task, entry, config)
            except plugin.PluginWarning as e:
                entry.fail()
                logger.error('Plugin error while writing: {}', e)
            except Exception as e:
                entry.fail()
                logger.exception('Exception while writing: {}', e)

    def output(self, task, entry, config):
        """Moves temp-file into final destination

        Raises:
            PluginError if operation fails
        """

        if 'file' not in entry and not task.options.test:
            logger.debug('file missing, entry: {}', entry)
            raise plugin.PluginError(
                'Entry `%s` has no temp file associated with' % entry['title'], logger
            )

        try:
            # use path from entry if has one, otherwise use from download definition parameter
            path = entry.get('path', config.get('path'))
            if not isinstance(path, str):
                raise plugin.PluginError('Invalid `path` in entry `%s`' % entry['title'])

            # override path from command line parameter
            if task.options.dl_path:
                path = task.options.dl_path

            # expand variables in path
            try:
                path = os.path.expanduser(entry.render(path))
            except RenderError as e:
                entry.fail('Could not set path. Error during string replacement: %s' % e)
                return

            # Clean illegal characters from path name
            path = pathscrub(path)

            # If we are in test mode, report and return
            if task.options.test:
                logger.info('Would write `{}` to `{}`', entry['title'], path)
                # Set a fake location, so the exec plugin can do string replacement during --test #1015
                entry['location'] = os.path.join(path, 'TEST_MODE_NO_OUTPUT')
                return

            # make path
            if not os.path.isdir(path):
                logger.debug('Creating directory {}', path)
                try:
                    os.makedirs(path)
                except:
                    raise plugin.PluginError('Cannot create path %s' % path, logger)

            # check that temp file is present
            if not os.path.exists(entry['file']):
                logger.debug('entry: {}', entry)
                raise plugin.PluginWarning(
                    'Downloaded temp file `%s` doesn\'t exist!?' % entry['file']
                )

            if config.get('filename'):
                try:
                    entry['filename'] = entry.render(config['filename'])
                    logger.debug('set filename from config {}', entry['filename'])
                except RenderError as e:
                    entry.fail('Could not set filename. Error during string replacement: %s' % e)
                    return
            # if we still don't have a filename, try making one from title (last resort)
            elif not entry.get('filename'):
                entry['filename'] = entry['title']
                logger.debug('set filename from title {}', entry['filename'])
                if 'mime-type' not in entry:
                    logger.warning(
                        'Unable to figure proper filename for {}. Using title.', entry['title']
                    )
                else:
                    guess = mimetypes.guess_extension(entry['mime-type'])
                    if not guess:
                        logger.warning('Unable to guess extension with mime-type {}', guess)
                    else:
                        self.filename_ext_from_mime(entry)

            name = entry.get('filename', entry['title'])
            # Remove illegal characters from filename #325, #353
            name = pathscrub(name)
            # Remove directory separators from filename #208
            name = name.replace('/', ' ')
            if sys.platform.startswith('win'):
                name = name.replace('\\', ' ')
            # remove duplicate spaces
            name = ' '.join(name.split())
            # combine to full path + filename
            destfile = os.path.join(path, name)
            logger.debug('destfile: {}', destfile)

            if os.path.exists(destfile):
                import filecmp

                if filecmp.cmp(entry['file'], destfile):
                    logger.debug("Identical destination file '{}' already exists", destfile)
                elif config.get('overwrite'):
                    logger.debug('Overwriting already existing file {}', destfile)
                else:
                    logger.info(
                        'File `{}` already exists and is not identical, download failed.', destfile
                    )
                    entry.fail('File `%s` already exists and is not identical.' % destfile)
                    return
            else:
                # move temp file
                logger.debug('moving {} to {}', entry['file'], destfile)

                try:
                    shutil.move(entry['file'], destfile)
                except (OSError, OSError) as err:
                    # ignore permission errors, see ticket #555
                    import errno

                    if not os.path.exists(destfile):
                        raise plugin.PluginError('Unable to write %s: %s' % (destfile, err))
                    if err.errno != errno.EPERM and err.errno != errno.EACCES:
                        raise

            # store final destination as output key
            entry['location'] = destfile

        finally:
            self.cleanup_temp_file(entry)

    def on_task_learn(self, task, config):
        """Make sure all temp files are cleaned up after output phase"""
        self.cleanup_temp_files(task)

    def on_task_abort(self, task, config):
        """Make sure all temp files are cleaned up when task is aborted."""
        self.cleanup_temp_files(task)

    def cleanup_temp_file(self, entry):
        if 'file' in entry:
            if os.path.exists(entry['file']):
                logger.debug('removing temp file {} from {}', entry['file'], entry['title'])
                os.remove(entry['file'])
            if os.path.exists(os.path.dirname(entry['file'])):
                shutil.rmtree(os.path.dirname(entry['file']))
            del entry['file']

    def cleanup_temp_files(self, task):
        """Checks all entries for leftover temp files and deletes them."""
        for entry in task.entries + task.rejected + task.failed:
            self.cleanup_temp_file(entry)


@event('plugin.register')
def register_plugin():
    plugin.register(PluginDownload, 'download', api_ver=2)


@event('options.register')
def register_parser_arguments():
    options.get_parser('execute').add_argument(
        '--dl-path',
        dest='dl_path',
        default=False,
        metavar='PATH',
        help='override path for download plugin, applies to all executed tasks',
    )
