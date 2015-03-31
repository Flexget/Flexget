# -*- coding: utf8 -*-
from __future__ import unicode_literals, division, absolute_import

from flexget.utils.charts_snep import SnepChartsParser
from flexget.utils.charts_snep import SnepChartsEntry
from tests import use_vcr


class TestSnepParser(object):
    @use_vcr
    def test_parser(self):
        parser = SnepChartsParser()
        parser.retrieve_charts('all_album', 'week', 2015, 10)

        assert (len(parser.charts_entries) == 200), "Expected 200 entries but parser produce %i entries." % len(parser.charts_entries)
        responses = TestSnepParser.build_test_responses()
        for a_response in responses:
            TestSnepParser.check_one_entry(parser.charts_entries[a_response.stat_position-1], a_response)

    @staticmethod
    def check_one_entry(unchecked, reference):
        """Kind of SnepChartsEntry.equals
        :param unchecked: SnepChartsEntry
        :param reference: SnepChartsEntry
        """

        assert unchecked is not None, "Expected a charts entry but got None"
        assert unchecked.artist == reference.artist, "Expected %s but got %s" % (reference.artist, unchecked.artist)
        assert unchecked.company == reference.company, "Expected %s but got %s" % (reference.company, unchecked.company)
        assert unchecked.title == reference.title, "Expected %s but got %s" % (reference.title, unchecked.title)
        assert unchecked.stat_position == reference.stat_position, "Expected %i but got %i" % (reference.stat_position, unchecked.stat_position)
        assert unchecked.best_position <= reference.best_position, "Expected better position than #%i but got #%i" % (reference.best_position, unchecked.best_position)
        assert unchecked.weeks_on_charts >= reference.weeks_on_charts, "Expected longer in charts than %i week(s) but got %i" % (reference.weeks_on_charts, unchecked.weeks_on_charts)

    @staticmethod
    def build_test_responses():
        """
        From http://www.snepmusique.com/tops-semaine/top-albums-fusionnes/?ye=2015&we=10
        at 2015-03-30
        :return: [SnepChartsEntry]
        """
        result = []
        an_entry = SnepChartsEntry()
        an_entry.artist = "Louane"
        an_entry.company = "MERCURY MUSIC GROUP / FONTANA"
        an_entry.title = "CHAMBRE 12"
        an_entry.stat_position = 1
        an_entry.best_position = 1
        result.append(an_entry)

        an_entry = SnepChartsEntry()
        an_entry.artist = "Christine and the Queens"
        an_entry.company = "BECAUSE MUSIC / BECAUSE MUSIC"
        an_entry.title = "CHALEUR HUMAINE"
        an_entry.stat_position = 2
        an_entry.best_position = 2
        result.append(an_entry)

        an_entry = SnepChartsEntry()
        an_entry.artist = "Multi Interprètes"
        an_entry.company = "DEF JAM RECORDINGS FRANCE / DEF JAM"
        an_entry.title = "FIFTY SHADES OF GREY"
        an_entry.stat_position = 5
        an_entry.best_position = 3
        result.append(an_entry)

        an_entry = SnepChartsEntry()
        an_entry.artist = "ZAZ"
        an_entry.company = "PLAY ON / PLAY ON"
        an_entry.title = "PARIS"
        an_entry.stat_position = 43
        an_entry.best_position = 2
        result.append(an_entry)
        return result