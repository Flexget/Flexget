from __future__ import unicode_literals, division, absolute_import
import urlparse
import logging
from flexget.entry import Entry
from flexget.plugin import register_plugin, internet
from flexget.utils.soup import get_soup
from flexget.utils.cached_input import cached
from flexget.utils.tools import urlopener

log = logging.getLogger('tvtorrents')


class InputTVTorrents(object):
    """
        A customized HTML input plugin. Parses out full torrent URLs from
        TVTorrents' page for Recently Aired TV shows.

        A bit fragile right now, because it depends heavily on the exact
        structure of the HTML.

        Just set tvt: true in your config, and provide the path to your login
        cookie by using the cookies plugin.

        Note: Of yourse, you need to configure patterns filter to match only
        desired content. The series filter does NOT appear to work well with
        this plugin yet - just use a pattern like (lost|csi).*?720p until we
        figure out why.

        Plugin-specific code by Fredrik Braenstroem.
    """

    def validator(self):
        from flexget import validator
        return validator.factory('url')

    @cached('tvt')
    @internet(log)
    def on_task_input(self, task):
        pageurl = "http://tvtorrents.com/loggedin/recently_aired.do"
        log.debug("InputPlugin tvtorrents requesting url %s" % pageurl)

        page = urlopener(pageurl, log)
        soup = get_soup(page)

        hscript = soup.find('script', src=None).contents[0]
        hlines = hscript.splitlines()
        hash = hlines[15].strip().split("'")[1]
        digest = hlines[16].strip().split("'")[1]
        hurl = hlines[17].strip().split("'")
        hashurl = hurl[1] + "%s" + hurl[3] + digest + hurl[5] + hash

        for link in soup.find_all('a'):
            if not 'href' in link:
                continue
            url = link['href']
            title = link.contents[0]

            if link.has_attr('onclick') and link['onclick'].find("loadTorrent") != -1:
                infohash = link['onclick'].split("'")[1]
                td = link.parent.parent.contents[4]
                sname = td.contents[0].strip()
                epi = td.contents[2].contents[0].strip()
                title = "%s - %s" % (sname, epi)
                url = hashurl % (infohash,)
            else:
                continue
            if title is None:
                continue

            title = title.strip()
            if not title:
                continue

            # fix broken urls
            if url.startswith('//'):
                url = "http:" + url
            elif not url.startswith('http://') or not url.startswith('https://'):
                url = urlparse.urljoin(pageurl, url)

            # in case the title contains xxxxxxx.torrent - foooo.torrent clean it a bit (get upto first .torrent)
            if title.lower().find('.torrent') > 0:
                title = title[:title.lower().find(".torrent")]

            entry = Entry()
            entry['url'] = url
            entry['title'] = title

            task.entries.append(entry)

register_plugin(InputTVTorrents, 'tvt')
