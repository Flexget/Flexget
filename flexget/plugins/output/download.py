import os
import time
import urllib
import urllib2
import logging
from flexget.plugin import register_plugin, register_parser_option, get_plugin_by_name, PluginWarning, PluginError
from httplib import BadStatusLine
from flexget.utils.tools import urlopener, replace_from_entry
import mimetypes

log = logging.getLogger('download')


class PluginDownload(object):

    """
        Downloads content from entry url and writes it into a file.

        Example:

        download: ~/torrents/

        Allow HTML content:

        By default download plugin reports failure if received content
        is a html. Usually this is some sort of custom error page without
        proper http code and thus entry is assumed to be downloaded
        incorrectly.

        In the rare case you actually need to retrieve html-pages you must
        disable this feature.

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

    def get_config(self, feed):
        """Return plugin configuration in advanced form"""
        config = feed.config['download']
        if isinstance(config, basestring):
            config = {'path': config}
        if not isinstance(config, dict):
            config = {}
        config.setdefault('fail_html', True)
        if not config.get('path'):
            config['require_path'] = True
        return config

    def on_process_start(self, feed):
        """Register the usable set keywords."""
        set_plugin = get_plugin_by_name('set')
        set_plugin.instance.register_keys({'path': 'text'})

    def on_feed_download(self, feed):
        config = self.get_config(feed)
        self.get_temp_files(feed, require_path=config.get('require_path', False), fail_html=config['fail_html'])

    def get_temp_file(self, feed, entry, require_path=False, handle_magnets=False, fail_html=True):
        """Download entry content and store in temporary folder.

        :require_path: whether or not entries without 'path' field are ignored
        :handle_magnets: when used any of urls containing magnet link will replace url, otherwise warning is printed.
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

    def get_temp_files(self, feed, require_path=False, handle_magnets=False, fail_html=True):
        """Download all feed content and store in temporary folder.

        :require_path: whether or not entries without 'path' field are ignored
        :handle_magnets: when used any of urls containing magnet link will replace url, otherwise warning is printed.
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
        except urllib2.HTTPError, e:
            log.warning('HTTPError %s' % e.code)
            return 'HTTP error'
        except urllib2.URLError, e:
            log.warning('URLError %s' % e.reason)
            return 'URL Error'
        except BadStatusLine, e:
            log.warning('Failed to reach server. Reason: %s' % e.reason)
            return 'BadStatusLine'
        except IOError, e:
            if hasattr(e, 'reason'):
                log.warning('Failed to reach server. Reason: %s' % e.reason)
            elif hasattr(e, 'code'):
                log.warning('The server couldn\'t fulfill the request. Error code: %s' % e.code)
            return 'IOError'
        except ValueError, e:
            # Probably unknown url type
            log.warning(e.message)
            return e.message

    def download_entry(self, feed, entry, url):
        """Downloads :entry: by using :url:.
        May raise several types of exception(s) or PluginWarning"""

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
        if 'basic_auth_password' in entry and 'basic_auth_username' in entry:
            log.debug('Basic auth enabled. User: %s Password: %s' % (entry['basic_auth_username'], entry['basic_auth_password']))
            passman = urllib2.HTTPPasswordMgrWithDefaultRealm()
            passman.add_password(None, url, entry['basic_auth_username'], entry['basic_auth_password'])
            handlers = [urllib2.HTTPBasicAuthHandler(passman)]
        else:
            handlers = None

        opener = urlopener(url, log, handlers=handlers)
        if opener.headers.get('content-encoding') in ('gzip', 'x-gzip', 'deflate'):
            import zlib
            decompress = zlib.decompressobj(15 + 32).decompress
        else:
            decompress = None

        # generate temp file, with random md5 sum ..
        # url alone is not random enough, it has happened that there are two entries with same url
        import hashlib
        m = hashlib.md5()
        m.update(url)
        m.update('%s' % time.time())
        tmp_path = os.path.join(feed.manager.config_base, 'temp')
        if not os.path.isdir(tmp_path):
            logging.debug('creating tmp_path %s' % tmp_path)
            os.mkdir(tmp_path)
        datafile = os.path.join(tmp_path, m.hexdigest())

        def read_chunks(data, buffer_size=1024):
            """ Helper generator to iterate over data in chunks """
            while True:
                chunk = data.read(buffer_size)
                if not chunk:
                    break
                yield chunk

        # download and write data into a temp file
        try:
            outfile = open(datafile, 'wb')
            try:
                for chunk in read_chunks(opener):
                    outfile.write(decompress(chunk) if decompress else chunk)
            except:
                # don't leave futile files behind
                # outfile has to be closed before we can delete it on Windows
                outfile.close()
                log.debug('Download interrupted, removing datafile')
                os.remove(datafile)
                raise
            outfile.close()
            # store temp filename into entry so other plugins may read and modify content
            # temp file is moved into final destination at self.output
            entry['file'] = datafile
            log.debug('%s field file set to: %s' % (entry['title'], entry['file']))
        finally:
            opener.close()

        entry['mime-type'] = opener.headers.gettype()

        if 'content-length' in opener.headers and not decompress:
            entry['content-length'] = int(opener.headers.get('content-length'))

        # prefer content-disposition naming, note: content-disposition can be disabled completely
        # by setting entry field `content-disposition` to False
        if entry.get('content-disposition', True):
            self.filename_from_headers(entry, opener)
        else:
            log.info('Content-disposition disabled for %s' % entry['title'])
        self.filename_ext_from_mime(entry)
        # TODO: LAST resort, try to scrap url for filename?

    def filename_from_headers(self, entry, response):
        """Checks entry filename if it's found from content-disposition"""
        from flexget.utils.tools import encode_html, decode_html
        import email

        data = str(response.info())

        # try to decode/encode, afaik this is against the specs but some servers do it anyway
        try:
            data = data.decode('utf-8')
            log.debug('response info UTF-8 decoded')
        except UnicodeError:
            try:
                data = unicode(data)
                log.debug('response info unicoded')
            except UnicodeError:
                pass

        # now we should have unicode string, let's convert into proper format where non-ascii
        # chars are entities
        data = encode_html(data)
        try:
            filename = email.message_from_string(data).get_filename(failobj=False)
        except (AttributeError, SystemExit, KeyboardInterrupt):
            raise # at least rethrow the most common stuff before catch-all
        except:
            log.error('Failed to decode filename from response: %r' % data)
            return
        if filename:
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

    def on_feed_output(self, feed):
        """Move downloaded content from temp folder to final destination"""
        for entry in feed.accepted:
            try:
                self.output(feed, entry)
            except PluginWarning, e:
                feed.fail(entry)
                log.error('Plugin error while writing: %s' % e)
            except Exception, e:
                feed.fail(entry)
                log.exception('Exception while writing: %s' % e)

    def output(self, feed, entry):
        """Moves temp-file into final destination"""

        config = self.get_config(feed)

        if 'file' not in entry and not feed.manager.options.test:
            log.debug('file missing, entry: %s' % entry)
            raise PluginError('Entry %s has no temp file associated with' % entry['title'])

        try:
            # use path from entry if has one, otherwise use from download definition parameter
            path = entry.get('path', config.get('path'))
            if path is None:
                raise PluginError('Unreachable situation?')

            # override path from command line parameter
            if feed.manager.options.dl_path:
                path = feed.manager.options.dl_path

            # expand variables in path
            path = replace_from_entry(path, entry, 'path', log.error)
            if not path:
                feed.fail(entry, 'Could not set path. Does not contain all fields for string replacement.')
                return
            path = os.path.expanduser(path)

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
                raise PluginWarning("Downloaded temp file '%s' doesn't exist!?" % entry['file'])

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

            # combine to full path + filename, replace / from filename (replaces: #208, #325, #353)
            name = entry.get('filename', entry['title'])
            for char in '/:<>^*?~':
                name = name.replace(char, ' ')
            # remove duplicate spaces
            name = ' '.join(name.split())
            destfile = os.path.join(path, name)
            log.debug('destfile: %s' % destfile)

            if os.path.exists(destfile):
                import filecmp
                if filecmp.cmp(entry['file'], destfile):
                    log.debug("Identical destination file '%s' already exists", destfile)
                    return
                elif config.get('overwrite'):
                    log.debug("Overwriting already existing file %s" % destfile)
                else:
                    log.info('File \'%s\' already exists and is not identical, download failed.' % destfile)
                    feed.fail(entry, 'File \'%s\' already exists and is not identical.' % destfile)
                    return

            # move temp file
            log.debug('moving %s to %s' % (entry['file'], destfile))

            try:
                import shutil
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

    def on_feed_exit(self, feed):
        """Make sure all temp files are cleaned up when feed exits"""
        self.cleanup_temp_files(feed)

    def on_feed_abort(self, feed):
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

register_plugin(PluginDownload, 'download')
register_parser_option('--dl-path', action='store', dest='dl_path', default=False,
                       metavar='PATH', help='Override path for download plugin. Applies to all executed feeds.')
