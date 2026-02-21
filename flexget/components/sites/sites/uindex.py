from __future__ import annotations

from urllib.parse import urljoin

from loguru import logger

from flexget import plugin
from flexget.components.sites.utils import torrent_availability
from flexget.entry import Entry
from flexget.event import event
from flexget.utils.cached_input import cached
from flexget.utils.requests import RequestException
from flexget.utils.soup import get_soup
from flexget.utils.tools import parse_filesize

logger = logger.bind(name='uindex')


class UIndex:
    """Fetch category listings from UIndex.

    Configuration example::

      uindex: movies

    Choose a single category from: ``movies``, ``tv``, ``game``, ``music``,
    ``app``, ``xxx``, ``anime``, ``other``. The plugin yields FlexGet entries
    populated with ``name``/``title``, ``url`` (magnet when available), ``size``
    (string), ``content_size`` (parsed value when possible), ``torrent_seeds``,
    ``torrent_leeches`` and ``torrent_availability``. The same configuration
    string works for both ``input`` and ``search`` plugin interfaces.
    """

    BASE_URL = 'https://uindex.org/'
    SECTION_URLS = {
        'movies': urljoin(BASE_URL, 'search.php?c=1'),
        'tv': urljoin(BASE_URL, 'search.php?c=2'),
        'game': urljoin(BASE_URL, 'search.php?c=3'),
        'music': urljoin(BASE_URL, 'search.php?c=4'),
        'app': urljoin(BASE_URL, 'search.php?c=5'),
        'xxx': urljoin(BASE_URL, 'search.php?c=6'),
        'anime': urljoin(BASE_URL, 'search.php?c=7'),
        'other': urljoin(BASE_URL, 'search.php?c=8'),
    }
    SECTION_KEYS = list(SECTION_URLS.keys())

    schema = {
        'type': 'string',
        'enum': SECTION_KEYS,
    }

    def _normalize_section(self, config):
        if not isinstance(config, str):
            raise plugin.PluginError('uindex plugin requires a single category name as a string')
        section = config.lower().strip()
        if section not in self.SECTION_URLS:
            raise plugin.PluginError(
                'Invalid uindex category `{}`. Choose one of: {}'.format(
                    config, ', '.join(self.SECTION_KEYS)
                )
            )
        return section

    def _fetch_section_table(self, task, section, search_query=None):
        url = self.SECTION_URLS[section]
        params = None
        if search_query:
            params = {'search': search_query}
        try:
            response = task.requests.get(url, params=params)
            response.raise_for_status()
        except RequestException as e:
            context = f'search `{search_query}`' if search_query else 'listing'
            logger.warning('Unable to retrieve UIndex section `{}` {}: {}', section, context, e)
            return None
        soup = get_soup(response.content)
        table = soup.find('table', class_='maintable')
        if not table:
            logger.warning(
                'No results table found for UIndex section `{}` ({}){}',
                section,
                url,
                f' query `{search_query}`' if search_query else '',
            )
        return table

    @staticmethod
    def _parse_int(value):
        digits = ''.join(ch for ch in value if ch.isdigit())
        return int(digits) if digits else 0

    def _parse_section_entries(self, table, section):
        entries = []
        for row in table.find_all('tr'):
            cells = row.find_all('td')
            if len(cells) < 5:
                continue

            name_cell = cells[1]
            magnet_link = None
            detail_href = None
            title_text = None

            for anchor in name_cell.find_all('a', href=True):
                href = anchor['href'].strip()
                if href.startswith('magnet:') and magnet_link is None:
                    magnet_link = href
                elif href.startswith('/') and detail_href is None:
                    detail_href = href
                    title_text = anchor.get_text(' ', strip=True) or title_text

            if title_text is None:
                title_text = name_cell.get_text(' ', strip=True)

            if not title_text or (magnet_link is None and detail_href is None):
                continue

            size_text = cells[2].get_text(' ', strip=True)
            content_size = None
            try:
                content_size = parse_filesize(size_text)
            except ValueError:
                logger.debug('Could not parse size `{}` for `{}`', size_text, title_text)

            seeds = self._parse_int(cells[3].get_text(' ', strip=True))
            leeches = self._parse_int(cells[4].get_text(' ', strip=True))

            entry = Entry()
            entry['title'] = title_text
            entry['name'] = title_text
            entry['url'] = magnet_link or urljoin(self.BASE_URL, detail_href)
            entry['size'] = size_text
            if content_size is not None:
                entry['content_size'] = content_size
            entry['torrent_seeds'] = seeds
            entry['torrent_leeches'] = leeches
            entry['torrent_availability'] = torrent_availability(seeds, leeches)
            entry['uindex_category'] = section
            if detail_href:
                entry['uindex_detail_url'] = urljoin(self.BASE_URL, detail_href)

            entries.append(entry)
        return entries

    @cached('uindex', persist='15 minutes')
    def on_task_input(self, task, config):
        section = self._normalize_section(config)

        table = self._fetch_section_table(task, section)
        if not table:
            return []

        entries = self._parse_section_entries(table, section)
        logger.verbose('UIndex produced {} entries for category `{}`', len(entries), section)
        return entries

    def search(self, task, entry, config):
        section = self._normalize_section(config)
        search_strings = entry.get('search_strings', [entry.get('title')])

        found_entries = []
        seen_urls = set()

        for search_string in search_strings:
            if not search_string:
                continue
            table = self._fetch_section_table(task, section, search_query=search_string)
            if not table:
                continue
            for result in self._parse_section_entries(table, section):
                url = result.get('url')
                if url and url in seen_urls:
                    continue
                if url:
                    seen_urls.add(url)
                found_entries.append(result)

        logger.verbose(
            'UIndex search produced {} entries for `{}` in category `{}`',
            len(found_entries),
            entry.get('title'),
            section,
        )
        return found_entries


@event('plugin.register')
def register_plugin():
    plugin.register(UIndex, 'uindex', interfaces=['search'], api_ver=2)
