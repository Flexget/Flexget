from bs4 import NavigableString
from loguru import logger
from requests import RequestException

from flexget import plugin
from flexget.entry import Entry
from flexget.event import event
from flexget.utils.cached_input import cached
from flexget.utils.soup import get_soup

try:
    # NOTE: Importing other plugins is discouraged!
    from flexget.components.imdb.utils import extract_id
except ImportError:
    raise plugin.DependencyError(issued_by=__name__, missing='imdb')

logger = logger.bind(name='sceper')


class InputSceper:
    """
    Uses sceper.ws category url as input.

    Example::

      sceper: http://sceper.ws/category/movies/movies-dvd-rip
    """

    schema = {'type': 'string', 'format': 'url'}

    def parse_site(self, url, task):
        """Parse configured url and return releases array"""

        try:
            page = task.requests.get(url).content
        except RequestException as e:
            raise plugin.PluginError('Error getting input page: %s' % e)
        soup = get_soup(page)

        releases = []
        for entry in soup.find_all('div', attrs={'class': 'entry'}):
            release = {}
            title = entry.find('h2')
            if not title:
                logger.debug('No h2 entrytitle')
                continue
            release['title'] = title.a.contents[0].strip()

            logger.debug('Processing title {}', release['title'])

            for link in entry.find_all('a'):
                # no content in the link
                if not link.contents:
                    continue
                link_name = link.contents[0]
                if link_name is None:
                    continue
                if not isinstance(link_name, NavigableString):
                    continue
                link_name = link_name.strip().lower()
                if link.has_attr('href'):
                    link_href = link['href']
                else:
                    continue
                logger.debug('found link {} -> {}', link_name, link_href)
                # handle imdb link
                if link_name.lower() == 'imdb':
                    logger.debug('found imdb link {}', link_href)
                    release['imdb_id'] = extract_id(link_href)

                # test if entry with this url would be rewritable by known plugins (ie. downloadable)
                temp = {}
                temp['title'] = release['title']
                temp['url'] = link_href
                urlrewriting = plugin.get('urlrewriting', self)
                if urlrewriting.url_rewritable(task, temp):
                    release['url'] = link_href
                    logger.trace('--> accepting {} (resolvable)', link_href)
                else:
                    logger.trace('<-- ignoring {} (non-resolvable)', link_href)

            # reject if no torrent link
            if 'url' not in release:
                from flexget.utils.log import log_once

                log_once(
                    '%s skipped due to missing or unsupported (unresolvable) download link'
                    % (release['title']),
                    logger,
                )
            else:
                releases.append(release)

        return releases

    @cached('sceper')
    @plugin.internet(logger)
    def on_task_input(self, task, config):
        releases = self.parse_site(config, task)
        return [Entry(release) for release in releases]


@event('plugin.register')
def register_plugin():
    plugin.register(InputSceper, 'sceper', api_ver=2)
