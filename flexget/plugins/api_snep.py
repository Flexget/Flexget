# -*- coding: utf8 -*-
from __future__ import unicode_literals, division, absolute_import
import datetime
import logging

from flexget import plugin
from flexget.plugins.filter.charts import ChartsConnector, ChartsEntry, ChartsRelease
from flexget.event import event
import re
from flexget.utils.soup import get_soup
from flexget.utils.requests import Session
from flexget.utils.tools import str_to_int


log = logging.getLogger('utils.charts_snep')

requests = Session()
requests.headers.update({'Accept-Language': 'fr-FR,en;q=0.8'})
requests.set_domain_delay('snepmusique.com', '1 second')


class SnepChartsConnector(ChartsConnector):
    """
    A ChartsConnector for retrieving and parsing charts
    from snepmusique.com, the official charts provider
    for France.
    """

    @property
    def organization(self):
        return 'snep'

    @property
    def __str__(self):
        return '<SnepParser(type=%s,entries count=%s)>' % (self.charts_type, len(self.charts_entries))

    @staticmethod
    def parse_entry(tag_row):
        """
        Produce a ChartsEntry from one row (tr tag) infos
        :param tag_row: Tag
        :rtype ChartsEntry
        """

        result = ChartsEntry()
        tag_pos = tag_row.select('td.pos.lwn')
        if len(tag_pos) == 1:
            result.rank = str_to_int(tag_pos[0].text) or -1

        tag_best_position = tag_row.find('td', {'class': 'bp'})
        if tag_best_position:
            result.best_rank = str_to_int(tag_best_position.text) or -1

        tag_weeks_on_charts = tag_row.find('td', {'class': 'sw'})
        if tag_weeks_on_charts:
            result.charted_weeks = str_to_int(tag_weeks_on_charts.text) or 0

        tag_infos = tag_row.find('div', {'class': 'infos'})
        if tag_infos:
            tag_artist = tag_infos.find('strong', {'class': 'artist'})
            if tag_artist:
                result.artist = tag_artist.text

            tag_title = tag_infos.find('p', {'class': 'title'})
            if tag_title:
                result.title = tag_title.text

            tag_company = tag_infos.find('p', {'class': 'company'})
            if tag_company:
                result.company = tag_company.text
        return result

    @staticmethod
    def parse(soup, base_url=None):
        """
        :param base_url: URL of the given soup
        :type soup: bs4.BeautifulSoup
        :rtype ChartsRelease
        """
        release = ChartsRelease()
        year_tags = soup.select("#year_top option[selected]")
        year = int(year_tags[0]["value"])
        week_tags = soup.select("#week_top option[selected]")
        week = int(week_tags[0]["value"])
        release_date = ywd_to_date(year, week, 1)
        release.expires = release_date + datetime.timedelta(weeks=1)

        html_entries = soup.select("table.table-top > tbody > tr")
        for unparsed_entry in html_entries:
            parsed_entry = SnepChartsConnector.parse_entry(unparsed_entry)
            release.entries.append(parsed_entry)
            parsed_entry.url = '%s#top-%i' % (base_url, parsed_entry.rank)

        log.verbose('Produces %i entries' % len(release.entries))
        return release

    def retrieve_charts(self, charts_type='radio', date_interval='week', **kargs):
        url = make_url(charts_type,date_interval, kargs.get('year'), kargs.get('week'))
        page = requests.get(url).text
        soup = get_soup(page)
        return SnepChartsConnector.parse(soup, url)


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
    :param date_interval: str [week, year]
    :param year: int
    :param week: int
    :rtype str
    """
    date_interval_to_url_path = {
        'year': 'tops-annuel',
        'week': 'tops-semaine'
    }
    type_to_url_path = {
        'all_album': 'top-albums-fusionnes',
        'disk_album': 'top-albums-physiques',
        'digit_album': 'top-albums-telecharges',
        'digit_single': 'top-singles-telecharges',
        'stream_single': 'top-singles-streaming',
        'compil': 'top-compilations',
        'back_catalog': 'top-back-catalogue',
        'radio': 'top-radios'
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


def ywd_to_date(year, week, weekday):
    """
    Author: https://mail.python.org/pipermail/tutor/2013-July/096752.html
    Convert (year, week, isoweekday) tuple to a datetime.date().

    >>> datetime.date(2013, 7, 12).isocalendar()
    (2013, 28, 5)
    >>> ywd_to_date(2013, 28, 5)
    datetime.date(2013, 7, 12)
    """
    first = datetime.date(year, 1, 1)
    first_year, _first_week, first_weekday = first.isocalendar()

    if first_year == year:
        week -= 1

    return first + datetime.timedelta(days=week*7+weekday-first_weekday)

@event('plugin.register')
def register_plugin():
    plugin.register(SnepChartsConnector, 'charts_connector_snep', groups=['charts_connector'], api_ver=2)
