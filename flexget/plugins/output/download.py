from __future__ import unicode_literals, division, absolute_import

from builtins import *  # noqa pylint: disable=unused-import, redefined-builtin
from future.moves.urllib.parse import unquote

import hashlib
import io
import logging
import mimetypes
import os
import shutil
import socket
import sys
import tempfile
from cgi import parse_header
from http.client import BadStatusLine

from requests import RequestException

from flexget import options, plugin
from flexget.event import event
from flexget.utils.tools import decode_html, native_str_to_text
from flexget.utils.template import RenderError
from flexget.utils.pathscrub import pathscrub

log = logging.getLogger('download')


class PluginDownload(object):
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
                    'filename': {'type': 'string'}
                },
                'additionalProperties': False
            },
            {'title': 'specify path', 'type': 'string', 'format': 'path'},
            {'title': 'no options', 'type': 'boolean', 'enum': [True]}
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

        self.get_temp_files(task, require_path=config.get('require_path', False), fail_html=config['fail_html'],
                            tmp_path=tmp)

    def get_temp_file(self, task, entry, require_path=False, handle_magnets=False, fail_html=True,
                      tmp_path=tempfile.gettempdir()):
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
                    log.debug('Accepting magnet url for %s', entry['title'])
                    entry['url'] = url
                    break
                else:
                    log.warning('Can\'t download magnet url')
                    errors.append('Magnet URL')
                    continue
            if require_path and 'path' not in entry:
                # Don't fail here, there might be a magnet later in the list of urls
                log.debug('Skipping url %s because there is no path for download', url)
                continue
            error = self.process_entry(task, entry, url, tmp_path)

            # disallow html content
            html_mimes = ['html', 'text/html']
            if entry.get('mime-type') in html_mimes and fail_html:
                error = 'Unexpected html content received from `%s` - maybe a login page?' % entry['url']
                self.cleanup_temp_file(entry)

            if not error:
                # Set the main url, so we know where this file actually came from
                log.debug('Successfully retrieved %s from %s', entry['title'], url)
                entry['url'] = url
                break
            else:
                errors.append(error)
        else:
            # check if entry must have a path (download: yes)
            if require_path and 'path' not in entry:
                log.error('%s can\'t be downloaded, no path specified for entry', entry['title'])
                entry.fail('no path specified for entry')
            else:
                entry.fail(', '.join(errors))

    def save_error_page(self, entry, task, page):
        received = os.path.join(task.manager.config_base, 'received', task.name)
        if not os.path.isdir(received):
            os.makedirs(received)
        filename = os.path.join(received, pathscrub('%s.error' % entry['title'], filename=True))
        log.error('Error retrieving %s, the error page has been saved to %s', entry['title'], filename)
        with io.open(filename, 'wb') as outfile:
            outfile.write(page)

    def get_temp_files(self, task, require_path=False, handle_magnets=False, fail_html=True,
                       tmp_path=tempfile.gettempdir()):
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
                log.info('Would download: %s', entry['title'])
            else:
                if not task.manager.unit_test:
                    log.info('Downloading: %s', entry['title'])
                self.download_entry(task, entry, url, tmp_path)
        except RequestException as e:
            log.warning('RequestException %s, while downloading %s', e, url)
            return 'Network error during request: %s' % e
        except BadStatusLine as e:
            log.warning('Failed to reach server. Reason: %s', getattr(e, 'message', 'N/A'))
            return 'BadStatusLine'
        except IOError as e:
            if hasattr(e, 'reason'):
                log.warning('Failed to reach server. Reason: %s', e.reason)
            elif hasattr(e, 'code'):
                log.warning('The server couldn\'t fulfill the request. Error code: %s', e.code)
            log.debug('IOError', exc_info=True)
            return 'IOError'
        except ValueError as e:
            # Probably unknown url type
            msg = 'ValueError %s' % e
            log.warning(msg)
            log.debug(msg, exc_info=True)
            return msg

    def download_entry(self, task, entry, url, tmp_path):
        """Downloads `entry` by using `url`.

        :raises: Several types of exceptions ...
        :raises: PluginWarning
        """

        log.debug('Downloading url \'%s\'', url)

        # get content
        auth = None
        if 'download_auth' in entry:
            auth = entry['download_auth']
            log.debug('Custom auth enabled for %s download: %s', entry['title'], entry['download_auth'])

        try:
            response = task.requests.get(url, auth=auth, raise_status=False)
        except UnicodeError:
            log.error('Unicode error while encoding url %s', url)
            return
        if response.status_code != 200:
            log.debug('Got %s response from server. Saving error page.', response.status_code)
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
            log.debug('creating tmp_path %s' % tmp_path)
            os.mkdir(tmp_path)

        # check for write-access
        if not os.access(tmp_path, os.W_OK):
            raise plugin.PluginError('Not allowed to write to temp directory `%s`' % tmp_path)

        # download and write data into a temp file
        tmp_dir = tempfile.mkdtemp(dir=tmp_path)
        fname = hashlib.md5(url.encode('utf-8', 'replace')).hexdigest()
        datafile = os.path.join(tmp_dir, fname)
        outfile = io.open(datafile, 'wb')
        try:
            for chunk in response.iter_content(chunk_size=150 * 1024, decode_unicode=False):
                outfile.write(chunk)
        except Exception as e:
            # don't leave futile files behind
            # outfile has to be closed before we can delete it on Windows
            outfile.close()
            log.debug('Download interrupted, removing datafile')
            os.remove(datafile)
            if isinstance(e, socket.timeout):
                log.error('Timeout while downloading file')
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
            log.debug('%s field file set to: %s', entry['title'], entry['file'])

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
            log.info('Content-disposition disabled for %s', entry['title'])
        self.filename_ext_from_mime(entry)

        if not entry.get('filename'):
            filename = unquote(url.rsplit('/', 1)[1])
            log.debug('No filename - setting from url: %s', filename)
            entry['filename'] = filename
        log.debug('Finishing download_entry() with filename %s', entry.get('filename'))

    def filename_from_headers(self, entry, response):
        """Checks entry filename if it's found from content-disposition"""
        if not response.headers.get('content-disposition'):
            # No content disposition header, nothing we can do
            return
        filename = parse_header(response.headers['content-disposition'])[1].get('filename')

        if filename:
            # try to decode to unicode, specs allow latin1, some may do utf-8 anyway
            try:
                filename = native_str_to_text(filename, encoding='latin1')
                log.debug('filename header latin1 decoded')
            except UnicodeError:
                try:
                    filename = native_str_to_text(filename, encoding='utf-8')
                    log.debug('filename header UTF-8 decoded')
                except UnicodeError:
                    pass
            filename = decode_html(filename)
            log.debug('Found filename from headers: %s', filename)
            if 'filename' in entry:
                log.debug('Overriding filename %s with %s from content-disposition', entry['filename'], filename)
            entry['filename'] = filename

    def filename_ext_from_mime(self, entry):
        """Tries to set filename extension from mime-type"""
        extensions = mimetypes.guess_all_extensions(entry['mime-type'], strict=False)
        if extensions:
            log.debug('Mimetype guess for %s is %s ', entry['mime-type'], extensions)
            if entry.get('filename'):
                if any(entry['filename'].endswith(extension) for extension in extensions):
                    log.debug('Filename %s extension matches to mime-type', entry['filename'])
                else:
                    # mimetypes library has no concept of a 'prefered' extension when there are multiple possibilites
                    # this causes the first to be used which is not always desirable, e.g. 'ksh' for 'text/plain'
                    extension = mimetypes.guess_extension(entry['mime-type'], strict=False)
                    log.debug('Adding mime-type extension %s to %s', extension, entry['filename'])
                    entry['filename'] = entry['filename'] + extension
        else:
            log.debug('Python doesn\'t know extension for mime-type: %s', entry['mime-type'])

    def on_task_output(self, task, config):
        """Move downloaded content from temp folder to final destination"""
        config = self.process_config(config)
        for entry in task.accepted:
            try:
                self.output(task, entry, config)
            except plugin.PluginWarning as e:
                entry.fail()
                log.error('Plugin error while writing: %s', e)
            except Exception as e:
                entry.fail()
                log.exception('Exception while writing: %s', e)

    def output(self, task, entry, config):
        """Moves temp-file into final destination

        Raises:
            PluginError if operation fails
        """

        if 'file' not in entry and not task.options.test:
            log.debug('file missing, entry: %s', entry)
            raise plugin.PluginError('Entry `%s` has no temp file associated with' % entry['title'])

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
                log.info('Would write `%s` to `%s`', entry['title'], path)
                # Set a fake location, so the exec plugin can do string replacement during --test #1015
                entry['location'] = os.path.join(path, 'TEST_MODE_NO_OUTPUT')
                return

            # make path
            if not os.path.isdir(path):
                log.debug('Creating directory %s', path)
                try:
                    os.makedirs(path)
                except:
                    raise plugin.PluginError('Cannot create path %s' % path, log)

            # check that temp file is present
            if not os.path.exists(entry['file']):
                log.debug('entry: %s', entry)
                raise plugin.PluginWarning('Downloaded temp file `%s` doesn\'t exist!?' % entry['file'])

            if config.get('filename'):
                try:
                    entry['filename'] = entry.render(config['filename'])
                    log.debug('set filename from config %s' % entry['filename'])
                except RenderError as e:
                    entry.fail('Could not set filename. Error during string replacement: %s' % e)
                    return
            # if we still don't have a filename, try making one from title (last resort)
            elif not entry.get('filename'):
                entry['filename'] = entry['title']
                log.debug('set filename from title %s', entry['filename'])
                if 'mime-type' not in entry:
                    log.warning('Unable to figure proper filename for %s. Using title.', entry['title'])
                else:
                    guess = mimetypes.guess_extension(entry['mime-type'])
                    if not guess:
                        log.warning('Unable to guess extension with mime-type %s', guess)
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
            log.debug('destfile: %s', destfile)

            if os.path.exists(destfile):
                import filecmp
                if filecmp.cmp(entry['file'], destfile):
                    log.debug("Identical destination file '%s' already exists", destfile)
                elif config.get('overwrite'):
                    log.debug("Overwriting already existing file %s", destfile)
                else:
                    log.info('File `%s` already exists and is not identical, download failed.', destfile)
                    entry.fail('File `%s` already exists and is not identical.' % destfile)
                    return
            else:
                # move temp file
                log.debug('moving %s to %s', entry['file'], destfile)

                try:
                    shutil.move(entry['file'], destfile)
                except (IOError, OSError) as err:
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
                log.debug('removing temp file %s from %s', entry['file'], entry['title'])
                os.remove(entry['file'])
            if os.path.exists(os.path.dirname(entry['file'])):
                shutil.rmtree(os.path.dirname(entry['file']))
            del (entry['file'])

    def cleanup_temp_files(self, task):
        """Checks all entries for leftover temp files and deletes them."""
        for entry in task.entries + task.rejected + task.failed:
            self.cleanup_temp_file(entry)


@event('plugin.register')
def register_plugin():
    plugin.register(PluginDownload, 'download', api_ver=2)


@event('options.register')
def register_parser_arguments():
    options.get_parser('execute').add_argument('--dl-path', dest='dl_path', default=False, metavar='PATH',
                                               help='override path for download plugin, applies to all executed tasks')
