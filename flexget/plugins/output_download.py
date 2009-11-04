import os
import time
import urllib
import urllib2
import logging
import shutil
import filecmp
from flexget.plugin import *
from sqlalchemy import Column, String, Integer, DateTime
from flexget.manager import Base
from datetime import datetime

log = logging.getLogger('download')

class Download(Base):

    __tablename__ = 'download_history'
    
    id = Column(Integer, primary_key=True)
    feed = Column(String)
    filename = Column(String)
    url = Column(String)
    title = Column(String)
    time = Column(DateTime)
    details = Column(String)
    
    def __init__(self):
        self.time = datetime.now()
    
    def __str__(self):
        return '<Download(filename=%s,feed=%s)>' % (self.filename, self.feed)


class PluginDownloads:

    """
        Provides --downloads
    """

    def on_process_start(self, feed):

        # temp hack for database change
        from flexget.manager import Session
        from flexget.utils.sqlalchemy_utils import table_columns, table_schema
        columns = table_columns('download_history', Session())
        if not 'details' in columns:
            log.critical('Please see bleeding edge news for neccessary actions')
            log.critical('Re-cap run: sqlite3 %s "drop table download_history;"' % feed.manager.db_filename)
            import sys
            sys.exit(1)

        if feed.manager.options.downloads:
            from flexget.manager import Session
            feed.manager.disable_feeds()
            session = Session()
            print '-- Downloads: ' + '-' * 65
            for download in session.query(Download).order_by(Download.time)[-50:]:
                print ' Title   : %s' % download.title
                print ' Url     : %s' % download.url
                print ' Stored  : %s' % download.filename
                print ' Time    : %s' % download.time.strftime("%c")
                if feed.manager.options.details:
                    print ' Details : %s' % download.details
                print '-' * 79
            session.close()


