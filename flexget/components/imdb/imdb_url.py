import re

from loguru import logger

from flexget import plugin
from flexget.components.imdb.utils import extract_id, make_url
from flexget.event import event

logger = logger.bind(name='metainfo_imdb_url')


class MetainfoImdbUrl:
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
            if not entry.get('description'):
                continue
            urls = re.findall(r'\bimdb.com/title/tt\d+\b', entry['description'])
            # Find unique imdb ids
            imdb_ids = [_f for _f in set(extract_id(url) for url in urls) if _f]
            if not imdb_ids:
                continue

            if len(imdb_ids) > 1:
                logger.debug('Found multiple imdb ids; not using any of: {}', ' '.join(imdb_ids))
                continue

            entry['imdb_id'] = imdb_ids[0]
            entry['imdb_url'] = make_url(entry['imdb_id'])
            logger.debug('Found imdb url in description {}', entry['imdb_url'])


@event('plugin.register')
def register_plugin():
    plugin.register(MetainfoImdbUrl, 'scan_imdb', builtin=True, api_ver=2)
