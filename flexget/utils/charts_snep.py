# -*- coding: utf8 -*-
from __future__ import unicode_literals, division, absolute_import
from abc import ABCMeta, abstractproperty
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


class ParsedChartEntry(ABCMeta(str('ParsedChartEntryABCMeta'), (object,), {})):
    """
    This class represents entries parsed form charts provider.
    """
    @abstractproperty
    def artist(self):
        """@:rtype str"""
        raise NotImplementedError

    @abstractproperty
    def song_title(self):
        """@:rtype str"""
        raise NotImplementedError

    @abstractproperty
    def rank(self):
        """@:rtype int"""
        raise NotImplementedError

    @abstractproperty
    def best_rank(self):
        """@:rtype int"""
        raise NotImplementedError

    @abstractproperty
    def charted_weeks(self):
        """@:rtype int"""
        raise NotImplementedError

    @abstractproperty
    def url(self):
        """@:rtype str"""
        raise NotImplementedError


class SnepParsedChartEntry(ParsedChartEntry):
    def __init__(self):
        self._url = None
        self._song_title = None
        self._artist = None
        self._company = None
        self._rank = None
        self._best_rank = None
        self._charted_weeks = 0

    @property
    def artist(self):
        return self._artist

    @property
    def song_title(self):
        return self._song_title

    @property
    def company(self):
        return self._company

    @property
    def rank(self):
        return self._rank

    @property
    def best_rank(self):
        return self._best_rank

    @property
    def charted_weeks(self):
        return self._charted_weeks

    @property
    def url(self):
        return self._url

    @staticmethod
    def get_entry_map():
        return {
            'charts_snep_rank': 'rank',
            'charts_snep_best_rank': 'best_rank',
            'charts_snep_weeks': 'charted_weeks',
            'music_artist': 'artist',
            'music_title': 'song_title',
            'music_company': 'company',
            'url': 'url'
        }


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
        :rtype SnepParsedChartEntry
        """

        result = SnepParsedChartEntry()
        tag_pos = tag_row.select('td.pos.lwn')
        if len(tag_pos) == 1:
            result._rank = str_to_int(tag_pos[0].text) or -1

        tag_best_position = tag_row.find('td', {'class': 'bp'})
        if tag_best_position:
            result._best_rank = str_to_int(tag_best_position.text) or -1

        tag_weeks_on_charts = tag_row.find('td', {'class': 'sw'})
        if tag_weeks_on_charts:
            result._charted_weeks = str_to_int(tag_weeks_on_charts.text) or 0

        tag_infos = tag_row.find('div', {'class': 'infos'})
        if tag_infos:
            tag_artist = tag_infos.find('strong', {'class': 'artist'})
            if tag_artist:
                result._artist = tag_artist.text

            tag_title = tag_infos.find('p', {'class': 'title'})
            if tag_title:
                result._song_title = tag_title.text

            tag_company = tag_infos.find('p', {'class': 'company'})
            if tag_company:
                result._company = tag_company.text
        return result

    def parse(self, soup, baseUrl=None):
        """
        :param self: SnepChartsParser
        :param soup: bs4.BeautifulSoup
        :rtype list of [SnepParsedChartEntry]
        """

        # year_tags = soup.select("#year_top option[selected]")
        # assert len(year_tags) == 1, "Got %i year tag instead of expected (one)." %len(year_tags)
        # year = int(year_tags[0]["value"])

        html_entries = soup.select("table.table-top > tbody > tr")
        for unparsed_entry in html_entries:
            parsed_entry = SnepChartsParser.parse_entry(unparsed_entry)
            parsed_entry._url = '%s#top-%i' % (baseUrl, parsed_entry.rank)
            self.charts_entries.append(parsed_entry)

        log.verbose('Produces %i entries' % len(self.charts_entries))
        return self.charts_entries

    def retrieve_charts(self, charts_type='radio', date_interval='week', year=None, week=None):
        url = make_url(charts_type,date_interval,year,week)
        page = requests.get(url).text
        soup = get_soup(page)
        return self.parse(soup, url)


def is_snep_url(url):
    """
    Tests if url go to snepmusique.com
    :param url: str
    :rtype bool
    """
    if not isinstance(url, basestring):
        return
    return re.match(r'https?://[^/]*snepmusique\.com/', url)


def make_url(charts_type='radio', date_interval='week', year=None, week=None):
    """
    Build the charts request URL based on charts_type and time interval definition
    :param charts_type: str [all_album, disk_album,digit_album, digit_single,
    stream_single, compil, back_catalog, radio]
    :param interval: str [week, year]
    :param year: int
    :param week: int
    :rtype str
    """
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