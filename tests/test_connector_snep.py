# -*- coding: utf8 -*-
from __future__ import unicode_literals, division, absolute_import
import datetime

from flexget.plugins.api_snep import SnepChartsConnector
from flexget.plugins.filter.charts import ChartsConnector, ChartsRelease, ChartsEntry
from tests import use_vcr


class SnepMockConnector(ChartsConnector):
    @property
    def organization(self):
        return 'snep'

    def retrieve_charts(self, charts_type='radio', date_interval='week', **kargs):
        """
        From http://www.snepmusique.com/tops-semaine/top-albums-fusionnes/?ye=2015&we=10
        at 2015-03-30
        :return: ChartsRelease
        """
        release = ChartsRelease()
        release.expires = datetime.date(2015, 3, 9)

        def build(artist, company, title, rank, best_rank, charted_weeks):
            result = ChartsEntry(
                artist=artist,
                title=title,
                rank=rank,
                best_rank=best_rank,
                charted_weeks=charted_weeks)
            result.company = company
            return result

        release.entries.append(build(
            artist="Louane",
            company="MERCURY MUSIC GROUP / FONTANA",
            title="CHAMBRE 12",
            rank=1,
            best_rank=1,
            charted_weeks=0))

        release.entries.append(build(
            artist="Christine and the Queens",
            company="BECAUSE MUSIC / BECAUSE MUSIC",
            title="CHALEUR HUMAINE",
            rank=2,
            best_rank=2,
            charted_weeks=38))

        release.entries.append(build(
            artist="Multi Interprètes",
            company="DEF JAM RECORDINGS FRANCE / DEF JAM",
            title="FIFTY SHADES OF GREY",
            rank=5,
            best_rank=3,
            charted_weeks=2))

        release.entries.append(build(
            artist="ZAZ",
            company="PLAY ON / PLAY ON",
            title="PARIS",
            rank=43,
            best_rank=2,
            charted_weeks=15))
        return release


class TestSnepParser(object):
    def test_organization(self):
        assert SnepChartsConnector().organization == 'snep'

    @use_vcr
    def test_parser(self):
        test_release = SnepChartsConnector().retrieve_charts('all_album', 'week', year=2015, week=10)
        mock_release = SnepMockConnector().retrieve_charts('all_album', 'week', year=2015, week=10)

        assert (len(test_release.entries) == 200), \
            "Expected 200 entries but parser produce %i entries." % len(test_release.entries)
        assert test_release.expires == mock_release.expires

        for entry in mock_release.entries:
            TestSnepParser.check_charts_entry(test_release.entries[entry.rank - 1], entry)

    @staticmethod
    def check_charts_entry(unchecked, reference):
        """Kind of SnepParsedChartEntry.equals
        :param unchecked: ChartsEntry
        :param reference: ChartsEntry
        """
        assert unchecked is not None, "Expected a charts entry but got None"
        assert unchecked.artist == reference.artist, "Expected %s but got %s" % (reference.artist, unchecked.artist)
        assert unchecked.company == reference.company, "Expected %s but got %s" % (reference.company, unchecked.company)
        assert unchecked.title == reference.title, "Expected %s but got %s" % (reference.title, unchecked.title)
        assert unchecked.rank == reference.rank, "Expected %i but got %i" % (reference.rank, unchecked.rank)
        assert unchecked.best_rank <= reference.best_rank, "Expected better position than #%i but got #%i" % (reference.best_rank, unchecked.best_rank)
        assert unchecked.charted_weeks >= reference.charted_weeks, "Expected longer in charts than %i week(s) but got %i" % (reference.charted_weeks, unchecked.charted_weeks)