class PluginDownload:

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
        root.accept('path')
        advanced = root.accept('dict')
        advanced.accept('path', key='path')
        advanced.accept('boolean', key='fail_html')
        return root

    def on_feed_download(self, feed):
        """Download all feed content and store in temporary folder"""
        for entry in feed.accepted:
            try:
                if feed.manager.options.test:
                    log.info('Would download: %s' % entry['title'])
                else:
                    if not feed.manager.unit_test:
                        log.info('Downloading: %s' % entry['title'])
                    self.download(feed, entry)
            except IOError, e:
                feed.fail(entry)
                if hasattr(e, 'reason'):
                    log.error('Failed to reach server. Reason: %s' % e.reason)
                elif hasattr(e, 'code'):
                    log.error('The server couldn\'t fulfill the request. Error code: %s' % e.code)

    def download(self, feed, entry):
        url = urllib.quote(entry['url'].encode('latin1'), safe=':/~?=&%')
        log.debug('Downloading url \'%s\'' % url)
        # get content
        if 'basic_auth_password' in entry and 'basic_auth_username' in entry:
            # TODO: should just add handler if default opener is present, now this will lose all other
            # handlers that other plugins have potentialy added
            log.debug('Basic auth enabled. User: %s Password: %s' % (entry['basic_auth_username'], entry['basic_auth_password']))
            passman = urllib2.HTTPPasswordMgrWithDefaultRealm()
            passman.add_password(None, url, entry['basic_auth_username'], entry['basic_auth_password'])
            handler = urllib2.HTTPBasicAuthHandler(passman)
            opener = urllib2.build_opener(handler)
            f = opener.open(url)
        else:
            if urllib2._opener:
                handlers = [h.__class__.__name__ for h in urllib2._opener.handlers]
                log.debug('default opener present, handlers: %s' % ', '.join(handlers))
            f = urllib2.urlopen(url)

        mimetype = f.headers.gettype()

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
            # store temp filename into entry so other plugins may read and modify content
            # temp file is moved into final destination at self.output
            entry['file'] = datafile
        except:
            # don't leave futile files behind
            os.remove(datafile)
            raise

        entry['mime-type'] = mimetype
        # prefer content-disposition naming
        self.filename_from_headers(entry, f)
        # if there is still no specified filename, use mime-type
        #if not 'filename' in entry:
        #that check is made by filename_from_mime
        self.filename_from_mime(entry)
        # TODO: LAST option, try to scrap url?

    def filename_from_headers(self, entry, response):
        """Checks entry filename if it's found from content-disposition"""
        from flexget.utils.tools import encode_html, decode_html
        import email

        data = str(response.info())
        
        # try to decode/encode, afaik this is against the specs but some servers do it anyway
        try:
            data = data.decode('utf-8')
            log.debug('response info UTF-8 decoded')
        except:
            try:
                data = unicode(data)
                log.debug('response info unicoded')
            except:
                pass
        
        # now we should have unicode string, let's convert into proper format where non-ascii 
        # chars are entities
        data = encode_html(data)
        
        try:
            filename = email.message_from_string(data).get_filename(failobj=False)
        except:
            log.error('Failed to decode filename from response: %s' % ''.join(['%02x' % ord(x) for x in data]))
            return
        if filename:
            filename = decode_html(filename)
            log.debug('Found filename from headers: %s' % filename)
            if 'filename' in entry:
                log.debug('Overriding filename %s with %s from content-disposition' % (entry['filename'], filename))
            entry['filename'] = filename

    def filename_from_mime(self, entry):
        """Tries to set filename (extensions) from mime-type"""
        import mimetypes
        extension = mimetypes.guess_extension(entry['mime-type'])
        if extension:
            log.debug('Mimetypes guess for %s is %s ' % (entry['mime-type'], extension))
            if 'filename' in entry:
                if entry['filename'].endswith('%s' % extension):
                    log.debug('Filename %s extension matches to mime-type' % entry['filename'])
                else:
                    log.debug('Adding mime-type extension %s to %s' % (extension, entry['filename']))
                    entry['filename'] = '%s%s' % (entry['filename'], extension)
        else:
            log.debug('Python doesn\'t know extension for mime-type: %s' % entry['mime-type'])

    def on_feed_output(self, feed):
        """Move downloaded content from temp folder to final destination"""
        for entry in feed.accepted:
            try:
                if feed.manager.options.test:
                    log.info('Would write: %s' % entry['title'])
                else:
                    self.output(feed, entry)
            except PluginWarning, e:
                feed.fail(entry)
                log.error('Plugin error while writing: %s' % e)
            except Exception, e:
                feed.fail(entry)
                log.exception('Exception while writing: %s' % e)

    def output(self, feed, entry):
        """Moves temp-file into final destination"""

        if not 'file' in entry:
            raise Exception('Entry %s has no temp file associated with' % entry['title'])

        try:
            # convert config into advanced form
            config = feed.config['download']
            if not isinstance(config, dict):
                config = {}
                config['path'] = feed.config['download']
                config['fail_html'] = True
                
            # use path from entry if has one, otherwise use from download definition parameter
            path = entry.get('path', config['path'])
            # override path from commandline parameter
            if feed.manager.options.dl_path:
                path = feed.manager.options.dl_path

            # make filename, if entry has perefered filename attribute use it, if not use title
            if not 'filename' in entry:
                html_mimes = ['html', 'text/html']
                if entry.get('mime-type') in html_mimes and config['fail_html']:
                    feed.fail(entry, 'unexpected html content')
                    log.error('Unexpected html content received from %s' % entry['url'])
                    return
                else:
                    log.warning('Unable to figure proper filename / extension for %s, using title. Mime-type: %s' % (entry['title'], entry.get('mime-type', 'N/A')))
                    # try to append an extension to the title
                    entry['filename'] = entry['title']
                    self.filename_from_mime(entry)

            # make path
            path = os.path.expanduser(path)

            if not os.path.exists(path):
                log.info('Creating directory %s' % path)
                try:
                    os.mkdir(path)
                except:
                    raise PluginError('Cannot create path %s' % path, log)
            
            # check that temp file is present
            if not os.path.exists(entry['file']):
                tmp_path = os.path.join(feed.manager.config_base, 'temp')
                log.debug('entry: %s' % entry)
                log.debug('temp: %s' % ', '.join(os.listdir(tmp_path)))
                raise PluginWarning("Downloaded temp file '%s' doesn't exist!?" % entry['file'])

            # combine to full path + filename, replace / from filename (replaces: #208, #325, #353)
            name = entry.get('filename', entry['title'])
            for char in '/:<>^*?~':
                name = name.replace(char, ' ')
            # remove duplicate spaces
            name = ' '.join(name.split())
            destfile = os.path.join(path, name)

            if os.path.exists(destfile):
                if filecmp.cmp(entry['file'], destfile):
                    logging.debug("Identical destination file '%s' already exists", destfile)
                    feed.fail(entry, 'Identical file \'%s\' already exists' % destfile)
                    return
                else:
                    # TODO: Rethink the best course of action in this case.
                    log.info('File \'%s\' already exists and is not identical, download failed.' % destfile)
                    feed.fail(entry, 'File \'%s\' already exists and is not identical.' % destfile)
                    return
            
            # move temp file
            logging.debug('moving %s to %s' % (entry['file'], destfile))
            shutil.move(entry['file'], destfile)

            # store final destination as output key
            entry['output'] = destfile
            
            # add to download history
            download = Download()
            download.feed = feed.name
            download.filename = destfile
            download.title = entry['title']
            download.url = entry['url']
            reason = ''
            if 'reason' in entry:
                reason = ' (reason: %s)' % entry['reason']
            download.details = 'Accepted by %s%s' % (entry.get('accepted_by', '<unknown>'), reason)
            feed.session.add(download)
            
            # test
            import time
            time.sleep(2)

        finally:
            if os.path.exists(entry['file']):
                log.debug('removing temp file %s from %s' % (entry['file'], entry['title']))
                os.remove(entry['file'])
            del(entry['file'])

register_plugin(PluginDownload, 'download')
register_plugin(PluginDownloads, 'downloads', builtin=True)
register_parser_option('--dl-path', action='store', dest='dl_path', default=False,
                       metavar='PATH', help='Override path for download plugin. Applies to all executed feeds.')
register_parser_option('--downloads', action='store_true', dest='downloads', default=False,
                       help='List latest downloads (50).')