# -*- coding: utf8 -*-
from __future__ import unicode_literals, division, absolute_import

from flexget.utils.charts_snep import SnepChartsParser
from tests import  use_vcr


class TestSnepParser(object):
    @use_vcr
    def test_parser(self):
        parser = SnepChartsParser()
        parser.retrieve_charts('all_album', 'week', 2015, 10)

        assert (len(parser.charts_entries) == 200), "Expected 200 entries but parser produce %i entries." % len(parser.charts_entries)
        TestSnepParser.subtest_parse_entry(parser.charts_entries[42])

    @staticmethod
    def subtest_parse_entry(entry):
        """Test if entry is correctly parsed from the
        #43 of http://www.snepmusique.com/tops-semaine/top-albums-fusionnes/?ye=2015&we=10
        :param entry: SnepChartsEntry"""

        assert (entry != None), "Expected a charts entry but got None"
        assert entry.artist == "ZAZ"
        assert entry.company == "PLAY ON / PLAY ON"
        assert entry.title == "PARIS"
        assert entry.stat_position == 43
        assert entry.best_position == 2