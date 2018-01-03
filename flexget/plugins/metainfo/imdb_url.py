from __future__ import unicode_literals, division, absolute_import
from builtins import *  # noqa pylint: disable=unused-import, redefined-builtin

import re
import logging

from flexget import plugin
from flexget.event import event
from flexget.utils.imdb import extract_id, make_url

log = logging.getLogger('metainfo_imdb_url')


class MetainfoImdbUrl(object):
    """
        Scan entry information for imdb url.
    """

    schema = {'type': 'boolean'}

    def on_task_metainfo(self, task, config):
        # check if disabled (value set to false)
        if 'scan_imdb' in task.config:
            if not task.config['scan_imdb']:
                return

        for entry in task.entries:
            # Don't override already populated imdb_ids
            if entry.get('imdb_id', eval_lazy=False):
                continue
            if 'description' not in entry:
                continue
            urls = re.findall(r'\bimdb.com/title/tt\d+\b', entry['description'])
            # Find unique imdb ids
            imdb_ids = [_f for _f in set(extract_id(url) for url in urls) if _f]
            if not imdb_ids:
                continue

            if len(imdb_ids) > 1:
                log.debug('Found multiple imdb ids; not using any of: %s' % ' '.join(imdb_ids))
                continue

            entry['imdb_id'] = imdb_ids[0]
            entry['imdb_url'] = make_url(entry['imdb_id'])
            log.debug('Found imdb url in description %s' % entry['imdb_url'])


@event('plugin.register')
def register_plugin():
    plugin.register(MetainfoImdbUrl, 'scan_imdb', builtin=True, api_ver=2)
