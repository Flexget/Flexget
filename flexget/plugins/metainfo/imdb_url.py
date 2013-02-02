from __future__ import unicode_literals, division, absolute_import
import re
import logging
from flexget.plugin import register_plugin

log = logging.getLogger('metainfo_imdb_url')


class MetainfoImdbUrl(object):
    """
        Scan entry information for imdb url.
    """

    def validator(self):
        from flexget import validator
        return validator.factory('boolean')

    def on_task_metainfo(self, task):
        # check if disabled (value set to false)
        if 'scan_imdb' in task.config:
            if not task.config['scan_imdb']:
                return

        for entry in task.entries:
            if not 'description' in entry:
                continue
            urls = re.findall(r'\bimdb.com/title/tt\d+\b', entry['description'])
            if not urls:
                continue

            # Uniquify the list of urls.
            urls = list(set(urls))
            if 1 < len(urls):
                log.debug('Found multiple imdb urls; not using any of: %s' %
                    ' '.join(urls))
                continue

            url = ''.join(['http://www.', urls[0]])
            entry['imdb_url'] = url
            log.debug('Found imdb url in description %s' % url)

register_plugin(MetainfoImdbUrl, 'scan_imdb', builtin=True)
