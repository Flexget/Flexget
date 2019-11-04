from __future__ import unicode_literals, division, absolute_import
from builtins import *  # noqa pylint: disable=unused-import, redefined-builtin
from future.moves.urllib import parse


import logging
import posixpath
import zlib
import re
import io

from jinja2 import Template

from flexget import plugin
from flexget.event import event
from flexget.entry import Entry
from flexget.utils.soup import get_soup
from flexget.utils.cached_input import cached

log = logging.getLogger('html')


class InputHtml(object):
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
                    'limit_scope': {
                        'type': 'array',
                        'items': {
                            'oneOf': [
                                {'type': 'string'},
                                {
                                    'type': 'object',
                                    'additionalProperties': {
                                        'type': 'object',
                                        'properties': {
                                            'element_name': {'type': 'string'},
                                            'attribute_name': {'type': 'string'},
                                            'attribute_value': {'type': 'string'},
                                            'start': {'type': 'integer', 'default': 1, 'minimum': 1},
                                            'end': {'type': 'integer', 'default': 31415, 'minimum': 1},
                                        },
                                        'additionalProperties': False,
                                        'anyOf': [
                                            {'required': ['element_name']},
                                            {'required': ['attribute_name']},
                                            {'required': ['attribute_value']},
                                        ],
                                        'dependencies': {'attribute_value': ['attribute_name']},
                                    },
                                },
                            ]
                        },
                    },
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
                    log.warning('Invalid basic authentication in url: %s' % config['url'])
                parts[1] = split[1]
                config['url'] = parse.urlunsplit(parts)

        if isinstance(config, str):
            config = {'url': config}
        get_auth_from_url()
        return config

    @cached('html')
    @plugin.internet(log)
    def on_task_input(self, task, config):
        config = self.build_config(config)

        auth = None
        if config.get('username') and config.get('password'):
            log.debug(
                'Basic auth enabled. User: %s Password: %s'
                % (config['username'], config['password'])
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
                new_entries = self._request_url(task, config, url, auth, dump_name)
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
        log.verbose('Requesting: %s' % url)
        page = task.requests.get(url, auth=auth)
        log.verbose('Response: %s (%s)' % (page.status_code, page.reason))
        soup = get_soup(page.content)

        # dump received content into a file
        if dump_name:
            log.verbose('Dumping: %s' % dump_name)
            data = soup.prettify()
            with io.open(dump_name, 'w', encoding='utf-8') as f:
                f.write(data)

        return self.create_entries(url, soup, config)

    def _title_from_link(self, link, log_link):
        title = link.text
        # longshot from next element (?)
        if not title:
            title = link.next.string
            if title is None:
                log.debug('longshot failed for %s' % log_link)
                return None
        return title or None

    def _title_from_url(self, url):
        parts = parse.urlsplit(url)
        name = ''
        if parts.scheme == 'magnet':
            match = re.search('(?:&dn(?:\.\d)?=)(.+?)(?:&)', parts.query)
            if match:
                name = match.group(1)
        else:
            name = posixpath.basename(parts.path)
        return parse.unquote_plus(name)

    def _get_anchor_list(self, element_tag_list, scope_num, search_terms, anchor_list):

        if scope_num < len(search_terms):
            temp_list = []
            for x in range(len(element_tag_list[scope_num])):
                result_set = (
                    element_tag_list[scope_num][x].find_all(search_terms[scope_num][0], search_terms[scope_num][1])
                )
                if (eval(search_terms[scope_num][2]) >= eval(search_terms[scope_num][3]) or
                    eval(search_terms[scope_num][2]) >= len(result_set)):
                    log.warning(
                        ("The specified start (%s) for scope_limit #%s is the same as or after the specified end (%s)"
                         " or actual end (%s) for match #%s. The start will be set to the beginning, by default.") % (
                            str(eval(search_terms[scope_num][2]) + 1), str(scope_num + 1),
                            str(eval(search_terms[scope_num][3])), str(len(result_set)), str(x + 1))
                    )
                    start = "0"
                else:
                    start = search_terms[scope_num][2]
                if eval(search_terms[scope_num][3]) > len(result_set):
                    log.warning(
                        ("The specified end (%s) for scope_limit #%s is after the actual end (%s) for match #%s. The "
                         "end will be set to the actual end, by default.") % (
                          str(eval(search_terms[scope_num][3])), str(scope_num + 1), str(len(result_set)), str(x + 1))
                    )
                    end = str(len(result_set))
                else:
                    end = search_terms[scope_num][3]
                for y in range(eval(start), eval(end)):
                    temp_list.append(result_set[y])

            element_tag_list.append(temp_list)
            return self._get_anchor_list(element_tag_list, scope_num + 1, search_terms, anchor_list)
        else:
            for x in range(len(element_tag_list[scope_num])):
                tmp_list = element_tag_list[scope_num][x].find_all('a')
                for item in tmp_list:
                    anchor_list.append(item)

            return anchor_list

    def _limit_scope(self, soup, config):

        search_terms = []
        scope_list = config.get('limit_scope')

        for element in scope_list:
            if isinstance(element, str):
                element_name = re.compile("^" + element + "$")
                refine_dict = {}
                start = "0"
                end = "len(result_set)"
            else:
                scope_name = next(iter(element))
                scope_info = element[scope_name]
                raw_element_name = scope_info.get('element_name')
                if not raw_element_name:
                    element_name = re.compile('.*')
                else:
                    element_name = re.compile("^" + raw_element_name + "$")
                start = str(scope_info.get('start') - 1)
                end = scope_info.get('end')
                attribute_name = scope_info.get('attribute_name')
                attribute_value = scope_info.get('attribute_value')
                if not attribute_name and not attribute_value:
                    refine_dict = {}
                else:
                    if not attribute_value:
                        attribute_value = '.*'
                    refine_dict = {attribute_name: re.compile("^" + attribute_value + "$")}

                if end == 31415:
                    end = "len(result_set)"
                else:
                    end = str(end)

            search_terms.append([element_name, refine_dict, start, end])
        return self._get_anchor_list([[soup]], 0, search_terms, [])

    def create_entries(self, page_url, soup, config):

        queue = []
        duplicates = {}
        duplicate_limit = 4

        def title_exists(title):
            """Helper method. Return True if title is already added to entries"""
            for entry in queue:
                if entry['title'] == title:
                    return True

        if config.get('limit_scope'):
            anchor_list = self._limit_scope(soup, config)
        else:
            anchor_list = soup.find_all('a')

        for link in anchor_list:

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
                    log.debug('url does not match any "links_re": %s' % url)
                    continue

            title_from = config.get('title_from', 'auto')
            if title_from == 'url':
                title = self._title_from_url(url)
                log.debug('title from url: %s' % title)
            elif title_from == 'title':
                if not link.has_attr('title'):
                    log.warning('Link `%s` doesn\'t have title attribute, ignored.' % log_link)
                    continue
                title = link['title']
                log.debug('title from title: %s' % title)
            elif title_from == 'auto':
                title = self._title_from_link(link, log_link)
                if title is None:
                    continue
                # automatic mode, check if title is unique
                # if there are too many duplicate titles, switch to title_from: url
                if title_exists(title):
                    # ignore index links as a counter
                    if 'index' in title and len(title) < 10:
                        log.debug('ignored index title %s' % title)
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
                        log.info(
                            'Link names seem to be useless, auto-configuring \'title_from: %s\'. '
                            'This may not work well, you might need to configure it yourself.'
                            % switch_to
                        )
                        config['title_from'] = switch_to
                        # start from the beginning  ...
                        return self.create_entries(page_url, soup, config)
            elif title_from == 'link' or title_from == 'contents':
                # link from link name
                title = self._title_from_link(link, log_link)
                if title is None:
                    continue
                log.debug('title from link: %s' % title)
            else:
                raise plugin.PluginError('Unknown title_from value %s' % title_from)

            if not title:
                log.warning('title could not be determined for link %s' % log_link)
                continue

            # strip unicode white spaces
            title = title.replace(u'\u200B', u'').strip()

            # in case the title contains xxxxxxx.torrent - foooo.torrent clean it a bit (get up to first .torrent)
            # TODO: hack
            if title.lower().find('.torrent') > 0:
                title = title[: title.lower().find('.torrent')]

            if title_exists(title):
                # title link should be unique, add CRC32 to end if it's not
                hash = zlib.crc32(url.encode("utf-8"))
                crc32 = '%08X' % (hash & 0xFFFFFFFF)
                title = '%s [%s]' % (title, crc32)
                # truly duplicate, title + url crc already exists in queue
                if title_exists(title):
                    continue
                log.debug('uniqued title to %s' % title)

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
