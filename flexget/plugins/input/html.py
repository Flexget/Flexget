import re
import zlib
from pathlib import Path
from urllib import parse

from jinja2 import Template
from loguru import logger
from requests.exceptions import HTTPError

from flexget import plugin
from flexget.entry import Entry
from flexget.event import event
from flexget.utils.cached_input import cached
from flexget.utils.soup import get_soup

logger = logger.bind(name='html')


class InputHtml:
    """
    Parses urls from html page. Usefull on sites which have direct download
    links of any type (mp3, jpg, torrent, ...).

    Many anime-fansubbers do not provide RSS-feed, this works well in many cases.

    Configuration expects url parameter.

    Note: This returns ALL links on url so you need to configure filters
    to match only to desired content.
    """

    schema = {
        'oneOf': [
            {'type': 'string'},
            {
                'type': 'object',
                'properties': {
                    'url': {'type': 'string', 'format': 'url'},
                    'username': {'type': 'string'},
                    'password': {'type': 'string'},
                    'dump': {'type': 'string'},
                    'title_from': {'type': 'string'},
                    'allow_empty_links': {'type': 'boolean'},
                    'links_re': {'type': 'array', 'items': {'type': 'string', 'format': 'regex'}},
                    'increment': {
                        'oneOf': [
                            {'type': 'boolean'},
                            {
                                'type': 'object',
                                'properties': {
                                    'from': {'type': 'integer'},
                                    'to': {'type': 'integer'},
                                    'name': {'type': 'string'},
                                    'step': {'type': 'integer'},
                                    'stop_when_empty': {'type': 'boolean'},
                                    'stop_when_404': {'type': 'boolean'},
                                    'entries_count': {'type': 'integer'},
                                },
                                'additionalProperties': False,
                            },
                        ]
                    },
                },
                'required': ['url'],
                'additionalProperties': False,
            },
        ]
    }

    def build_config(self, config):
        def get_auth_from_url():
            """Moves basic authentication from url to username and password fields"""
            parts = list(parse.urlsplit(config['url']))
            split = parts[1].split('@')
            if len(split) > 1:
                auth = split[0].split(':')
                if len(auth) == 2:
                    config['username'], config['password'] = auth[0], auth[1]
                else:
                    logger.warning('Invalid basic authentication in url: {}', config['url'])
                parts[1] = split[1]
                config['url'] = parse.urlunsplit(parts)

        if isinstance(config, str):
            config = {'url': config}
        get_auth_from_url()
        return config

    @cached('html')
    @plugin.internet(logger)
    def on_task_input(self, task, config):
        config = self.build_config(config)

        auth = None
        if config.get('username') and config.get('password'):
            logger.debug(
                'Basic auth enabled. User: {} Password: {}', config['username'], config['password']
            )
            auth = (config['username'], config['password'])

        increment = config.get('increment')
        base_url = config['url']
        if increment:
            entries = None
            if not isinstance(increment, dict):
                increment = {}
            current = increment.get('from', 0)
            to = increment.get('to')
            step = increment.get('step', 1)
            base_url = config['url']
            entries_count = increment.get('entries_count', 500)
            stop_when_empty = increment.get('stop_when_empty', True)
            stop_when_404 = increment.get('stop_when_404', True)
            increment_name = increment.get('name', 'i')

            template_url = Template(base_url)
            template_dump = None
            if 'dump' in config:
                dump_name = config['dump']
                if dump_name:
                    template_dump = Template(dump_name)

            while to is None or current < to:
                render_ctx = {increment_name: current}
                url = template_url.render(**render_ctx)
                dump_name = None
                if template_dump:
                    dump_name = template_dump.render(**render_ctx)
                try:
                    new_entries = self._request_url(task, config, url, auth, dump_name)
                except HTTPError as e:
                    if stop_when_404 and e.response.status_code == 404:
                        break
                    raise e
                if not entries:
                    entries = new_entries
                else:
                    entries.extend(new_entries)
                if stop_when_empty and not new_entries:
                    break
                if entries_count and len(entries) >= entries_count:
                    break
                current += step
            return entries
        else:
            return self._request_url(task, config, base_url, auth, dump_name=config.get('dump'))

    def _request_url(self, task, config, url, auth, dump_name=None):
        logger.verbose('Requesting: {}', url)
        page = task.requests.get(url, auth=auth)
        logger.verbose('Response: {} ({})', page.status_code, page.reason)
        soup = get_soup(page.content)

        # dump received content into a file
        if dump_name:
            logger.verbose('Dumping: {}', dump_name)
            data = soup.prettify()
            with open(dump_name, 'w', encoding='utf-8') as f:
                f.write(data)

        return self.create_entries(url, soup, config)

    def _title_from_link(self, link, log_link):
        title = link.text
        # longshot from next element (?)
        if not title:
            title = link.next.string
            if title is None:
                logger.debug('longshot failed for {}', log_link)
                return None
        return title or None

    @staticmethod
    def _title_from_url(url):
        parts = parse.urlsplit(url)
        name = ''
        if parts.scheme == 'magnet':
            match = re.search(r'(?:&dn(?:\.\d)?=)(.+?)(?:&)', parts.query)
            if match:
                name = match.group(1)
        else:
            name = Path(parts.path).name
        return parse.unquote_plus(name)

    def create_entries(self, page_url, soup, config):
        queue = []
        duplicates = {}
        duplicate_limit = 4

        def title_exists(title):
            """Helper method. Return True if title is already added to entries"""
            for entry in queue:
                if entry['title'] == title:
                    return True

        for link in soup.find_all('a'):
            # not a valid link
            if not link.has_attr('href'):
                continue
            # no content in the link
            if not link.contents and not config.get('allow_empty_links', False):
                continue

            url = link['href']
            # fix broken urls
            if url.startswith('//'):
                url = 'http:' + url
            elif not url.startswith('http://') or not url.startswith('https://'):
                url = parse.urljoin(page_url, url)

            log_link = url
            log_link = log_link.replace('\n', '')
            log_link = log_link.replace('\r', '')

            # get only links matching regexp
            regexps = config.get('links_re', None)
            if regexps:
                accept = False
                for regexp in regexps:
                    if re.search(regexp, url):
                        accept = True
                if not accept:
                    logger.debug('url does not match any "links_re": {}', url)
                    continue

            title_from = config.get('title_from', 'auto')
            if title_from == 'url':
                title = self._title_from_url(url)
                logger.debug('title from url: {}', title)
            elif title_from == 'title':
                if not link.has_attr('title'):
                    logger.warning("Link `{}` doesn't have title attribute, ignored.", log_link)
                    continue
                title = link['title']
                logger.debug('title from title: {}', title)
            elif title_from == 'auto':
                title = self._title_from_link(link, log_link)
                if title is None:
                    continue
                # automatic mode, check if title is unique
                # if there are too many duplicate titles, switch to title_from: url
                if title_exists(title):
                    # ignore index links as a counter
                    if 'index' in title and len(title) < 10:
                        logger.debug('ignored index title {}', title)
                        continue
                    duplicates.setdefault(title, 0)
                    duplicates[title] += 1
                    if duplicates[title] > duplicate_limit:
                        # if from url seems to be bad choice use title
                        from_url = self._title_from_url(url)
                        switch_to = 'url'
                        for ext in ('.html', '.php'):
                            if from_url.endswith(ext):
                                switch_to = 'title'
                        logger.info(
                            "Link names seem to be useless, auto-configuring 'title_from: {}'. This may not work well, you might need to configure it yourself.",
                            switch_to,
                        )
                        config['title_from'] = switch_to
                        # start from the beginning  ...
                        return self.create_entries(page_url, soup, config)
            elif title_from == 'link' or title_from == 'contents':
                # link from link name
                title = self._title_from_link(link, log_link)
                if title is None:
                    continue
                logger.debug('title from link: {}', title)
            else:
                raise plugin.PluginError('Unknown title_from value %s' % title_from)

            if not title:
                logger.warning('title could not be determined for link {}', log_link)
                continue

            # strip unicode white spaces
            title = title.replace('\u200B', '').strip()

            # in case the title contains xxxxxxx.torrent - foooo.torrent clean it a bit (get up to first .torrent)
            # TODO: hack
            if title.lower().find('.torrent') > 0:
                title = title[: title.lower().find('.torrent')]

            if title_exists(title):
                # title link should be unique, add CRC32 to end if it's not
                hash = zlib.crc32(url.encode("utf-8"))
                crc32 = '%08X' % (hash & 0xFFFFFFFF)
                title = f'{title} [{crc32}]'
                # truly duplicate, title + url crc already exists in queue
                if title_exists(title):
                    continue
                logger.debug('uniqued title to {}', title)

            entry = Entry()
            entry['url'] = url
            entry['title'] = title

            if 'username' in config and 'password' in config:
                entry['download_auth'] = (config['username'], config['password'])

            queue.append(entry)

        # add from queue to task
        return queue


@event('plugin.register')
def register_plugin():
    plugin.register(InputHtml, 'html', api_ver=2)
