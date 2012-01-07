import os
import time
import urllib
import urllib2
import logging
import mimetypes
import hashlib
import shutil
import sys
from cgi import parse_header
from httplib import BadStatusLine
from requests import RequestException
from flexget.plugin import register_plugin, register_parser_option, get_plugin_by_name, PluginWarning, PluginError
from flexget.utils.tools import decode_html
from flexget.utils.template import RenderError

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

    def validator(self):
        """Return config validator"""
        from flexget import validator
        root = validator.factory()
        root.accept('path', allow_replacement=True)
        root.accept('boolean')
        advanced = root.accept('dict')
        advanced.accept('path', key='path', allow_replacement=True)
        advanced.accept('boolean', key='fail_html')
        advanced.accept('boolean', key='overwrite')
        return root

    def process_config(self, config):
        """Return plugin configuration in advanced form"""
        if isinstance(config, basestring):
            config = {'path': config}
        if not isinstance(config, dict):
            config = {}
        config.setdefault('fail_html', True)
        if not config.get('path'):
            config['require_path'] = True
        return config

    def on_process_start(self, feed, config):
        """Register the usable set keywords."""
        set_plugin = get_plugin_by_name('set')
        set_plugin.instance.register_keys({'path': 'text'})

    def on_feed_download(self, feed, config):
        config = self.process_config(config)
        self.get_temp_files(feed, require_path=config.get('require_path', False), fail_html=config['fail_html'])

    def get_temp_file(self, feed, entry, require_path=False, handle_magnets=False, fail_html=True):
        """Download entry content and store in temporary folder.

        :param bool require_path:
          whether or not entries without 'path' field are ignored
        :param bool handle_magnets:
          when used any of urls containing magnet link will replace url,
          otherwise warning is printed.
        :param fail_html:
          fail entries which url respond with html content
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
                    log.debug('Accepting magnet url for %s' % entry['title'])
                    entry['url'] = url
                    break
                else:
                    log.warning('Can\'t download magnet url')
                    errors.append('Magnet URL')
                    continue
            if require_path and 'path' not in entry:
                # Don't fail here, there might be a magnet later in the list of urls
                log.debug('Skipping url %s because there is no path for download' % url)
                continue
            error = self.process_entry(feed, entry, url)

            # disallow html content
            html_mimes = ['html', 'text/html']
            if entry.get('mime-type') in html_mimes and fail_html:
                error = 'Unexpected html content received from `%s` - maybe a login page?' % entry['url']
                self.cleanup_temp_file(entry)

            if not error:
                # Set the main url, so we know where this file actually came from
                log.debug('Successfully retrieved %s from %s' % (entry['title'], url))
                entry['url'] = url
                break
            else:
                errors.append(error)
        else:
            # check if entry must have a path (download: yes)
            if require_path and 'path' not in entry:
                log.error('%s can\'t be downloaded, no path specified for entry' % entry['title'])
                feed.fail(entry, 'no path specified for entry')
            else:
                feed.fail(entry, ", ".join(errors))

    def save_error_page(self, entry, feed, page):
        received = os.path.join(feed.manager.config_base, 'received', feed.name)
        if not os.path.isdir(received):
            os.makedirs(received)
        filename = os.path.join(received, '%s.error' % entry['title'].encode(sys.getfilesystemencoding(), 'replace'))
        log.error('Error retrieving %s, the error page has been saved to %s' % (entry['title'], filename))
        outfile = open(filename, 'w')
        try:
            outfile.write(page)
        finally:
            outfile.close()

    def get_temp_files(self, feed, require_path=False, handle_magnets=False, fail_html=True):
        """Download all feed content and store in temporary folder.

        :param bool require_path:
          whether or not entries without 'path' field are ignored
        :param bool handle_magnets:
          when used any of urls containing magnet link will replace url,
          otherwise warning is printed.
        :param fail_html:
          fail entries which url respond with html content
        """
        for entry in feed.accepted:
            self.get_temp_file(feed, entry, require_path, handle_magnets, fail_html)

    def process_entry(self, feed, entry, url):
        """Processes :entry: by using :url: from it.
           Does not fail the :entry: if there is a network issue, instead just log and return a string error."""
        try:
            if feed.manager.options.test:
                log.info('Would download: %s' % entry['title'])
            else:
                if not feed.manager.unit_test:
                    log.info('Downloading: %s' % entry['title'])
                self.download_entry(feed, entry, url)
        except RequestException, e:
            # TODO: Improve this error message?
            log.warning('RequestException %s' % e)
            return 'Request Exception'
        # TODO: I think these exceptions will not be thrown by requests library.
        except urllib2.HTTPError, e:
            log.warning('HTTPError %s' % e.code)
            return 'HTTP error'
        except urllib2.URLError, e:
            log.warning('URLError %s' % e.reason)
            return 'URL Error'
        except BadStatusLine, e:
            log.warning('Failed to reach server. Reason: %s' % getattr(e, 'message', 'N/A'))
            return 'BadStatusLine'
        except IOError, e:
            if hasattr(e, 'reason'):
                log.warning('Failed to reach server. Reason: %s' % e.reason)
            elif hasattr(e, 'code'):
                log.warning('The server couldn\'t fulfill the request. Error code: %s' % e.code)
            log.debug('IOError', exc_info=True)
            return 'IOError'
        except ValueError, e:
            # Probably unknown url type
            msg = 'ValueError %s' % e
            log.warning(msg)
            log.debug(msg, exc_info=True)
            return msg

    def download_entry(self, feed, entry, url):
        """Downloads :entry: by using :url:

        Raises:
            Several types of exceptions ...
            PluginWarning
        """

        # see http://bugs.python.org/issue1712522
        # note, url is already unicode ...
        try:
            url = url.encode('latin1')
        except UnicodeEncodeError:
            log.debug('URL for `%s` could not be encoded in latin1' % entry['title'])
            try:
                url = url.encode('utf-8')
            except:
                log.warning('Unable to URL-encode URL for `%s`' % entry['title'])
        if not isinstance(url, unicode):
            url = urllib.quote(url, safe=':/~?=&%')
        log.debug('Downloading url \'%s\'' % url)

        # get content
        auth = None
        if 'basic_auth_password' in entry and 'basic_auth_username' in entry:
            log.debug('Basic auth enabled. User: %s Password: %s' % (entry['basic_auth_username'], entry['basic_auth_password']))
            auth = (entry['basic_auth_username'], entry['basic_auth_password'])

        response = feed.requests.get(url, auth=auth, raise_status=False)
        if response.status_code != 200:
            # Save the error page
            response.encoding = None
            if response.content:
                self.save_error_page(entry, feed, response.content)
            # Raise the error
            response.raise_for_status()
            return

        # generate temp file, with random md5 sum ..
        # url alone is not random enough, it has happened that there are two entries with same url
        md5_hash = hashlib.md5('%s%s' % (url, time.time())).hexdigest()
        tmp_path = os.path.join(feed.manager.config_base, 'temp')
        if not os.path.isdir(tmp_path):
            logging.debug('creating tmp_path %s' % tmp_path)
            os.mkdir(tmp_path)
        datafile = os.path.join(tmp_path, md5_hash)

        # download and write data into a temp file
        outfile = open(datafile, 'wb')
        try:
            for chunk in response.iter_content(decode_unicode=False):
                outfile.write(chunk)
        except:
            # don't leave futile files behind
            # outfile has to be closed before we can delete it on Windows
            outfile.close()
            log.debug('Download interrupted, removing datafile')
            os.remove(datafile)
            raise
        else:
            outfile.close()
            # Do a sanity check on downloaded file
            if os.path.getsize(datafile) == 0:
                feed.fail(entry, 'File %s is 0 bytes in size' % datafile)
                return
            # store temp filename into entry so other plugins may read and modify content
            # temp file is moved into final destination at self.output
            entry['file'] = datafile
            log.debug('%s field file set to: %s' % (entry['title'], entry['file']))


        entry['mime-type'] = response.headers['content-type']

        content_encoding = response.headers.get('content-encoding', '')
        decompress = 'gzip' in content_encoding or 'deflate' in content_encoding
        if 'content-length' in response.headers and not decompress:
            entry['content-length'] = int(response.headers['content-length'])

        # prefer content-disposition naming, note: content-disposition can be disabled completely
        # by setting entry field `content-disposition` to False
        if entry.get('content-disposition', True):
            self.filename_from_headers(entry, response)
        else:
            log.info('Content-disposition disabled for %s' % entry['title'])
        self.filename_ext_from_mime(entry)
        # TODO: LAST resort, try to scrap url for filename?

    def filename_from_headers(self, entry, response):
        """Checks entry filename if it's found from content-disposition"""
        if not response.headers.get('content-disposition'):
            # No content disposition header, nothing we can do
            return
        filename = parse_header(response.headers['content-disposition'])[1].get('filename')
        
        if filename:
            # try to decode/encode, afaik this is against the specs but some servers do it anyway
            try:
                filename = filename.decode('utf-8')
                log.debug('response info UTF-8 decoded')
            except UnicodeError:
                pass
            filename = decode_html(filename)
            log.debug('Found filename from headers: %s' % filename)
            if 'filename' in entry:
                log.debug('Overriding filename %s with %s from content-disposition' % (entry['filename'], filename))
            entry['filename'] = filename

    def filename_ext_from_mime(self, entry):
        """Tries to set filename extension from mime-type"""
        extension = mimetypes.guess_extension(entry['mime-type'])
        if extension:
            log.debug('Mimetype guess for %s is %s ' % (entry['mime-type'], extension))
            if entry.get('filename'):
                if entry['filename'].endswith(extension):
                    log.debug('Filename %s extension matches to mime-type' % entry['filename'])
                else:
                    log.debug('Adding mime-type extension %s to %s' % (extension, entry['filename']))
                    entry['filename'] = entry['filename'] + extension
        else:
            log.debug('Python doesn\'t know extension for mime-type: %s' % entry['mime-type'])

    def on_feed_output(self, feed, config):
        """Move downloaded content from temp folder to final destination"""
        config = self.process_config(config)
        for entry in feed.accepted:
            try:
                self.output(feed, entry, config)
            except PluginWarning, e:
                feed.fail(entry)
                log.error('Plugin error while writing: %s' % e)
            except Exception, e:
                feed.fail(entry)
                log.exception('Exception while writing: %s' % e)

    def output(self, feed, entry, config):
        """Moves temp-file into final destination

        Raises:
            PluginError if operation fails
        """

        if 'file' not in entry and not feed.manager.options.test:
            log.debug('file missing, entry: %s' % entry)
            raise PluginError('Entry `%s` has no temp file associated with' % entry['title'])

        try:
            # use path from entry if has one, otherwise use from download definition parameter
            path = entry.get('path', config.get('path'))
            if not isinstance(path, basestring):
                raise PluginError('Invalid `path` in entry `%s`' % entry['title'])

            # override path from command line parameter
            if feed.manager.options.dl_path:
                path = feed.manager.options.dl_path

            # expand variables in path
            try:
                path = os.path.expanduser(entry.render(path))
            except RenderError, e:
                feed.fail(entry, 'Could not set path. Error during string replacement: %s' % e)
                return

            # If we are in test mode, report and return
            if feed.manager.options.test:
                log.info('Would write `%s` to `%s`' % (entry['title'], path))
                # Set a fake location, so the exec plugin can do string replacement during --test #1015
                entry['output'] = os.path.join(path, 'TEST_MODE_NO_OUTPUT')
                return

            # make path
            if not os.path.isdir(path):
                log.info('Creating directory %s' % path)
                try:
                    os.makedirs(path)
                except:
                    raise PluginError('Cannot create path %s' % path, log)

            # check that temp file is present
            if not os.path.exists(entry['file']):
                tmp_path = os.path.join(feed.manager.config_base, 'temp')
                log.debug('entry: %s' % entry)
                log.debug('temp: %s' % ', '.join(os.listdir(tmp_path)))
                raise PluginWarning('Downloaded temp file `%s` doesn\'t exist!?' % entry['file'])

            # if we still don't have a filename, try making one from title (last resort)
            if not entry.get('filename'):
                entry['filename'] = entry['title']
                log.debug('set filename from title %s' % entry['filename'])
                if not 'mime-type' in entry:
                    log.warning('Unable to figure proper filename for %s. Using title.' % entry['title'])
                else:
                    guess = mimetypes.guess_extension(entry['mime-type'])
                    if not guess:
                        log.warning('Unable to guess extension with mime-type %s' % guess)
                    else:
                        self.filename_ext_from_mime(entry)

            # combine to full path + filename, replace / from filename (replaces bc tickets #208, #325, #353)
            name = entry.get('filename', entry['title'])
            for char in '/:<>^*?~"':
                name = name.replace(char, ' ')
            # remove duplicate spaces
            name = ' '.join(name.split())
            destfile = os.path.join(path, name)
            log.debug('destfile: %s' % destfile)

            if os.path.exists(destfile):
                import filecmp
                if filecmp.cmp(entry['file'], destfile):
                    log.debug("Identical destination file '%s' already exists", destfile)
                elif config.get('overwrite'):
                    log.debug("Overwriting already existing file %s" % destfile)
                else:
                    log.info('File `%s` already exists and is not identical, download failed.' % destfile)
                    feed.fail(entry, 'File `%s` already exists and is not identical.' % destfile)
                    return
            else:
                # move temp file
                log.debug('moving %s to %s' % (entry['file'], destfile))

                try:
                    shutil.move(entry['file'], destfile)
                except OSError, err:
                    # ignore permission errors, see ticket #555
                    import errno
                    if not os.path.exists(destfile):
                        raise PluginError('Unable to write %s' % destfile)
                    if err.errno != errno.EPERM:
                        raise

            # store final destination as output key
            entry['output'] = destfile

        finally:
            self.cleanup_temp_file(entry)

    def on_feed_exit(self, feed, config):
        """Make sure all temp files are cleaned up when feed exits"""
        self.cleanup_temp_files(feed)

    def on_feed_abort(self, feed, config):
        """Make sure all temp files are cleaned up when feed is aborted."""
        self.cleanup_temp_files(feed)

    def cleanup_temp_file(self, entry):
        if 'file' in entry:
            if os.path.exists(entry['file']):
                log.debug('removing temp file %s from %s' % (entry['file'], entry['title']))
                os.remove(entry['file'])
            del(entry['file'])

    def cleanup_temp_files(self, feed):
        """Checks all entries for leftover temp files and deletes them."""
        for entry in feed.entries + feed.rejected + feed.failed:
            self.cleanup_temp_file(entry)

register_plugin(PluginDownload, 'download', api_ver=2)
register_parser_option('--dl-path', action='store', dest='dl_path', default=False,
                       metavar='PATH', help='Override path for download plugin. Applies to all executed feeds.')
