import logging
from flexget.plugin import register_plugin, priority, DependencyError

log = logging.getLogger('nzb_size')

# a bit hacky, add nzb as a known mimetype
import mimetypes
mimetypes.add_type('application/x-nzb', '.nzb')


class NzbSize(object):

    """
    Provides entry size information when dealing with nzb files
    """

    @priority(200)
    def on_feed_modify(self, feed):
        """
        The downloaded file is accessible in modify phase
        """
        try:
            from pynzb import nzb_parser
        except ImportError:
            # TODO: remove builtin status so this won't get repeated on every feed execution
            # TODO: this will get loaded even without any need for nzb
            raise DependencyError(issued_by='nzb_size', missing='lib pynzb')

        for entry in feed.accepted:
            if entry.get('mime-type', None) in [u'text/nzb', u'application/x-nzb'] or \
               entry.get('filename', '').endswith('.nzb'):

                if 'file' not in entry:
                    log.warning('%s does not have a to get size from' % entry['title'])
                    continue

                filename = entry['file']
                log.debug('reading %s' % filename)
                xmldata = file(filename).read()

                try:
                    nzbfiles = nzb_parser.parse(xmldata)
                except:
                    log.debug('%s is not a valid nzb' % entry['title'])
                    continue

                size = 0
                for nzbfile in nzbfiles:
                    for segment in nzbfile.segments:
                        size += segment.bytes

                size_mb = size / 1024 / 1024
                log.debug('%s content size: %s MB' % (entry['title'], size_mb))
                entry['content_size'] = size_mb
            else:
                log.trace('%s does not seem to be nzb' % entry['title'])


register_plugin(NzbSize, 'nzb_size', builtin=True)
