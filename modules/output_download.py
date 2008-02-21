import yaml
import re
import os, sys
import urllib
import logging

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

        How it works behind the scenes:

        Module downloads url content into entry at the request phase,
        actual file is written at output. This is done in two phases
        because this way other modules may modify or reject content.
        If entry has filename attribute it is used, if not mandatory
        attribute title is used.
    """

    def register(self, manager, parser):
        manager.register(instance=self, event="download", keyword="download", callback=self.execute_downloads)
        manager.register(instance=self, event="output", keyword="download", callback=self.execute_outputs)

    def validate_config(self, feed):
        # check for invalid configuration, abort whole download if not goig to work
        if not feed.config["download"]:
            raise Exception('Feed %s is missing download path, check your configuration.' % feed.name)

    def execute_downloads(self, feed):
        self.validate_config(feed)
        for entry in feed.entries:
            try:
                if feed.manager.options.test:
                    log.info("Would download %s" % entry['title'])
                else:
                    self.download(feed, entry)
            except IOError, e:
                feed.failed(entry)
                log.warning("Download of %s timed out" % entry['title']);
            except Exception, e:
                # notify framework that outputing this entry failed
                feed.failed(entry)
                log.exception('Execute downloads: %s' % e)

    def download(self, feed, entry):
        # get content
        # urllib2 is too smart here, it borks on basic auth urls
        f = urllib.urlopen(entry['url'])
        mimetype = f.headers.getsubtype()
        content = f.read()
        f.close()
        # store data and mimetype for entry
        entry['data'] = content
        entry['mimetype'] = mimetype

    def execute_outputs(self, feed):
        self.validate_config(feed)
        for entry in feed.entries:
            try:
                if feed.manager.options.test:
                    log.info("Would write entry %s" % entry['title'])
                else:
                    self.output(feed, entry)
            except Warning, e:
                # different handling because IOError is "ok"
                log.warning('Error while writing: %s' % e)
            except Exception, e:
                feed.failed(entry)
                log.exception('Error while writing: %s' % e)

    def output(self, feed, entry):
        """Writes entry.data into file"""
        if not entry.has_key('data'):
            raise Exception('Entry %s has no data' % entry['title'])
        # use path from entry if has one, otherwise use from download definition parameter
        path = entry.get('path', feed.config["download"])
        # make filename, if entry has perefered filename attribute use it, if not use title
        destfile = os.path.join(os.path.expanduser(path), entry.get('filename', entry['title']))
        if not os.path.exists(destfile):
            f = file(destfile, 'w')
            f.write(entry['data'])
            f.close()
        else:
            raise Warning("File '%s' already exists" % destfile)
