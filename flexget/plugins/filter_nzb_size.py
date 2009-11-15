import logging
from flexget.plugin import *

log = logging.getLogger('nzb_size')


class NzbSize(object):

    """
    Filter NZBs based on size.

    Example:

    nzb_size:
      min: 200
      max: 500

    Optional strict value can be used to reject all non nzb entries.

    """

    def validator(self):
        from flexget import validator
        config = validator.factory('dict')
        config.accept('number', key='min')
        config.accept('number', key='max')
        config.accept('boolean', key='strict')
        return config

    def on_feed_modify(self, feed):
        """
        The downloaded file is accessible in modify event, we'll need to perform filtering in it.
        """
        from pynzb import nzb_parser

        config = feed.config['nzb_size']

        for entry in feed.accepted:
            filename = entry['file']
            log.debug('reading %s' % filename)
            xmldata = file(filename).read()

            try:
                nzbfiles = nzb_parser.parse(xmldata)
            except:
                if config.get('strict', False):
                    feed.reject(entry, 'not a valid nzb')

            size = 0
            for nzbfile in nzbfiles:
                for segment in nzbfile.segments:
                    size += segment.bytes

            size_mb = size / 1024 / 1024

            log.debug('size: %s MB' % size_mb)

            if 'min' in config:
                if size_mb <= int(config['min']):
                    feed.reject(entry, 'nzb too small, %s MB <= %s MB' % (size_mb, config['min']))
            if 'max' in config:
                if size_mb >= int(config['min']):
                    feed.reject(entry, 'nzb too large, %s MB >= %s MB' % (size_mb, config['max']))


register_plugin(NzbSize, 'nzb_size')
