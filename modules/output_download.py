import sys, os, string, time
import urllib2
import logging
import shutil
import md5
from manager import ModuleWarning

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
        manager.register('download')
        # add new commandline parameter
        parser.add_option('--dl-path', action='store', dest='dl_path', default=False,
                          help='Override path for download module. Applies to all executed feeds.')

    def validate(self, config):
        """Validate given configuration"""
        if not isinstance(config, str):
            return ['wrong datatype']
        path = os.path.expanduser(config)
        if not os.path.exists(path):
            return ['path %s does not exists' % path]

    def validate_config(self, feed):
        # TODO: migrate into real validate!!!
        # check for invalid configuration, abort whole download if not goig to work
        # TODO: rewrite and check exists
        if not feed.config['download']:
            raise ModuleWarning('Feed %s is missing download path, check your configuration.' % feed.name)

    def feed_download(self, feed):
        """Download all feed content and store in temporary folder"""
        self.validate_config(feed) # TODO: remove
        for entry in feed.entries:
            try:
                if feed.manager.options.test:
                    log.info('Would download %s' % entry['title'])
                else:
                    feed.verbose_progress('Downloading %s' % entry['title'])
                    self.download(feed, entry)
            except urllib2.HTTPError, e:
                feed.fail(entry)
                log.error('HTTP Error: %s' % e)
            except IOError, e:
                feed.fail(entry)
                log.warning('Timed out %s' % entry['title'])
                log.exception('Execute downloads: %s' % e)
            except Exception, e:
                feed.fail(entry)
                log.exception('Execute downloads: %s' % e)

    def download(self, feed, entry):
        log.debug('Downloading url %s' % entry['url'])
        # get content
        if entry.has_key('basic_auth_password') and entry.has_key('basic_auth_username'):
            log.debug('Basic auth enabled. User: %s Password: %s' % (entry['basic_auth_username'], entry['basic_auth_password']))
            passman = urllib2.HTTPPasswordMgrWithDefaultRealm()
            passman.add_password(None, entry['url'], entry['basic_auth_username'], entry['basic_auth_password'])
            handler = urllib2.HTTPBasicAuthHandler(passman)
            opener = urllib2.build_opener(handler)
            f = opener.open(entry['url'])
        else:
            f = urllib2.urlopen(entry['url'])

        mimetype = f.headers.getsubtype()

        # generate temp file, with random md5 sum .. 
        # url alone is not random enough, it has happened that there are two entries with same url
        m = md5.new()
        m.update(entry['url'])
        m.update('%s' % time.time())
        tmp_path = os.path.join(sys.path[0], 'temp')
        if not os.path.isdir(tmp_path):
            logging.debug('creating tmp_path %s' % tmp_path)
            os.mkdir(tmp_path)
        datafile = os.path.join(tmp_path, m.hexdigest()) 

        # download and write data into a temp file
        buffer_size = 1024
        outfile = open(datafile, 'wb')
        try:
            while 1:
                data = f.read(buffer_size)
                if not data:
                    log.debug('wrote file %s' % datafile)
                    break
                outfile.write(data)
            outfile.close()
            f.close()
            # store temp filename into entry so other modules may read and modify content
            # temp file is moved into final destination at self.output
            entry['file'] = datafile
        except:
            # don't leave futile files behind
            os.remove(datafile)
            raise

        entry['mimetype'] = mimetype
        # if there is no specified filename, generate one from headers
        if not entry.has_key('filename'):
            self.set_filename(entry, f)

    def set_filename(self, entry, response):
        """Set entry['filename'] with intelligence"""
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
            log.debug('mimetypes guess for %s is %s ' % (response.headers.getsubtype(), ext))
            log.debug('Using with guessed extension: %s' % entry['filename'])
            return

    def feed_output(self, feed):
        """Move downloaded content from temp folder to final destination"""
        self.validate_config(feed)
        for entry in feed.entries:
            try:
                if feed.manager.options.test:
                    log.info('Would write entry %s' % entry['title'])
                else:
                    self.output(feed, entry)
            except ModuleWarning, e:
                feed.fail(entry)
                log.error('Error while writing: %s' % e)
            except Exception, e:
                feed.fail(entry)
                log.exception('Error while writing: %s' % e)
            # remove temp file if it remains due exceptions
            if entry.has_key('file'):
                if os.path.exists(entry['file']):
                    log.debug('removing temp file %s (left behind) from %s' % (entry['file'], entry['title']))
                    os.remove(entry['file'])

    def output(self, feed, entry):
        """Moves temp-file into final destination"""
        if not entry.has_key('file'):
            raise Exception('Entry %s has no temp file associated with' % entry['title'])
        # use path from entry if has one, otherwise use from download definition parameter
        path = entry.get('path', feed.config['download'])
        # override path from commandline parameter
        if feed.manager.options.dl_path:
            path = feed.manager.options.dl_path
        # make filename, if entry has perefered filename attribute use it, if not use title
        if not entry.has_key('filename'):
            log.warn('Unable to figure proper filename extension for %s' % entry['title'])

        destfile = os.path.join(os.path.expanduser(path), entry.get('filename', entry['title']))

        if not os.path.exists(os.path.expanduser(path)):
            raise ModuleWarning('Cannot write output file %s, does the path exist?' % destfile, log)

        if os.path.exists(destfile):
            raise ModuleWarning('File \'%s\' already exists' % destfile, log)
            
        if not os.path.exists(entry['file']):
            tmp_path = os.path.join(sys.path[0], 'temp')
            log.debug('entry: %s' % entry)
            log.debug('temp: %s' % string.join(os.listdir(tmp_path), ', '))
            raise ModuleWarning('Downloaded temp file \'%s\' doesn\'t exists!' % entry['file'])

        # move file
        shutil.move(entry['file'], destfile)
        logging.debug('moved %s to %s' % (entry['file'], destfile))
        # remove temp file from entry
        del(entry['file'])

        # TODO: should we add final filename? different key?     
