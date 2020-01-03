import re

from loguru import logger
from requests.exceptions import RequestException

from flexget import plugin
from flexget.components.sites.urlrewriting import UrlRewritingError
from flexget.components.sites.utils import normalize_unicode
from flexget.event import event
from flexget.utils.soup import get_soup

logger = logger.bind(name='rmz')


class UrlRewriteRmz:
    r"""
    rmz.cr (rapidmoviez.com) urlrewriter
    Version 0.1

    Configuration

    rmz:
      filehosters_re:
        - domain\.com
        - domain2\.org

    Only add links that match any of the regular expressions listed under filehosters_re.

    If more than one valid link is found, the url of the entry is rewritten to
    the first link found. The complete list of valid links is placed in the
    'urls' field of the entry.

    Therefore, it is recommended, that you configure your output to use the
    'urls' field instead of the 'url' field.

    For example, to use jdownloader 2 as output, you would use the exec plugin:
    exec:
      - echo "text={{urls}}" >> "/path/to/jd2/folderwatch/{{title}}.crawljob"
    """

    schema = {
        'type': 'object',
        'properties': {'filehosters_re': {'type': 'array', 'items': {'format': 'regexp'}}},
        'additionalProperties': False,
    }

    # Since the urlrewriter relies on a config, we need to create a default one
    config = {'filehosters_re': []}

    # grab config
    def on_task_start(self, task, config):
        self.config = config

    # urlrewriter API
    def url_rewritable(self, task, entry):
        url = entry['url']
        rewritable_regex = r'^https?:\/\/(www.)?(rmz\.cr|rapidmoviez\.(com|eu))\/.*'
        return re.match(rewritable_regex, url) is not None

    @plugin.internet(logger)
    # urlrewriter API
    def url_rewrite(self, task, entry):
        try:
            page = task.requests.get(entry['url'])
        except RequestException as e:
            raise UrlRewritingError(str(e))
        try:
            soup = get_soup(page.text)
        except Exception as e:
            raise UrlRewritingError(str(e))
        link_elements = soup.find_all('pre', class_='links')
        if 'urls' in entry:
            urls = list(entry['urls'])
        else:
            urls = []
        for element in link_elements:
            urls.extend(element.text.splitlines())
        regexps = self.config.get('filehosters_re', [])
        filtered_urls = []
        for i, url in enumerate(urls):
            urls[i] = normalize_unicode(url)
            for regexp in regexps:
                if re.search(regexp, urls[i]):
                    filtered_urls.append(urls[i])
                    logger.debug('Url: "{}" matched filehoster filter: {}', urls[i], regexp)
                    break
            else:
                if regexps:
                    logger.debug(
                        'Url: "{}" does not match any of the given filehoster filters: {}',
                        urls[i],
                        str(regexps),
                    )
        if regexps:
            logger.debug('Using filehosters_re filters: {}', str(regexps))
            urls = filtered_urls
        else:
            logger.debug('No filehoster filters configured, using all found links.')
        num_links = len(urls)
        logger.verbose('Found {} links at {}.', num_links, entry['url'])
        if num_links:
            entry['urls'] = urls
            entry['url'] = urls[0]
        else:
            raise UrlRewritingError('No useable links found at %s' % entry['url'])


@event('plugin.register')
def register_plugin():
    plugin.register(UrlRewriteRmz, 'rmz', interfaces=['urlrewriter', 'task'], api_ver=2)
