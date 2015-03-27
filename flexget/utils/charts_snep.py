# -*- coding: utf8 -*-
from __future__ import unicode_literals, division, absolute_import
import difflib
import logging
import re

from bs4.element import Tag
from flexget.utils.soup import get_soup
from flexget.utils.requests import Session
from flexget.utils.tools import str_to_int
from flexget.plugin import get_plugin_by_name

log = logging.getLogger('utils.charts_snep')
requests = Session()
#requests.headers.update({'User-Agent': 'Python-urllib/2.6'})
#requests.headers.update({'User-Agent': random.choice(USERAGENTS)})

requests.headers.update({'Accept-Language': 'fr-FR,en;q=0.8'})
requests.set_domain_delay('snepmusique.com', '1 second')

class SnepChartsEntry(object):
    """ Plain Old Object for store a charts entry from SNEP website. """
    def __init__(self):
        self.title = None
        self.artist = None
        self.company = None

        self.stat_position = None
        self.best_position = None

    def __str__(self):
        def s(value):
            return value if (value != None) else '-'

        def i(value):
            return value if (value != None) else -1

        return "artist:%s, company:%s, title:%s, stat_position:%i, best_position:%i" % (s(self.artist), s(self.company), s(self.title), i(self.stat_position), i(self.best_position))


class SnepChartsParser(object):
    """Parser de page de charts du SNEP"""

    def __init__(self):
        self.stat_date_start = None
        self.stat_date_end = None
        self.charts_type = None
        self.charts_entries = []

    @property
    def __str__(self):
        return '<SnepParser(type=%s,entries count=%s)>' % (self.charts_type, len(self.charts_entries))

    @staticmethod
    def parse_entry(tag_row):
        """
        :param tag_row: Tag
        :rtype SnepChartsEntry
        """

        result = SnepChartsEntry()
        tag_pos = tag_row.select('td.pos.lwn')
        if len(tag_pos) == 1:
            result.stat_position = str_to_int(tag_pos[0].text) or -1

        tag_best_position = tag_row.find('td', {'class': 'bp'})
        if tag_best_position:
            result.best_position = str_to_int(tag_best_position.text) or -1

        tag_infos = tag_row.find('div', {'class': 'infos'})
        if tag_infos:
            tag_artist = tag_infos.find('strong', {'class': 'artist'})
            if tag_artist:
                if tag_artist and tag_artist.text != 'Multi Interprètes':
                    result.artist = tag_artist.text

            tag_title = tag_infos.find('p', {'class': 'title'})
            if tag_title:
                result.title = tag_title.text

            tag_company = tag_infos.find('p', {'class': 'company'})
            if tag_company:
                result.company = tag_company.text
        return result

    def parse(self, soup):
        """
        :param self: SnepChartsParser
        :param soup: bs4.BeautifulSoup
        :rtype list of [SnepChartsEntry]
        """

        # year_tags = soup.select("#year_top option[selected]")
        # assert len(year_tags) == 1, "Got %i year tag instead of expected (one)." %len(year_tags)
        # year = int(year_tags[0]["value"])

        html_entries = soup.select("table.table-top > tbody > tr")
        for unparsed_entry in html_entries:
            self.charts_entries.append(SnepChartsParser.parse_entry(unparsed_entry))

        return self.charts_entries

    def retrieve_charts(self, charts_type='radio', date_interval='week', year=None, week=None):
        url = make_url(charts_type,date_interval,year,week)
        page = requests.get(url).text
        soup = get_soup(page)
        return self.parse(soup)

def is_snep_url(url):
    """Tests if url go to snepmusique.com."""
    if not isinstance(url, basestring):
        return
    return re.match(r'https?://[^/]*snepmusique\.com/', url)

def make_url(charts_type='radio', date_interval='week', year=None, week=None):
    """Construit l'url pour le type de charts demandé (type:[all_album, disk_album,
    digit_album, digit_single, stream_single, compil, back_catalog, radio],
    interval=[week, year]"""
    date_interval_to_url_path = {
        'year' : 'tops-annuel',
        'week' : 'tops-semaine'
    }
    type_to_url_path = {
        'all_album': 'top-albums-fusionnes',
        'disk_album': 'top-albums-physiques',
        'digit_album': 'top-albums-telecharges',
        'digit_single': 'top-singles-telecharges',
        'stream_single': 'top-singles-streaming',
        'compil': 'top-compilations',
        'back_catalog': 'top-back-catalogue',
        'radio' : 'top-radios'
    }

    part_url = '?'
    if isinstance(year, int):
        part_url += 'ye=%i&' % year
    if isinstance(week, int):
        part_url += 'we=%i' % week

    return u'http://www.snepmusique.com/%s/%s/%s' \
           % (date_interval_to_url_path[date_interval],
              type_to_url_path[charts_type],
              part_url)