import os.path
import re
from pathlib import Path

from loguru import logger

from flexget import plugin
from flexget.event import event
from flexget.utils.tools import format_filesize, parse_filesize

logger = logger.bind(name='metanfo_csize')

SIZE_RE = re.compile(r'Size[^\d]{0,7}(\d*\.?\d+).{0,5}(MB|GB)', re.IGNORECASE | re.UNICODE)


class MetainfoContentSize:
    """
    Utility:

    Check if content size is mentioned in description and set content_size attribute for entries if it is.
    Also sets content_size for entries with local files from input_listdir.
    """

    schema = {'type': 'boolean', 'default': False}

    def on_task_metainfo(self, task, config):
        # check if disabled (value set to false)
        if config is False:
            return

        count = 0
        for entry in task.entries:
            if entry.get('content_size'):
                # Don't override if already set
                logger.trace(
                    'skipping content size check because it is already set for {!r}',
                    entry['title'],
                )
                continue
            # Try to parse size from description
            description = entry.get('description', '')
            if isinstance(description, str):
                try:
                    entry['content_size'] = parse_filesize(description, si=False, match_re=SIZE_RE)
                    continue
                except ValueError:
                    pass
            # If this entry has a local file, (it was added by filesystem plugin) grab the size.
            if entry.get('location'):
                # If it is a .torrent or .nzb, don't bother getting the size as it will not be the content's size
                location = entry['location']
                if isinstance(location, str):
                    location = Path(location)
                if location.suffix in ('.nzb', '.torrent'):
                    continue
                try:
                    if location.is_file():
                        amount = os.path.getsize(entry['location'])
                        logger.trace('setting content size to {}', format_filesize(amount))
                        entry['content_size'] = amount
                        continue
                except OSError:
                    # is_file can throw OSError for invalid paths (at least on windows)
                    continue

        if count:
            logger.debug('Found content size information from {} entries', count)


@event('plugin.register')
def register_plugin():
    plugin.register(MetainfoContentSize, 'metainfo_content_size', builtin=True, api_ver=2)
