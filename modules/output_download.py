import os
import urllib2
import logging

__pychecker__ = 'unusednames=parser,feed'

log = logging.getLogger('download')

class ModuleDownload:

    """
        Downloads content from entry url and writes it into a file.
        Simple example:

        download: ~/torrents/

        Advanced users:

        Some modules may set an alternative download path for entry.
        Prime example is module patterns that can be used to override path.

        Configuration example:
        
        pattenrs:
          - pattern1
          - pattern2
          - pattern3: ~/another_location/
        download: ~/torrents/

        This results that entries matching patterns 1 and 2 are saved into
        ~/torrents/ and pattern3 is saved to ~/another_location/.
        
        You may use commandline parameter --dl-path to temporarily override 
        all paths to another location.
    """

    def register(self, manager, parser):
        manager.register(instance=self, event="download", keyword="download", callback=self.execute_downloads)
        manager.register(instance=self, event="output", keyword="download", callback=self.execute_outputs)
        # add new commandline parameter
        parser.add_option("--dl-path", action="store", dest="dl_path", default=False,
                          help="Override path for download module. Applies to all executed feeds.")

    def validate_config(self, feed):
        # check for invalid configuration, abort whole download if not goig to work
        # TODO: rewrite and check exists
        if not feed.config['download']:
            raise Warning('Feed %s is missing download path, check your configuration.' % feed.name)

    def execute_downloads(self, feed):
        self.validate_config(feed)
        for entry in feed.entries:
            try:
                if feed.manager.options.test:
                    log.info('Would download %s' % entry['title'])
                else:
                    self.download(feed, entry)
            except IOError, e:
                feed.failed(entry)
                log.warning('Download of %s timed out' % entry['title']);
            except Exception, e:
                # notify framework that outputing this entry failed
                feed.failed(entry)
                log.exception('Execute downloads: %s' % e)

    def download(self, feed, entry):
        # get content
        if entry.has_key('basic_auth_password') and entry.has_key('basic_auth_username'):
            log.debug('Basic auth enabled')
            auth_handler = urllib2.HTTPPasswordMgrWithDefaultRealm()
            auth_handler.add_password(None, entry['url'], entry['basic_auth_username'], entry['basic_auth_password'])
            opener = urllib2.build_opener(auth_handler)
            f = opener.open(entry['url'])
        else:
            f = urllib2.urlopen(entry['url'])

        mimetype = f.headers.getsubtype()
        content = f.read()
        f.close()
        # store data and mimetype for entry
        entry['data'] = content
        entry['mimetype'] = mimetype
        # if there is no specified filename, generate one from headers
        if not entry.has_key('filename'):
            self.set_filename(entry, f)

    def set_filename(self, entry, response):
        # check from content-disposition
        import email
        filename = email.message_from_string(unicode(response.info()).encode('utf-8')).get_filename(failobj=False)
        if filename:
            # TODO: must be hmtl decoded!
            log.debug('Found filename from headers: %s' % filename)
            entry['filename'] = filename
            return
        # guess extension from content-type
        import mimetypes
        ext = mimetypes.guess_extension(response.headers.getsubtype())
        if ext:
            entry['filename'] = entry['title'] + ext
            log.debug('mimetypes guess for %s is %s ' % (response.headers.getsubtype(), guess))
            log.debug('Using with guessed extension: %s' % entry['filename'])
            return
        

    def execute_outputs(self, feed):
        self.validate_config(feed)
        for entry in feed.entries:
            try:
                if feed.manager.options.test:
                    log.info('Would write entry %s' % entry['title'])
                else:
                    self.output(feed, entry)
                    feed.verbose_details('Downloaded %s' % entry['title'])
            except Warning, e:
                # different handling because IOError is "ok"
                log.warning('Error while writing: %s' % e)
            except Exception, e:
                feed.failed(entry)
                log.exception('Error while writing: %s' % e)

    def output(self, feed, entry):
        """Writes entry.data into a file"""
        if not entry.has_key('data'):
            raise Exception('Entry %s has no data' % entry['title'])
        # use path from entry if has one, otherwise use from download definition parameter
        path = entry.get('path', feed.config['download'])
        # override path from commandline parameter
        if feed.manager.options.dl_path:
            path = feed.manager.options.dl_path
        # make filename, if entry has perefered filename attribute use it, if not use title
        if not entry.has_key('filename'):
            log.warn('Unable to figure proper filename extension for %s' % entry['title'])
        destfile = os.path.join(os.path.expanduser(path), entry.get('filename', entry['title']))
        if os.path.exists(destfile):
            raise Warning("File '%s' already exists" % destfile)
        # write file
        try:
            f = file(destfile, 'w')
            f.write(entry['data'])
            f.close()
        except:
            # remove failed write
            os.remove(destfile)
            log.error('Invalid data object: type: %s repr: %s' % (type(entry['data']), repr(entry['data'])) )
            raise
