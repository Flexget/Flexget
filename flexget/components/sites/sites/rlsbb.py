from __future__ import unicode_literals, division, absolute_import
from builtins import *  # noqa pylint: disable=unused-import, redefined-builtin

import logging
import re

from flexget import plugin
from flexget.event import event
from flexget.components.sites.urlrewriting import UrlRewritingError
from flexget.utils.soup import get_soup
from flexget.components.sites.utils import normalize_unicode

from requests.exceptions import RequestException

log = logging.getLogger('rlsbb')


class UrlRewriteRlsbb(object):
    """
    rlsbb.ru urlrewriter
    Version 0.1

    Configuration

    rlsbb:
      filehosters_re:
        - domain\.com
        - domain2\.org
      link_text_re:
        - UPLOADGiG
        - NiTROFLARE
        - RAPiDGATOR
      parse_comments: no

    filehosters_re: Only add links that match any of the regular expressions 
      listed under filehosters_re.
    link_text_re: search for <a> tags where the text (not the url) matches 
      one of the given regular expressions. The href property of these <a> tags
      will be used as the url (or urls).
    parse_comments: whether the plugin should also parse the comments or only 
      the main post. Note that it is highly recommended to use filehosters_re
      if you enable parse_comments. Otherwise, the plugin may return too
      many and even some potentially dangerous links. 

    If more than one valid link is found, the url of the entry is rewritten to
    the first link found. The complete list of valid links is placed in the
    'urls' field of the entry.

    Therefore, it is recommended, that you configure your output to use the
    'urls' field instead of the 'url' field.

    For example, to use jdownloader 2 as output, you would use the exec plugin:
    exec:
      - echo "text={{urls}}" >> "/path/to/jd2/folderwatch/{{title}}.crawljob"
    """

    DEFAULT_DOWNLOAD_TEXT = ['UPLOADGiG', 'NiTROFLARE', 'RAPiDGATOR']

    schema = {
        'type': 'object',
        'properties': {
            'filehosters_re': {'type': 'array', 'items': {'format': 'regexp'}, 'default': []},
            'link_text_re': {
                'type': 'array',
                'items': {'format': 'regexp'},
                'default': DEFAULT_DOWNLOAD_TEXT,
            },
            'parse_comments': {'type': 'boolean', 'default': False},
        },
        'additionalProperties': False,
    }

    # Since the urlrewriter relies on a config, we need to create a default one
    config = {'filehosters_re': [], 'link_text_re': DEFAULT_DOWNLOAD_TEXT, 'parse_comments': False}

    # grab config
    def on_task_start(self, task, config):
        self.config = config

    # urlrewriter API
    def url_rewritable(self, task, entry):
        url = entry['url']
        rewritable_regex = r'^https?:\/\/(www.)?rlsbb\.(ru|com)\/.*'
        return re.match(rewritable_regex, url) is not None

    def _get_soup(self, task, url):
        try:
            page = task.requests.get(url)
        except RequestException as e:
            raise UrlRewritingError(str(e))
        try:
            return get_soup(page.text)
        except Exception as e:
            raise UrlRewritingError(str(e))

    # if the file is split into several parts, rlsbb links to a separate page
    # which we parse here
    def _grab_multilinks(self, task, url):
        soup = self._get_soup(task, url)
        link_list = soup.find('ol')
        link_divs = link_list.find_all('div')
        links = []
        for link in link_divs:
            links.append(link.string())
        return links

    @plugin.internet(log)
    # urlrewriter API
    def url_rewrite(self, task, entry):
        soup = self._get_soup(task, entry['url'])

        # grab links from the main post:
        link_elements = []
        log.debug(
            'Searching %s for a tags where the text matches one of: %s',
            entry['url'],
            str(self.config.get('link_text_re')),
        )
        for regexp in self.config.get('link_text_re'):
            link_elements.extend(soup.find_all('a', string=re.compile(regexp)))
        log.debug('Original urls: %s', str(entry['urls']))
        if 'urls' in entry:
            urls = list(entry['urls'])
            log.debug('Original urls: %s', str(entry['urls']))
        else:
            urls = []
        log.debug('Found link elements: %s', str(link_elements))
        for element in link_elements:
            if re.search('nfo1.rlsbb.(ru|com)', element['href']):
                # grab multipart links
                urls.extend(self.grab_multilinks(task, element['href']))
            else:
                urls.append(element['href'])

        # grab links from comments
        regexps = self.config.get('filehosters_re', [])
        if self.config.get('parse_comments'):
            comments = soup.find_all('div', id=re.compile("commentbody"))
            log.debug('Comment parsing enabled: found %d comments.', len(comments))
            if comments and not regexps:
                log.warn(
                    'You have enabled comment parsing but you did not define any filehoster_re filter. You may get a lot of unwanted and potentially dangerous links from the comments.'
                )
            for comment in comments:
                links = comment.find_all('a')
                for link in links:
                    urls.append(link['href'])

        # filter urls:
        filtered_urls = []
        for i, url in enumerate(urls):
            urls[i] = normalize_unicode(url)
            for regexp in regexps:
                if re.search(regexp, urls[i]):
                    filtered_urls.append(urls[i])
                    log.debug('Url: "%s" matched filehoster filter: %s', urls[i], regexp)
                    break
            else:
                if regexps:
                    log.debug(
                        'Url: "%s" was discarded because it does not match any of the given filehoster filters: %s',
                        urls[i],
                        str(regexps),
                    )
        if regexps:
            log.debug('Using filehosters_re filters: %s', str(regexps))
            urls = filtered_urls
        else:
            log.debug('No filehoster filters configured, using all found links.')
        num_links = len(urls)
        log.verbose('Found %d links at %s.', num_links, entry['url'])
        if num_links:
            entry['urls'] = urls
            entry['url'] = urls[0]
        else:
            raise UrlRewritingError('No useable links found at %s' % entry['url'])


@event('plugin.register')
def register_plugin():
    plugin.register(UrlRewriteRlsbb, 'rlsbb', interfaces=['urlrewriter', 'task'], api_ver=2)
