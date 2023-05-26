import mimetypes

from loguru import logger

from flexget import plugin
from flexget.event import event

logger = logger.bind(name='nzb_size')

# a bit hacky, add nzb as a known mimetype
mimetypes.add_type('application/x-nzb', '.nzb')


class NzbSize:
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
            if (
                entry.get('mime-type') in ['text/nzb', 'application/x-nzb']
                or entry.get('filename')
                and entry['filename'].endswith('.nzb')
            ):
                if 'file' not in entry:
                    logger.warning(
                        '`{}` does not have a `file` that could be used to get size information',
                        entry['title'],
                    )
                    continue

                filename = entry['file']
                logger.debug('reading {}', filename)
                xmldata = open(filename).read()

                try:
                    nzbfiles = nzb_parser.parse(xmldata)
                except Exception:
                    logger.debug('{} is not a valid nzb', entry['title'])
                    continue

                size = 0
                for nzbfile in nzbfiles:
                    for segment in nzbfile.segments:
                        size += segment.bytes

                size_mb = size / 1024 / 1024
                logger.debug('{} content size: {} MB', entry['title'], size_mb)
                entry['content_size'] = size_mb
            else:
                logger.trace('{} does not seem to be nzb', entry['title'])


@event('plugin.register')
def register_plugin():
    plugin.register(NzbSize, 'nzb_size', api_ver=2, builtin=True)
