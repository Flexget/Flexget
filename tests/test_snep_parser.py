# -*- coding: utf8 -*-
from __future__ import unicode_literals, division, absolute_import
from flexget.entry import Entry

from flexget.utils.charts_snep import SnepChartsParser
from flexget.utils.charts_snep import SnepParsedChartEntry
from tests import use_vcr


class TestSnepParser(object):
    @use_vcr
    def test_parser(self):
        parser = SnepChartsParser()
        parser.retrieve_charts('all_album', 'week', 2015, 10)

        assert (len(parser.charts_entries) == 200), "Expected 200 entries but parser produce %i entries." % len(parser.charts_entries)
        responses = TestSnepParser.build_test_responses()
        for a_response in responses:
            TestSnepParser.check_charts_entry(parser.charts_entries[a_response.rank - 1], a_response)
            TestSnepParser.check_mapped_entry(parser.charts_entries[a_response.rank - 1], a_response)

    @staticmethod
    def check_charts_entry(unchecked, reference):
        """Kind of SnepParsedChartEntry.equals
        :param unchecked: flexget.utils.charts_snep.SnepParsedChartEntry
        :param reference: flexget.utils.charts_snep.SnepParsedChartEntry
        """
        assert unchecked is not None, "Expected a charts entry but got None"
        assert unchecked.artist == reference.artist, "Expected %s but got %s" % (reference.artist, unchecked.artist)
        assert unchecked.company == reference.company, "Expected %s but got %s" % (reference.company, unchecked.company)
        assert unchecked.song_title == reference.song_title, "Expected %s but got %s" % (reference.song_title, unchecked.song_title)
        assert unchecked.rank == reference.rank, "Expected %i but got %i" % (reference.rank, unchecked.rank)
        assert unchecked.best_rank <= reference.best_rank, "Expected better position than #%i but got #%i" % (reference.best_rank, unchecked.best_rank)
        assert unchecked.charted_weeks >= reference.charted_weeks, "Expected longer in charts than %i week(s) but got %i" % (reference.charted_weeks, unchecked.charted_weeks)

    @staticmethod
    def check_mapped_entry(unchecked, reference):
        """
        :param unchecked: flexget.utils.charts_snep.SnepParsedChartEntry
        :param reference: flexget.utils.charts_snep.SnepParsedChartEntry
        """
        mapped_entry = Entry()
        mapped_entry.update_using_map(SnepParsedChartEntry.get_entry_map(), unchecked)
        assert mapped_entry.get('music_artist', None) == reference.artist, "Expected %s but got %s" % (reference.artist, mapped_entry.get('music_artist', None))
        assert mapped_entry.get('music_company', None) == reference.company, "Expected %s but got %s" % (reference.company, mapped_entry.get('music_company', None))
        assert mapped_entry.get('music_title', None) == reference.song_title, "Expected %s but got %s" % (reference.song_title, mapped_entry.get('music_title', None))
        assert mapped_entry.get('charts_snep_rank', None) == reference.rank, "Expected %i but got %i" % (reference.rank, mapped_entry.get('charts_snep_rank', None))
        assert mapped_entry.get('charts_snep_best_rank', None) <= reference.best_rank, "Expected better position than #%i but got #%i" % (reference.best_rank, mapped_entry.get('charts_snep_best_rank', None))
        assert mapped_entry.get('charts_snep_weeks', None) >= reference.charted_weeks, "Expected longer in charts than %i week(s) but got %i" % (reference.charted_weeks, mapped_entry.get('charts_snep_weeks', None))

    @staticmethod
    def build_test_responses():
        """
        From http://www.snepmusique.com/tops-semaine/top-albums-fusionnes/?ye=2015&we=10
        at 2015-03-30
        :return: [SnepParsedChartEntry]
        """
        result = []
        an_entry = SnepParsedChartEntry()
        an_entry._artist = "Louane"
        an_entry._company = "MERCURY MUSIC GROUP / FONTANA"
        an_entry._song_title = "CHAMBRE 12"
        an_entry._rank = 1
        an_entry._best_rank = 1
        an_entry._charted_weeks = 0
        result.append(an_entry)

        an_entry = SnepParsedChartEntry()
        an_entry._artist = "Christine and the Queens"
        an_entry._company = "BECAUSE MUSIC / BECAUSE MUSIC"
        an_entry._song_title = "CHALEUR HUMAINE"
        an_entry._rank = 2
        an_entry._best_rank = 2
        an_entry._charted_weeks = 38
        result.append(an_entry)

        an_entry = SnepParsedChartEntry()
        an_entry._artist = "Multi Interprètes"
        an_entry._company = "DEF JAM RECORDINGS FRANCE / DEF JAM"
        an_entry._song_title = "FIFTY SHADES OF GREY"
        an_entry._rank = 5
        an_entry._best_rank = 3
        an_entry._charted_weeks = 2
        result.append(an_entry)

        an_entry = SnepParsedChartEntry()
        an_entry._artist = "ZAZ"
        an_entry._company = "PLAY ON / PLAY ON"
        an_entry._song_title = "PARIS"
        an_entry._rank = 43
        an_entry._best_rank = 2
        an_entry._charted_weeks = 15
        result.append(an_entry)
        return result