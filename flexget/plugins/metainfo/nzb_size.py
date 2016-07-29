from __future__ import unicode_literals, division, absolute_import
from builtins import *  # pylint: disable=unused-import, redefined-builtin

import logging
import mimetypes

from flexget import plugin
from flexget.event import event

log = logging.getLogger('nzb_size')

# a bit hacky, add nzb as a known mimetype
mimetypes.add_type('application/x-nzb', '.nzb')


class NzbSize(object):
    """
    Provides entry size information when dealing with nzb files
    """

    @plugin.priority(200)
    def on_task_modify(self, task, config):
        """
        The downloaded file is accessible in modify phase
        """
        try:
            from pynzb import nzb_parser
        except ImportError:
            # TODO: remove builtin status so this won't get repeated on every task execution
            # TODO: this will get loaded even without any need for nzb
            raise plugin.DependencyError(issued_by='nzb_size', missing='lib pynzb')

        for entry in task.accepted:
            if entry.get('mime-type', None) in [u'text/nzb', u'application/x-nzb'] or \
                    entry.get('filename', '').endswith('.nzb'):

                if 'file' not in entry:
                    log.warning('`%s` does not have a `file` that could be used to get size information' %
                                entry['title'])
                    continue

                filename = entry['file']
                log.debug('reading %s' % filename)
                xmldata = open(filename).read()

                try:
                    nzbfiles = nzb_parser.parse(xmldata)
                except Exception:
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


@event('plugin.register')
def register_plugin():
    plugin.register(NzbSize, 'nzb_size', api_ver=2, builtin=True)
