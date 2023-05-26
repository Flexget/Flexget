from urllib.parse import parse_qs, urlencode, urlparse

from loguru import logger
from requests.exceptions import RequestException

from flexget import plugin
from flexget.components.sites.urlrewriting import UrlRewritingError
from flexget.event import event

logger = logger.bind(name='rutracker')


class SiteRutracker:
    schema = {'type': 'boolean'}

    base_url = 'https://api.t-ru.org'

    # urlrewriter API
    def url_rewritable(self, task, entry):
        url = entry['url']
        return url.startswith('https://rutracker.org/forum/viewtopic.php?t=')

    @plugin.internet(logger)
    def url_rewrite(self, task, entry):
        """
        Gets torrent information for topic from rutracker api
        """

        url = entry['url']
        logger.info('rewriting download url: {}', url)

        topic_id = parse_qs(urlparse(url).query)['t'][0]

        api_url = f"{self.base_url}/v1/get_tor_topic_data"
        api_params = {
            'by': 'topic_id',
            'val': topic_id,
        }
        try:
            topic_request = task.requests.get(api_url, params=api_params)
        except RequestException as e:
            raise UrlRewritingError(f'rutracker request failed: {e}')

        topic = topic_request.json()['result'][topic_id]

        magnet = {
            'xt': f"urn:btih:{topic['info_hash']}",
            'tr': [f'http://bt{i}.t-ru.org/ann?magnet' for i in ['', '2', '3', '4']],
            'dn': topic['topic_title'],
        }
        magnet_qs = urlencode(magnet, doseq=True, safe=':')
        magnet_uri = f"magnet:?{magnet_qs}"
        entry['url'] = magnet_uri


@event('plugin.register')
def register_plugin():
    plugin.register(SiteRutracker, 'rutracker', interfaces=['urlrewriter'], api_ver=2)
